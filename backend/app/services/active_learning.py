"""主动学习池（P19）。

把「模型没把握」的待领任务标进 task_metadata.active_learning_pool，
claim-next 可选择先发这些题。入池条件：

- 状态 PENDING 且无人领取
- pre_label_confidence 缺失，或低于 quality_config.active_learning_threshold
  （未配置则用 AUTO_LABEL_CONFIDENCE_THRESHOLD）

高置信任务若已在池内会在 sync 时移出，避免池被已经高置信的题占满。
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.project import Project
from app.models.task import Task, TaskStatus


def _threshold(project: Project) -> float:
    qc = project.quality_config if isinstance(project.quality_config, dict) else {}
    try:
        if qc.get("active_learning_threshold") is not None:
            return float(qc["active_learning_threshold"])
    except (TypeError, ValueError):
        pass
    return float(settings.AUTO_LABEL_CONFIDENCE_THRESHOLD)


def _meta(task: Task) -> Dict[str, Any]:
    return dict(task.task_metadata or {})


def sync_pool(db: Session, project: Project) -> Dict[str, int]:
    """扫描项目待领任务，按阈值增删池标记。返回 added/removed 计数。"""
    th = _threshold(project)
    tasks = (
        db.query(Task)
        .filter(
            Task.project_id == project.id,
            Task.status == TaskStatus.PENDING,
            Task.assignee_id.is_(None),
        )
        .all()
    )
    added = 0
    removed = 0
    for t in tasks:
        conf = t.pre_label_confidence
        meta = _meta(t)
        in_pool = bool(meta.get("active_learning_pool"))
        should = conf is None or conf < th
        if should and not in_pool:
            meta["active_learning_pool"] = True
            meta["active_learning_reason"] = "low_confidence" if conf is not None else "no_prelabel"
            t.task_metadata = meta
            added += 1
        elif not should and in_pool:
            meta.pop("active_learning_pool", None)
            meta.pop("active_learning_reason", None)
            t.task_metadata = meta
            removed += 1
    db.flush()
    return {"synced": len(tasks), "added": added, "removed": removed, "threshold": th}


def list_pool(db: Session, project_id: int, limit: int = 100) -> List[Task]:
    """池内待领任务：低置信优先。JSON 标记在 Python 侧过滤（兼容 SQLite/PG）。"""
    rows = (
        db.query(Task)
        .filter(
            Task.project_id == project_id,
            Task.status == TaskStatus.PENDING,
            Task.assignee_id.is_(None),
        )
        .order_by(Task.pre_label_confidence.asc().nullsfirst(), Task.priority.desc(), Task.id.asc())
        .limit(min(limit * 4, 500))
        .all()
    )
    pooled = [t for t in rows if _meta(t).get("active_learning_pool")]
    return pooled[: min(limit, 500)]


def pool_count(db: Session, project_id: int) -> int:
    return len(list_pool(db, project_id, limit=500))


def pool_task_ids(db: Session, project_id: int) -> List[int]:
    return [t.id for t in list_pool(db, project_id, limit=200)]


def promote_for_relabel(db: Session, project_id: int, task_ids: List[int]) -> int:
    """管理员指定重标：释放领取人、回到 PENDING，并强制留在池中。"""
    if not task_ids:
        return 0
    rows = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.id.in_(task_ids))
        .all()
    )
    n = 0
    for t in rows:
        t.status = TaskStatus.PENDING
        t.assignee_id = None
        meta = _meta(t)
        meta["active_learning_pool"] = True
        meta["relabel_requested"] = True
        t.task_metadata = meta
        n += 1
    db.flush()
    return n


def task_pool_item(t: Task) -> Dict[str, Any]:
    meta = _meta(t)
    data = t.data if isinstance(getattr(t, "data", None), dict) else {}
    return {
        "id": t.id,
        "pre_label_confidence": t.pre_label_confidence,
        "priority": t.priority,
        "reason": meta.get("active_learning_reason"),
        "filename": data.get("filename") or data.get("file_name"),
    }
