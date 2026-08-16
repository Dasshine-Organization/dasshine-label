"""
项目与标注相关的权限判断（与前端 imageAnnotationPermissions 对齐）。
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

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


def _meta_assignee_ids(task: Task) -> List[int]:
    meta = task.task_metadata if isinstance(task.task_metadata, dict) else {}
    ids: List[int] = []
    for key in ("assignee_ids", "co_assignee_ids"):
        raw = meta.get(key)
        if not isinstance(raw, list):
            continue
        for x in raw:
            try:
                uid = int(x)
            except (TypeError, ValueError):
                continue
            if uid not in ids:
                ids.append(uid)
    if task.assignee_id is not None and task.assignee_id not in ids:
        ids.insert(0, task.assignee_id)
    return ids


def is_task_assignee(task: Task, user: User) -> bool:
    """主受让人或交叉共标人。"""
    if task.assignee_id == user.id:
        return True
    return user.id in _meta_assignee_ids(task)


def cross_submit_progress(task: Task) -> dict[str, Any]:
    meta = task.task_metadata if isinstance(task.task_metadata, dict) else {}
    try:
        need = int(meta.get("cross_validate_count") or 1)
    except (TypeError, ValueError):
        need = 1
    need = max(1, min(need, 5))
    submitted = meta.get("submitted_annotator_ids")
    if not isinstance(submitted, list):
        submitted = []
    return {
        "need": need,
        "done": len(submitted),
        "submitted_annotator_ids": submitted,
        "assignee_ids": _meta_assignee_ids(task),
    }


def can_access_task_workspace(db: Session, task: Task, user: User) -> bool:
    """可读写任务工作台草稿：超管/平台管理员、项目负责人、成员、或受让人"""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True
    project = task.project
    m = get_project_member(db, project.id, user.id)
    if m:
        return True
    return is_task_assignee(task, user)


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


def can_review_project(db: Session, project: Project, user: User) -> bool:
    """审核任务：平台管理员；平台审核员（须为项目成员）；或项目 owner/manager/reviewer"""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return True
    m = get_project_member(db, project.id, user.id)
    if not m:
        return False
    if user.role == UserRole.REVIEWER:
        return True
    return m.role in ("owner", "manager", "reviewer")
