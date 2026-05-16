"""
任务标注草稿 API（保存标注过程）
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.annotation_draft import AnnotationDraft
from app.models.user import User
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter()


class AnnotationDraftPayload(BaseModel):
    """与前端会话结构兼容的任意 JSON 对象"""

    payload: Dict[str, Any] = Field(default_factory=dict)


class AnnotationDraftResponse(BaseModel):
    task_id: int
    user_id: int
    payload: Dict[str, Any]
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/tasks/{task_id}/annotation-draft", response_model=AnnotationDraftResponse)
def get_annotation_draft(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问该任务草稿")

    row = (
        db.query(AnnotationDraft)
        .filter(AnnotationDraft.task_id == task_id, AnnotationDraft.user_id == current_user.id)
        .first()
    )
    if not row:
        return AnnotationDraftResponse(task_id=task_id, user_id=current_user.id, payload={}, updated_at=None)
    return AnnotationDraftResponse(
        task_id=task_id,
        user_id=current_user.id,
        payload=row.payload or {},
        updated_at=row.updated_at,
    )


@router.put("/tasks/{task_id}/annotation-draft", response_model=AnnotationDraftResponse)
def put_annotation_draft(
    task_id: int,
    body: AnnotationDraftPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权保存该任务草稿")

    row = (
        db.query(AnnotationDraft)
        .filter(AnnotationDraft.task_id == task_id, AnnotationDraft.user_id == current_user.id)
        .first()
    )
    if not row:
        row = AnnotationDraft(task_id=task_id, user_id=current_user.id, payload=body.payload)
        db.add(row)
    else:
        row.payload = body.payload
    db.commit()
    db.refresh(row)
    return AnnotationDraftResponse(
        task_id=task_id,
        user_id=current_user.id,
        payload=row.payload,
        updated_at=row.updated_at,
    )
