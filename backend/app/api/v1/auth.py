"""
认证路由
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.config import settings
from app.core.password_policy import validate_password
from app.core.security import create_access_token, verify_password, get_password_hash
from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole, UserStatus
from app.services import audit

router = APIRouter()


# 请求/响应模型
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    level: str
    avatar: str | None
    is_admin: bool = False          # 新增字段，默认 False
    active_org_id: int | None = None

    model_config = {"from_attributes": True}   # 允许从 ORM 对象转换

    @model_validator(mode='after')
    def set_is_admin(self):
        # role 字段已经有值了，用它来计算 is_admin
        self.is_admin = self.role in ('super_admin', 'admin')
        return self


@router.post("/auth/register", response_model=UserResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """用户注册（默认标注员角色）"""
    if not settings.AUTH_REGISTER_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="公开注册已关闭，请使用组织邀请或 SSO",
        )

    pwd_err = validate_password(user_data.password)
    if pwd_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pwd_err)

    # 检查用户名
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已存在"
        )
    
    # 创建用户
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=UserRole.ANNOTATOR,
        status=UserStatus.ACTIVE
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)

    from app.services.organization_service import OrganizationService

    OrganizationService(db).ensure_personal_org(user)
    db.refresh(user)

    return user


@router.get("/auth/public-config")
def public_auth_config():
    """前端启动配置。demo_entries_enabled 仅看 DEMO_ENTRIES_ENABLED，不因 DEBUG 强开。"""
    from app.services.oidc import oidc_configured

    demo = bool(settings.DEMO_ENTRIES_ENABLED)
    return {
        "register_enabled": bool(settings.AUTH_REGISTER_ENABLED),
        "oidc_enabled": oidc_configured(),
        "frontend_url": settings.FRONTEND_URL,
        "demo_entries_enabled": demo,
        "metrics_enabled": bool(settings.METRICS_ENABLED),
    }


@router.post("/auth/login", response_model=TokenResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """用户登录"""
    # 查找用户
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username)
    ).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    from app.services.organization_service import OrganizationService

    OrganizationService(db).ensure_personal_org(user)
    user.last_login = datetime.now(timezone.utc)
    audit.record(
        db,
        action="auth.login",
        actor_user_id=user.id,
        organization_id=user.active_org_id,
        detail={"method": "password"},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(user)
    
    # 创建令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "level": user.level,
            "is_admin": user.is_admin,
            "active_org_id": user.active_org_id,
        }
    }


@router.get("/auth/oidc/login")
def oidc_login():
    """跳转 IdP 授权页"""
    from app.services.oidc import build_authorize_url, oidc_configured

    if not oidc_configured():
        raise HTTPException(status_code=503, detail="OIDC 未配置")
    try:
        url, _state = build_authorize_url()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"OIDC 不可用: {e}") from e
    return RedirectResponse(url)


@router.get("/auth/oidc/callback")
def oidc_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """OIDC 回调：换用户并跳转前端带 token"""
    from app.services.oidc import exchange_code, oidc_configured, upsert_oidc_user
    from app.services.organization_service import OrganizationService

    if error:
        return RedirectResponse(
            f"{settings.FRONTEND_URL.rstrip('/')}/login?oidc_error={error}"
        )
    if not oidc_configured() or not code:
        raise HTTPException(status_code=400, detail="OIDC 回调无效")
    try:
        claims = exchange_code(code)
        user = upsert_oidc_user(db, claims)
        OrganizationService(db).ensure_personal_org(user)
        user.last_login = datetime.now(timezone.utc)
        audit.record(
            db,
            action="auth.login",
            actor_user_id=user.id,
            organization_id=user.active_org_id,
            detail={"method": "oidc"},
            ip=request.client.host if request.client else None,
        )
        db.commit()
        token = create_access_token(
            data={"sub": str(user.id), "username": user.username, "role": str(user.role)},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    except Exception as e:
        return RedirectResponse(
            f"{settings.FRONTEND_URL.rstrip('/')}/login?oidc_error=exchange_failed"
        )
    return RedirectResponse(
        f"{settings.FRONTEND_URL.rstrip('/')}/login?oidc_token={token}"
    )


@router.get("/auth/me", response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户信息"""
    from app.services.organization_service import OrganizationService

    OrganizationService(db).ensure_personal_org(current_user)
    db.refresh(current_user)
    return current_user


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """当前用户修改密码"""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前密码不正确",
        )
    pwd_err = validate_password(body.new_password)
    if pwd_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=pwd_err)
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    current_user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    return {"message": "密码已更新"}


@router.post("/auth/refresh")
def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新令牌"""
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.id)},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
