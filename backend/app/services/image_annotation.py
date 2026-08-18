"""
2D 图像标注：草稿保存时更新任务状态、提交最终结果。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.annotation import Annotation, AnnotationStatus, AnnotationType
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.project_acl import can_access_task_workspace
from app.services.project_service import _get_schema


def _frames_have_labels(payload: Dict[str, Any]) -> bool:
    frames = payload.get("frames") or {}
    if not isinstance(frames, dict):
        return False
    for anns in frames.values():
        if isinstance(anns, list) and len(anns) > 0:
            return True
    return False


def _boxes3d_have_labels(payload: Dict[str, Any]) -> bool:
    boxes = payload.get("boxes3d")
    return isinstance(boxes, list) and len(boxes) > 0


def _payload_has_work(payload: Dict[str, Any]) -> bool:
    labels = payload.get("classificationLabels") or payload.get("classification_labels")
    if isinstance(labels, list) and len(labels) > 0:
        return True
    pixels = payload.get("pixelLabels")
    if isinstance(pixels, dict) and len(pixels) > 0:
        return True
    points = payload.get("pointLabels")
    if isinstance(points, dict) and len(points) > 0:
        return True
    return _frames_have_labels(payload) or _boxes3d_have_labels(payload)


def ensure_task_assignee(db: Session, task: Task, user: User) -> None:
    """项目成员打开任务时自动领取（待分配且无受让人）。"""
    if task.assignee_id is not None:
        return
    if task.status not in (TaskStatus.PENDING,):
        return
    if not can_access_task_workspace(db, task, user):
        return
    now = datetime.now(timezone.utc)
    task.assignee_id = user.id
    task.status = TaskStatus.ASSIGNED
    task.assigned_at = now
    db.commit()
    db.refresh(task)


def touch_task_on_draft(db: Session, task: Task, user: User, payload: Dict[str, Any]) -> str:
    """
    保存草稿后同步任务状态。
    有标注内容时标记为 annotating。
    返回当前任务 status 字符串。
    """
    if not can_access_task_workspace(db, task, user):
        return task.status.value if hasattr(task.status, "value") else str(task.status)

    ensure_task_assignee(db, task, user)

    from app.services.project_acl import is_task_assignee

    if is_task_assignee(task, user) and _payload_has_work(payload):
        if task.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED):
            task.status = TaskStatus.ANNOTATING
            if not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(task)

    return task.status.value if hasattr(task.status, "value") else str(task.status)


def submit_image_annotation(
    db: Session, task: Task, user: User, payload: Dict[str, Any], work_time: int
) -> Annotation:
    if not can_access_task_workspace(db, task, user):
        raise PermissionError("无权提交该任务")

    ensure_task_assignee(db, task, user)

    schema = _get_schema(task.project)
    ann_type = schema.get("ann_type", "bbox_2d")
    export_doc = {
        "schema": "dasshine.image_export.v1",
        "task_id": task.id,
        "ann_type": ann_type,
        "session": payload,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task.id,
            Annotation.annotator_id == user.id,
            Annotation.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        existing.data = export_doc
        existing.work_time = work_time
        existing.version += 1
        ann = existing
    else:
        ann = Annotation(
            id=str(uuid.uuid4()),
            task_id=task.id,
            data_id=str(task.id),
            annotation_type=AnnotationType.BOUNDING_BOX,
            data=export_doc,
            status=AnnotationStatus.COMPLETED,
            annotator_id=user.id,
            work_time=work_time,
            is_latest=True,
        )
        db.add(ann)

    now = datetime.now(timezone.utc)
    from app.services.task_completion import after_annotation_submit

    after_annotation_submit(db, task, user.id, export_doc, work_time=work_time)
    if not task.started_at:
        task.started_at = now
    db.commit()
    db.refresh(ann)
    db.refresh(task)
    return ann


def submit_pointcloud_annotation(
    db: Session, task: Task, user: User, payload: Dict[str, Any], work_time: int
) -> Annotation:
    if not can_access_task_workspace(db, task, user):
        raise PermissionError("无权提交该任务")

    ensure_task_assignee(db, task, user)

    schema = _get_schema(task.project)
    ann_type = schema.get("ann_type", "bbox_3d")
    export_doc = {
        "schema": "dasshine.pointcloud_export.v1",
        "task_id": task.id,
        "ann_type": ann_type,
        "session": payload,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task.id,
            Annotation.annotator_id == user.id,
            Annotation.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        existing.data = export_doc
        existing.work_time = work_time
        existing.version += 1
        existing.annotation_type = AnnotationType.CUBOID_3D
        ann = existing
    else:
        ann = Annotation(
            id=str(uuid.uuid4()),
            task_id=task.id,
            data_id=str(task.id),
            annotation_type=AnnotationType.CUBOID_3D,
            data=export_doc,
            status=AnnotationStatus.COMPLETED,
            annotator_id=user.id,
            work_time=work_time,
            is_latest=True,
        )
        db.add(ann)

    now = datetime.now(timezone.utc)
    from app.services.task_completion import after_annotation_submit

    after_annotation_submit(db, task, user.id, export_doc, work_time=work_time)
    if not task.started_at:
        task.started_at = now
    db.commit()
    db.refresh(ann)
    db.refresh(task)
    return ann
