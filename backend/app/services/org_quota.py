"""
组织配额：项目数 / 任务数 / 成员数上限。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.organization import Organization, OrganizationMember
from app.models.project import Project
from app.models.task import Task

DEFAULT_QUOTA: Dict[str, int] = {
    "max_projects": 50,
    "max_tasks": 100_000,
    "max_members": 200,
    "credits": 10_000,
}


def normalize_quota(raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    out = dict(DEFAULT_QUOTA)
    if isinstance(raw, dict):
        for k in DEFAULT_QUOTA:
            if k in raw and raw[k] is not None:
                try:
                    out[k] = max(0, int(raw[k]))
                except (TypeError, ValueError):
                    pass
    return out


def org_usage(db: Session, org_id: int) -> Dict[str, int]:
    projects = db.query(Project).filter(Project.organization_id == org_id).all()
    project_ids = [p.id for p in projects]
    task_count = 0
    if project_ids:
        task_count = db.query(Task).filter(Task.project_id.in_(project_ids)).count()
    member_count = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id)
        .count()
    )
    return {
        "projects": len(projects),
        "tasks": task_count,
        "members": member_count,
    }


def check_can_add_project(db: Session, org: Organization) -> Tuple[bool, str]:
    quota = normalize_quota(getattr(org, "quota", None))
    usage = org_usage(db, org.id)
    if usage["projects"] >= quota["max_projects"]:
        return False, f"组织项目数已达上限 ({quota['max_projects']})"
    return True, ""


def check_can_add_tasks(
    db: Session, org: Optional[Organization], add_count: int = 1
) -> Tuple[bool, str]:
    if org is None:
        return True, ""
    quota = normalize_quota(getattr(org, "quota", None))
    usage = org_usage(db, org.id)
    if usage["tasks"] + max(0, add_count) > quota["max_tasks"]:
        return False, f"组织任务数将超过上限 ({quota['max_tasks']})"
    return True, ""


def check_can_add_member(db: Session, org: Organization) -> Tuple[bool, str]:
    quota = normalize_quota(getattr(org, "quota", None))
    usage = org_usage(db, org.id)
    if usage["members"] >= quota["max_members"]:
        return False, f"组织成员数已达上限 ({quota['max_members']})"
    return True, ""
