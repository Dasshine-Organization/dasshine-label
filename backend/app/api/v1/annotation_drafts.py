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
from app.services.image_annotation import (
    submit_image_annotation,
    submit_pointcloud_annotation,
    touch_task_on_draft,
)
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter()


class ImageSubmitBody(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    work_time: int = Field(0, ge=0)


class AnnotationDraftPayload(BaseModel):
    """与前端会话结构兼容的任意 JSON 对象"""

    payload: Dict[str, Any] = Field(default_factory=dict)


class AnnotationDraftResponse(BaseModel):
    task_id: int
    user_id: int
    payload: Dict[str, Any]
    updated_at: Optional[datetime] = None
    task_status: Optional[str] = None

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

    task_status = touch_task_on_draft(db, task, current_user, body.payload)

    return AnnotationDraftResponse(
        task_id=task_id,
        user_id=current_user.id,
        payload=row.payload,
        updated_at=row.updated_at,
        task_status=task_status,
    )


@router.post("/tasks/{task_id}/image/submit")
def submit_image_task(
    task_id: int,
    body: ImageSubmitBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交 2D 图像标注（项目成员可直接提交，无需先走领取流程）。"""
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        ann = submit_image_annotation(db, task, current_user, body.payload, body.work_time)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    status_val = task.status.value if hasattr(task.status, "value") else str(task.status)
    return {
        "message": "标注已提交",
        "annotation_id": ann.id,
        "task_id": task_id,
        "task_status": status_val,
    }


@router.post("/tasks/{task_id}/pointcloud/submit")
def submit_pointcloud_task(
    task_id: int,
    body: ImageSubmitBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交 3D 点云标注（项目成员可直接提交）。"""
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        ann = submit_pointcloud_annotation(db, task, current_user, body.payload, body.work_time)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    status_val = task.status.value if hasattr(task.status, "value") else str(task.status)
    return {
        "message": "标注已提交",
        "annotation_id": ann.id,
        "task_id": task_id,
        "task_status": status_val,
    }
