"""文本 / 语音 / 视频标注工作区 API"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.modality_workspace import get_workspace, save_workspace, submit_workspace
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter(tags=["多模态标注"])


class ModalityPayloadBody(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class ModalitySubmitBody(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)
    work_time: int = Field(0, ge=0)


@router.get("/tasks/{task_id}/modality/workspace")
def read_modality_workspace(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问该任务")
    from app.services.golden_blind import maybe_attach_golden_fields

    ws = get_workspace(db, task, current_user)
    return maybe_attach_golden_fields(db, task, current_user, ws)


@router.put("/tasks/{task_id}/modality/workspace")
def write_modality_workspace(
    task_id: int,
    body: ModalityPayloadBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权保存")
    row = save_workspace(db, task, current_user, body.payload)
    return {
        "task_id": task_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.post("/tasks/{task_id}/modality/submit")
def submit_modality_workspace(
    task_id: int,
    body: ModalitySubmitBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权提交")
    ann = submit_workspace(db, task, current_user, body.payload, body.work_time)
    db.refresh(task)
    from app.services.project_acl import cross_submit_progress

    progress = cross_submit_progress(task)
    status_val = task.status.value if hasattr(task.status, "value") else str(task.status)
    fully = status_val == "submitted"
    return {
        "message": "标注已提交" if fully else f"已提交（交叉 {progress['done']}/{progress['need']}）",
        "annotation_id": ann.id,
        "task_id": task_id,
        "task_status": status_val,
        "submit_progress": {"done": progress["done"], "need": progress["need"]},
    }
