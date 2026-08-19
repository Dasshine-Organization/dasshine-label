"""
黄金题盲测：对标注员剥离敏感字段；提交后比对答案写 metadata。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User
from app.services.project_acl import can_review_project


def can_see_golden(db: Session, task: Task, user: User) -> bool:
    if getattr(user, "is_admin", False):
        return True
    project = task.project
    if project is None:
        return False
    return can_review_project(db, project, user)


def strip_golden_from_task_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """从任务/工作台响应中移除盲测敏感字段。"""
    out = dict(payload)
    out.pop("is_golden", None)
    out.pop("golden_answer", None)
    return out


def maybe_attach_golden_fields(
    db: Session,
    task: Task,
    user: User,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """仅审核/管理可见 is_golden 与答案摘要。"""
    if not can_see_golden(db, task, user):
        return strip_golden_from_task_payload(payload)
    payload = dict(payload)
    payload["is_golden"] = bool(task.is_golden)
    if task.is_golden:
        ans = task.golden_answer if isinstance(task.golden_answer, dict) else None
        payload["golden_answer"] = ans
        payload["has_golden_answer"] = bool(ans and (ans.get("data") or ans))
    return payload


def record_golden_match(
    db: Session,
    task: Task,
    user_id: int,
    annotation_data: Optional[Dict[str, Any]],
) -> Optional[bool]:
    """
    若为黄金题且有标准答案，比对并写入 task_metadata.golden_scores[user_id]。
    返回是否匹配；非黄金题返回 None。
    """
    if not task.is_golden or not task.golden_answer:
        return None
    from app.services.quality_control import QualityControlService

    gold = task.golden_answer
    if isinstance(gold, dict) and isinstance(gold.get("data"), dict):
        gold_payload = gold["data"]
    elif isinstance(gold, dict):
        gold_payload = gold
    else:
        return None

    svc = QualityControlService(db)
    matched = svc._results_match(annotation_data or {}, gold_payload)
    meta = dict(task.task_metadata) if isinstance(task.task_metadata, dict) else {}
    scores = meta.get("golden_scores")
    if not isinstance(scores, dict):
        scores = {}
    scores[str(user_id)] = {"matched": bool(matched)}
    meta["golden_scores"] = scores
    task.task_metadata = meta

    # P17：连续黄金题失败 streak（按项目记在 member.meta）
    if task.project_id:
        from app.services.guidelines import get_member_streak, set_member_streak
        from app.services.notifications import notify

        streak = get_member_streak(db, task.project_id, user_id)
        if matched:
            streak = 0
        else:
            streak += 1
        set_member_streak(db, task.project_id, user_id, streak)
        qc = (task.project.quality_config if task.project else None) or {}
        try:
            threshold = int(qc.get("golden_fail_threshold") or 5)
        except (TypeError, ValueError):
            threshold = 5
        if not matched and streak >= threshold:
            notify(
                db,
                user_id,
                type="golden_paused",
                title="领取已暂停",
                body=f"连续 {streak} 道黄金题未通过，已暂停领取新任务，请联系管理员。",
                payload={"project_id": task.project_id, "streak": streak},
            )

    return bool(matched)
