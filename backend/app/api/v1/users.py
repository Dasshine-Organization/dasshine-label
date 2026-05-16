"""
用户管理API
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, get_current_admin
from app.core.password_policy import validate_password
from app.core.permissions import can_assign_role, has_platform_permission
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus, AnnotatorLevel

router = APIRouter()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None
    role: UserRole = UserRole.ANNOTATOR


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    level: Optional[AnnotatorLevel] = None
    skills: Optional[List[str]] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    status: str
    level: str
    accuracy_score: float
    completed_tasks: int
    is_admin: bool = False

    model_config = {"from_attributes": True}


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        status=user.status.value if hasattr(user.status, "value") else str(user.status),
        level=user.level.value if hasattr(user.level, "value") else str(user.level),
        accuracy_score=user.accuracy_score,
        completed_tasks=user.completed_tasks,
        is_admin=user.is_admin,
    )


def _apply_role_update(actor: User, user: User, new_role: UserRole) -> None:
    if user.role == new_role:
        return
    if not can_assign_role(actor, new_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权分配该角色",
        )
    # 非超级管理员不能修改超级管理员
    if user.role == UserRole.SUPER_ADMIN and actor.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法修改超级管理员",
        )
    user.role = new_role


@router.get("/users/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户信息"""
    return _user_to_response(current_user)


@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 50,
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
):
    """获取用户列表 (管理员)"""
    query = db.query(User).filter(User.status != UserStatus.DELETED)

    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)

    users = query.order_by(User.id.desc()).offset(skip).limit(limit).all()
    return [_user_to_response(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """获取用户详情 (管理员)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _user_to_response(user)


@router.post("/users", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """创建用户 (管理员)"""
    if not can_assign_role(current_user, user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权创建该角色的用户",
        )

    pwd_err = validate_password(user.password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="邮箱已存在")

    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        role=user.role,
        status=UserStatus.ACTIVE,
        level=AnnotatorLevel.NOVICE,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return _user_to_response(db_user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """更新用户信息 (管理员)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == current_user.id and user_update.role and user_update.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    update_data = user_update.model_dump(exclude_unset=True)

    if "role" in update_data and update_data["role"] is not None:
        _apply_role_update(current_user, user, update_data.pop("role"))

    if "skills" in update_data and update_data["skills"] is not None:
        update_data["skills"] = json.dumps(update_data["skills"])

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    body: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """管理员重置用户密码"""
    if not has_platform_permission(current_user, "users.reset_password"):
        raise HTTPException(status_code=403, detail="权限不足")

    pwd_err = validate_password(body.new_password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="无法重置超级管理员密码")

    user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    return {"message": "密码已重置"}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """删除用户 (管理员) — 软删除"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="无法删除超级管理员")

    user.status = UserStatus.DELETED
    db.commit()
    return {"message": "用户已删除"}


@router.get("/users/{user_id}/stats")
def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户统计信息"""
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="权限不足")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return {
        "user_id": user.id,
        "username": user.username,
        "accuracy_score": user.accuracy_score,
        "efficiency_score": user.efficiency_score,
        "total_tasks": user.total_tasks,
        "completed_tasks": user.completed_tasks,
        "completion_rate": user.completion_rate,
        "level": user.level.value if hasattr(user.level, "value") else str(user.level),
    }
