"""
任务提交门闩：交叉共标满 N 人后才进入 SUBMITTED；可选一致率自动过审。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.task import Task, TaskStatus


def task_meta(task: Task) -> Dict[str, Any]:
    return dict(task.task_metadata) if isinstance(task.task_metadata, dict) else {}


def required_annotator_count(task: Task) -> int:
    meta = task_meta(task)
    try:
        n = int(meta.get("cross_validate_count") or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, 5))


def assignee_ids_from_task(task: Task) -> List[int]:
    meta = task_meta(task)
    ids: List[int] = []
    raw = meta.get("assignee_ids")
    if isinstance(raw, list):
        for x in raw:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
    if task.assignee_id is not None and task.assignee_id not in ids:
        ids.insert(0, task.assignee_id)
    co = meta.get("co_assignee_ids")
    if isinstance(co, list):
        for x in co:
            try:
                uid = int(x)
            except (TypeError, ValueError):
                continue
            if uid not in ids:
                ids.append(uid)
    return ids


def count_distinct_latest_annotators(db: Session, task_id: int) -> Set[int]:
    rows = (
        db.query(Annotation.annotator_id)
        .filter(Annotation.task_id == task_id, Annotation.is_latest.is_(True))
        .distinct()
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


def apply_cross_submit_gate(
    db: Session,
    task: Task,
    user_id: int,
    *,
    work_time: int | None = None,
) -> Dict[str, Any]:
    """
    在已写入当前用户 Annotation 之后调用。
    未满 N：保持 ANNOTATING；满 N：SUBMITTED。
    返回进度信息。
    """
    meta = task_meta(task)
    need = required_annotator_count(task)
    db.flush()  # ensure new Annotation visible for count
    annotators = count_distinct_latest_annotators(db, task.id)
    annotators.add(user_id)
    submitted_ids = sorted(annotators)

    meta["submitted_annotator_ids"] = submitted_ids
    meta["cross_validate_count"] = need
    meta["submit_progress"] = {"done": len(submitted_ids), "need": need}
    task.task_metadata = meta

    now = datetime.now(timezone.utc)
    if work_time is not None:
        task.work_time = work_time
    if not task.started_at:
        task.started_at = now

    if len(submitted_ids) >= need:
        task.status = TaskStatus.SUBMITTED
        task.submitted_at = now
        fully = True
    else:
        # Keep annotating so remaining co-assignees can submit
        if task.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.REJECTED):
            task.status = TaskStatus.ANNOTATING
        elif task.status == TaskStatus.SUBMITTED:
            pass
        else:
            task.status = TaskStatus.ANNOTATING
        fully = False

    return {
        "fully_submitted": fully,
        "done": len(submitted_ids),
        "need": need,
        "submitted_annotator_ids": submitted_ids,
        "task_status": task.status.value if hasattr(task.status, "value") else str(task.status),
    }


def maybe_auto_approve_on_agreement(db: Session, task: Task) -> Dict[str, Any]:
    """
    quality_config.auto_approve_on_agreement=true 且交叉人数≥2、一致率≥min_agreement 时自动 APPROVED。
    """
    project = task.project
    if not project:
        return {"auto_approved": False}
    qc = project.quality_config if isinstance(project.quality_config, dict) else {}
    if not qc.get("auto_approve_on_agreement"):
        return {"auto_approved": False}
    need = required_annotator_count(task)
    if need < 2:
        return {"auto_approved": False, "reason": "cross_validate_count < 2"}

    try:
        threshold = float(qc.get("min_agreement") if qc.get("min_agreement") is not None else 0.8)
    except (TypeError, ValueError):
        threshold = 0.8

    from app.services.consensus import latest_annotations, set_canonical
    from app.services.quality_control import QualityControlService

    result = QualityControlService(db).calculate_cross_validation(task.id)
    if not result:
        return {"auto_approved": False, "reason": "no_agreement"}
    if result.agreement_rate < threshold:
        return {
            "auto_approved": False,
            "agreement_rate": result.agreement_rate,
            "threshold": threshold,
        }

    versions = latest_annotations(task)
    if versions:
        set_canonical(db, task, versions[0].id)
    task.status = TaskStatus.APPROVED
    task.completed_at = datetime.now(timezone.utc)
    meta = task_meta(task)
    meta["auto_approved"] = True
    meta["auto_approved_agreement"] = result.agreement_rate
    meta["auto_approved_at"] = datetime.now(timezone.utc).isoformat()
    task.task_metadata = meta
    return {
        "auto_approved": True,
        "agreement_rate": result.agreement_rate,
        "threshold": threshold,
        "task_status": "approved",
    }


def after_annotation_submit(
    db: Session,
    task: Task,
    user_id: int,
    annotation_data: Optional[Dict[str, Any]] = None,
    *,
    work_time: int | None = None,
) -> Dict[str, Any]:
    """提交门闩 + 黄金题静默评分 + 可选一致率自动过审。"""
    from app.services.golden_blind import record_golden_match

    progress = apply_cross_submit_gate(db, task, user_id, work_time=work_time)
    matched = record_golden_match(db, task, user_id, annotation_data)
    if matched is not None:
        progress["golden_matched"] = matched
    if progress.get("fully_submitted"):
        auto = maybe_auto_approve_on_agreement(db, task)
        progress.update(auto)
        if auto.get("auto_approved"):
            progress["task_status"] = "approved"
        try:
            from app.services.webhooks import emit_for_task

            emit_for_task(db, task, "task.submitted")
        except Exception:
            pass
    return progress
