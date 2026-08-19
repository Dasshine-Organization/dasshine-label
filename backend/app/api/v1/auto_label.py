"""
自动标注 API：单任务写入草稿；批量优先入 Celery，broker 不可用时同步小批量兜底。
不再返回 501。
"""

from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user, get_db
from app.models.user import User
from app.services.auto_label import get_auto_label_service
from app.services.auto_label_adapters import (
    AutoLabelAdapterError,
    AutoLabelConfigError,
    AutoLabelUnsupportedError,
    adapter_status,
)
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter()
logger = logging.getLogger(__name__)


class AutoLabelRequest(BaseModel):
    project_id: int
    batch_size: int = Field(100, ge=1, le=500)


class AutoLabelResponse(BaseModel):
    success: bool
    processed: int
    high_confidence: int
    low_confidence: int
    failed: int
    queued: bool = False
    job_id: Optional[str] = None
    sync_fallback: bool = False
    errors: List[Dict[str, Any]] = Field(default_factory=list)


def _raise_auto_label(exc: Exception) -> None:
    if isinstance(exc, AutoLabelConfigError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if isinstance(exc, AutoLabelUnsupportedError):
        code = status.HTTP_404_NOT_FOUND if "不存在" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    if isinstance(exc, AutoLabelAdapterError):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    raise exc


@router.post("/auto-label/process/{task_id}")
def process_single_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对单个任务执行自动标注并写入当前用户草稿（LLM / Whisper / OCR / demo）。"""
    task, _project = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问该任务")

    service = get_auto_label_service(db)
    try:
        result = service.process_task(task_id, user_id=current_user.id)
    except (AutoLabelConfigError, AutoLabelUnsupportedError, AutoLabelAdapterError) as e:
        _raise_auto_label(e)

    return {
        "success": True,
        "task_id": task_id,
        "confidence": result.overall_confidence,
        "model": result.model,
        "adapter": result.adapter,
        "processing_time": result.processing_time,
        "draft_written": result.draft_written,
        "recommended": result.recommended,
        "needs_review": result.needs_review,
        "results": [
            {
                "label": r.label,
                "text": r.text,
                "start": r.start,
                "end": r.end,
                "confidence": r.confidence,
            }
            for r in result.results
        ],
        "high_confidence": result.recommended,
    }


@router.post("/auto-label/batch", response_model=AutoLabelResponse)
def batch_process(
    request: AutoLabelRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """批量预标注：优先 Celery；broker 不可用则同步处理最多 AUTO_LABEL_BATCH_SYNC_MAX 条。"""
    from app.models.project import Project
    from app.core.config import settings

    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        from app.tasks.auto_label_tasks import batch_auto_label_task

        async_result = batch_auto_label_task.delay(
            request.project_id, request.batch_size, current_user.id
        )
        return AutoLabelResponse(
            success=True,
            processed=0,
            high_confidence=0,
            low_confidence=0,
            failed=0,
            queued=True,
            job_id=str(async_result.id),
        )
    except Exception as exc:
        logger.warning("Celery 不可用，自动标注改为同步小批量: %s", exc)
        cap = min(request.batch_size, int(settings.AUTO_LABEL_BATCH_SYNC_MAX or 20))
        service = get_auto_label_service(db)
        try:
            stats = service.batch_process(request.project_id, cap, user_id=current_user.id)
        except (AutoLabelConfigError, AutoLabelUnsupportedError, AutoLabelAdapterError) as err:
            _raise_auto_label(err)
        return AutoLabelResponse(
            success=True,
            processed=stats["processed"],
            high_confidence=stats.get("high_confidence", 0),
            low_confidence=stats.get("low_confidence", 0),
            failed=stats["failed"],
            queued=False,
            sync_fallback=True,
            errors=stats.get("errors") or [],
        )


@router.get("/auto-label/status/{project_id}")
def get_auto_label_status(
    project_id: int,
    _current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.models.project import Project
    from app.models.task import Task

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    total_tasks = db.query(Task).filter(Task.project_id == project_id).count()
    prelabeled_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence.isnot(None),
    ).count()
    high_confidence = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence >= 0.8,
    ).count()
    low_confidence = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence < 0.8,
        Task.pre_label_confidence.isnot(None),
    ).count()

    return {
        "project_id": project_id,
        "project_name": project.name,
        "auto_label_enabled": project.auto_label_enabled,
        "total_tasks": total_tasks,
        "prelabeled_tasks": prelabeled_tasks,
        "high_confidence": high_confidence,
        "low_confidence": low_confidence,
        "pending_tasks": total_tasks - prelabeled_tasks,
        "high_confidence_rate": round(high_confidence / prelabeled_tasks * 100, 2)
        if prelabeled_tasks > 0
        else 0,
        "adapters": adapter_status(),
    }


@router.post("/auto-label/enable/{project_id}")
def enable_auto_label(
    project_id: int,
    model: Optional[str] = "default",
    threshold: float = 0.8,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.auto_label_enabled = True
    project.auto_label_model = model
    project.auto_label_threshold = threshold
    db.commit()

    return {
        "success": True,
        "message": f"项目 '{project.name}' 已启用自动标注",
        "model": model,
        "threshold": threshold,
        "adapters": adapter_status(),
    }


@router.post("/auto-label/disable/{project_id}")
def disable_auto_label(
    project_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.auto_label_enabled = False
    db.commit()

    return {
        "success": True,
        "message": f"项目 '{project.name}' 已禁用自动标注",
    }
