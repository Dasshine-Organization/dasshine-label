"""项目吞吐 / 单价 / TAT 分析（P19 运营看板）。

指标口径：
- 吞吐：窗口内 completed_at 落在近 N 天的「已通过」任务数 / 天数
- 单价成本：schema.price_per_task × 历史全部已通过数（累计，非窗口）
- TAT：标注 started_at→submitted_at、审核 submitted_at→completed_at、端到端 p50（小时）

计数与日吞吐走 SQL 聚合；TAT 只拉取已通过任务的时间戳列（不载入 data/JSON）。
completed_at 在审核通过 / 一致率自动过审时写入；历史任务若无该字段则不进 TAT 样本。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Date, cast, func
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

    status_rows = (
        db.query(Task.status, func.count(Task.id))
        .filter(Task.project_id == project.id)
        .group_by(Task.status)
        .all()
    )
    by_status: Dict[Any, int] = {status: int(n) for status, n in status_rows}
    total_tasks = sum(by_status.values())
    approved_total = by_status.get(TaskStatus.APPROVED, 0)
    submitted = by_status.get(TaskStatus.SUBMITTED, 0) + by_status.get(TaskStatus.REVIEWING, 0)
    pending = by_status.get(TaskStatus.PENDING, 0)

    approved_in_window = int(
        db.query(func.count(Task.id))
        .filter(
            Task.project_id == project.id,
            Task.status == TaskStatus.APPROVED,
            Task.completed_at.isnot(None),
            Task.completed_at >= since,
        )
        .scalar()
        or 0
    )

    daily_rows = (
        db.query(cast(Task.completed_at, Date).label("day"), func.count(Task.id))
        .filter(
            Task.project_id == project.id,
            Task.status == TaskStatus.APPROVED,
            Task.completed_at.isnot(None),
            Task.completed_at >= since,
        )
        .group_by("day")
        .order_by("day")
        .all()
    )
    series = [
        {"date": day.isoformat() if hasattr(day, "isoformat") else str(day), "approved": int(n)}
        for day, n in daily_rows
        if day is not None
    ]

    # 仅时间戳列，避免把整表 JSON data 拉进内存
    time_rows = (
        db.query(Task.started_at, Task.submitted_at, Task.completed_at)
        .filter(Task.project_id == project.id, Task.status == TaskStatus.APPROVED)
        .all()
    )
    annotate_hours: List[float] = []
    review_hours: List[float] = []
    e2e_hours: List[float] = []
    for start_raw, sub_raw, done_raw in time_rows:
        start = _utc(start_raw)
        sub = _utc(sub_raw)
        done = _utc(done_raw)
        if start and sub and sub >= start:
            annotate_hours.append((sub - start).total_seconds() / 3600)
        if sub and done and done >= sub:
            review_hours.append((done - sub).total_seconds() / 3600)
        if start and done and done >= start:
            e2e_hours.append((done - start).total_seconds() / 3600)

    spend = round(approved_total * price_per_task, 2)

    return {
        "project_id": project.id,
        "days": days,
        "price_per_task": price_per_task,
        "summary": {
            "total_tasks": total_tasks,
            "approved": approved_total,
            "approved_in_window": approved_in_window,
            "submitted": submitted,
            "pending": pending,
            "estimated_spend": spend,
            "throughput_per_day": round(approved_in_window / days, 2) if days else 0,
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
