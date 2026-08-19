"""
API依赖注入
"""

from typing import Generator, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.security import decode_access_token
from app.core.exceptions import raise_unauthorized
from app.models.user import User

# 安全scheme
security = HTTPBearer(auto_error=False)


def get_db() -> Generator:
    """获取数据库会话"""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> User:
    """获取当前用户（JWT 或组织 API Key）"""
    raw_key = None
    if x_api_key and x_api_key.startswith("ds_"):
        raw_key = x_api_key
    elif credentials and credentials.credentials.startswith("ds_"):
        raw_key = credentials.credentials

    if raw_key:
        from app.models.organization import OrganizationMember
        from app.services.org_api_keys import resolve_api_key

        resolved = resolve_api_key(db, raw_key)
        if not resolved:
            raise_unauthorized("无效的 API Key")
        key, org = resolved
        user = None
        if key.created_by_id:
            user = db.query(User).filter(User.id == key.created_by_id).first()
        if not user:
            owner = (
                db.query(OrganizationMember)
                .filter(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.role == "owner",
                )
                .first()
            )
            if owner:
                user = db.query(User).filter(User.id == owner.user_id).first()
        if not user or not user.is_active:
            raise_unauthorized("API Key 无关联用户")
        # 请求期内切换作用域（落库 active_org，便于后续调用）
        user.active_org_id = org.id
        request.state.auth_via = "api_key"
        request.state.api_org_id = org.id
        db.commit()
        return user

    if not credentials:
        raise_unauthorized("未提供认证令牌")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise_unauthorized("无效的认证令牌")

    user_id = payload.get("sub")
    if not user_id:
        raise_unauthorized("无效的认证令牌")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise_unauthorized("用户不存在")

    if not user.is_active:
        raise_unauthorized("用户已被禁用")

    request.state.auth_via = "jwt"
    return user


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前管理员"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user
