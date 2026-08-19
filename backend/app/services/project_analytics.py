"""项目吞吐 / 单价 / TAT 分析"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.services.project_service import _get_schema


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2


def get_project_analytics(db: Session, project: Project, days: int = 30) -> Dict[str, Any]:
    days = max(1, min(days, 365))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    schema = _get_schema(project)
    try:
        price_per_task = float(schema.get("price_per_task") or 0)
    except (TypeError, ValueError):
        price_per_task = 0.0

    tasks = db.query(Task).filter(Task.project_id == project.id).all()
    approved = [t for t in tasks if t.status == TaskStatus.APPROVED]
    approved_recent = [
        t for t in approved
        if _utc(t.completed_at) and _utc(t.completed_at) >= since  # type: ignore
    ]

    annotate_hours: List[float] = []
    review_hours: List[float] = []
    e2e_hours: List[float] = []
    for t in approved:
        start = _utc(t.started_at)
        sub = _utc(t.submitted_at)
        done = _utc(t.completed_at)
        if start and sub:
            annotate_hours.append((sub - start).total_seconds() / 3600)
        if sub and done:
            review_hours.append((done - sub).total_seconds() / 3600)
        if start and done:
            e2e_hours.append((done - start).total_seconds() / 3600)

    # 按完成日吞吐
    daily: Dict[str, int] = {}
    for t in approved_recent:
        d = _utc(t.completed_at)
        if not d:
            continue
        key = d.date().isoformat()
        daily[key] = daily.get(key, 0) + 1
    series = [{"date": k, "approved": daily[k]} for k in sorted(daily.keys())]

    approved_total = len(approved)
    spend = round(approved_total * price_per_task, 2)

    return {
        "project_id": project.id,
        "days": days,
        "price_per_task": price_per_task,
        "summary": {
            "total_tasks": len(tasks),
            "approved": approved_total,
            "approved_in_window": len(approved_recent),
            "submitted": sum(1 for t in tasks if t.status in (TaskStatus.SUBMITTED, TaskStatus.REVIEWING)),
            "pending": sum(1 for t in tasks if t.status == TaskStatus.PENDING),
            "estimated_spend": spend,
            "throughput_per_day": round(len(approved_recent) / days, 2) if days else 0,
        },
        "tat_hours": {
            "annotate_p50": _median(annotate_hours),
            "review_p50": _median(review_hours),
            "e2e_p50": _median(e2e_hours),
            "annotate_samples": len(annotate_hours),
            "review_samples": len(review_hours),
        },
        "daily_throughput": series,
    }
