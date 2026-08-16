"""
共识裁决：选定 canonical 标注作为导出/审核真源。
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.annotation import Annotation
from app.models.task import Task


def latest_annotations(task: Task) -> List[Annotation]:
    anns = [a for a in (task.annotations or []) if getattr(a, "is_latest", True)]
    anns.sort(
        key=lambda a: (a.updated_at or a.created_at or 0),
        reverse=True,
    )
    return anns


def resolve_canonical_annotation(
    task: Task, db: Optional[Session] = None
) -> Optional[Annotation]:
    """优先 tasks.canonical_annotation_id，否则退回最新 is_latest。"""
    cid = getattr(task, "canonical_annotation_id", None)
    if cid:
        for a in task.annotations or []:
            if a.id == cid:
                return a
        if db is not None:
            row = db.query(Annotation).filter(Annotation.id == cid).first()
            if row and row.task_id == task.id:
                return row
    anns = latest_annotations(task)
    return anns[0] if anns else None


def set_canonical(db: Session, task: Task, annotation_id: str) -> bool:
    ann = (
        db.query(Annotation)
        .filter(Annotation.id == annotation_id, Annotation.task_id == task.id)
        .first()
    )
    if not ann:
        return False
    task.canonical_annotation_id = annotation_id
    db.flush()
    return True
