"""
组织作用域（硬隔离）：任务池 / 项目读 / claim / 审核队列。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.services.organization_service import OrganizationService
from app.services.project_acl import get_project_member


def ensure_active_org_id(db: Session, user: User) -> Optional[int]:
    """确保个人组织并返回 active_org_id（超管可为 None 表示全局）。"""
    svc = OrganizationService(db)
    if not user.is_admin:
        svc.ensure_personal_org(user)
    elif user.active_org_id is None:
        # 超管无当前组织：不强制；有则用于可选收窄
        pass
    else:
        svc.ensure_personal_org(user)
    return user.active_org_id


def user_can_access_org_project(db: Session, project: Project, user: User) -> bool:
    """
    非超管：项目须属于用户可访问组织，且为创建者或项目成员。
    超管：放行。
    """
    if user.is_admin:
        return True
    org_id = getattr(project, "organization_id", None)
    svc = OrganizationService(db)
    svc.ensure_personal_org(user)
    if org_id is not None:
        if not svc.user_in_org(user.id, org_id):
            return False
        # 当前工作组织不一致时仍允许访问自己所属组织的项目（避免切换 org 后 403 误伤）
        # 硬隔离只要求「属于该组织」，不要求必须等于 active_org
    else:
        # 无组织旧项目：仅创建者或成员
        pass
    if project.created_by_id == user.id:
        return True
    return get_project_member(db, project.id, user.id) is not None


def project_visible_in_active_org(db: Session, project: Project, user: User) -> bool:
    """
    任务池 / claim 用：非超管只能操作当前 active_org 下的项目。
    超管：有 active_org 则同样收窄；无则全局。
    """
    if user.is_admin and not user.active_org_id:
        return True
    active = ensure_active_org_id(db, user)
    if active is None:
        return user.is_admin
    return getattr(project, "organization_id", None) == active
