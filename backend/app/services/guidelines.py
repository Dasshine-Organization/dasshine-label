"""项目标注规范（Markdown）+ 必读确认。内容存 quality_config；确认存 project_members.meta。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember
from app.models.user import User
from app.services.project_acl import get_project_member


def _qc(project: Project) -> Dict[str, Any]:
    return dict(project.quality_config or {}) if isinstance(project.quality_config, dict) else {}


def _member_meta(member: Optional[ProjectMember]) -> Dict[str, Any]:
    if not member or not isinstance(member.meta, dict):
        return {}
    return dict(member.meta)


def guidelines_payload(project: Project, user: Optional[User] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    qc = _qc(project)
    version = int(qc.get("guidelines_version") or 0)
    md = str(qc.get("guidelines_md") or "")
    must_read = bool(qc.get("guidelines_must_read", True)) if md.strip() else False
    ack_version = 0
    if user and db is not None:
        member = get_project_member(db, project.id, user.id)
        meta = _member_meta(member)
        try:
            ack_version = int(meta.get("guideline_ack_version") or 0)
        except (TypeError, ValueError):
            ack_version = 0
        # 项目创建者 / 超管可跳过必读门槛，但仍返回状态
        if getattr(user, "is_admin", False) or project.created_by_id == user.id:
            needs_ack = False
        else:
            needs_ack = bool(must_read and version > 0 and ack_version < version)
    else:
        needs_ack = bool(must_read and version > 0)

    return {
        "project_id": project.id,
        "guidelines_md": md,
        "guidelines_version": version,
        "must_read": must_read,
        "ack_version": ack_version,
        "needs_ack": needs_ack,
    }


def update_guidelines(
    project: Project,
    *,
    markdown: str,
    must_read: Optional[bool] = None,
    bump: bool = True,
) -> Dict[str, Any]:
    qc = _qc(project)
    qc["guidelines_md"] = markdown or ""
    if must_read is not None:
        qc["guidelines_must_read"] = bool(must_read)
    elif "guidelines_must_read" not in qc:
        qc["guidelines_must_read"] = True
    if bump:
        try:
            qc["guidelines_version"] = int(qc.get("guidelines_version") or 0) + 1
        except (TypeError, ValueError):
            qc["guidelines_version"] = 1
    elif not qc.get("guidelines_version"):
        qc["guidelines_version"] = 1 if (markdown or "").strip() else 0
    project.quality_config = qc
    return qc


def ack_guidelines(db: Session, project: Project, user: User) -> Tuple[bool, Dict[str, Any]]:
    qc = _qc(project)
    version = int(qc.get("guidelines_version") or 0)
    if version <= 0:
        return False, {"error": "项目尚无标注规范"}

    member = get_project_member(db, project.id, user.id)
    if not member:
        # 自动建 annotator 成员以便记录确认（claim / 工作台用户）
        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role="annotator",
            can_assign=False,
            can_review=False,
            can_export=False,
            meta={},
        )
        db.add(member)
        db.flush()

    meta = _member_meta(member)
    meta["guideline_ack_version"] = version
    member.meta = meta
    return True, guidelines_payload(project, user, db)


def ensure_guidelines_acked(db: Session, project: Project, user: User) -> Optional[str]:
    """若需必读未确认，返回错误文案；否则 None。"""
    st = guidelines_payload(project, user, db)
    if st.get("needs_ack"):
        return "请先阅读并确认项目标注规范后再领取/标注任务"
    return None


def get_member_streak(db: Session, project_id: int, user_id: int) -> int:
    member = get_project_member(db, project_id, user_id)
    meta = _member_meta(member)
    try:
        return int(meta.get("golden_fail_streak") or 0)
    except (TypeError, ValueError):
        return 0


def set_member_streak(db: Session, project_id: int, user_id: int, streak: int) -> None:
    member = get_project_member(db, project_id, user_id)
    if not member:
        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role="annotator",
            meta={},
        )
        db.add(member)
        db.flush()
    meta = _member_meta(member)
    meta["golden_fail_streak"] = max(0, int(streak))
    member.meta = meta
