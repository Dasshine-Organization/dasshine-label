"""
项目与标注相关的权限判断（与前端 imageAnnotationPermissions 对齐）。
"""

from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User, UserRole


def get_project_member(db: Session, project_id: int, user_id: int) -> Optional[ProjectMember]:
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )


def is_project_owner_user(project: Project, member: Optional[ProjectMember], user: User) -> bool:
    """项目所有者：创建者或与成员表中 role=owner 一致"""
    if project.created_by_id == user.id:
        return True
    if member and member.role == "owner":
        return True
    return False


def can_access_task_workspace(db: Session, task: Task, user: User) -> bool:
    """可读写任务工作台草稿：超管/平台管理员、项目负责人、成员、或受让人"""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True
    project = task.project
    m = get_project_member(db, project.id, user.id)
    if m:
        return True
    if task.assignee_id == user.id:
        return True
    return False


def can_edit_project_label_classes(db: Session, project: Project, user: User) -> bool:
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True
    m = get_project_member(db, project.id, user.id)
    if not m:
        return False
    return m.role in ("owner", "manager", "annotator")


def can_delete_project_label_class(db: Session, project: Project, user: User) -> bool:
    """仅超级管理员或项目所有者（创建者 / owner 角色）可删除标签类"""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    m = get_project_member(db, project.id, user.id)
    return is_project_owner_user(project, m, user)


def get_task_and_project(db: Session, task_id: int) -> Tuple[Optional[Task], Optional[Project]]:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return None, None
    return task, task.project


def can_administrate_project(db: Session, project: Project, user: User) -> bool:
    """修改/删除项目：平台管理员或项目所有者"""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True
    m = get_project_member(db, project.id, user.id)
    return is_project_owner_user(project, m, user)
