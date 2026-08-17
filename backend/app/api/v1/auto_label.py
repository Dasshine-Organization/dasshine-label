"""
自动标注API
"""

from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, get_current_admin
from app.services.auto_label import AutoLabelService, get_auto_label_service

router = APIRouter()


class AutoLabelRequest(BaseModel):
    project_id: int
    batch_size: int = 100


class AutoLabelResponse(BaseModel):
    success: bool
    processed: int
    high_confidence: int
    low_confidence: int
    failed: int


@router.post("/auto-label/process/{task_id}")
async def process_single_task(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    对单个任务执行自动标注（LLM/OCR 路径）。

    注：2D 图像预标注请使用 /tasks/{id}/prelabel/*（demo_template / YOLO）。
    """
    from fastapi import HTTPException

    service = get_auto_label_service(db)
    try:
        result = await service.process_task(task_id)
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501,
            detail=f"该自动标注路径未启用：{e}。2D 图像请使用预标注 API /tasks/{{id}}/prelabel/run",
        ) from e

    if not result:
        return {
            "success": False,
            "message": "自动标注失败，请检查任务是否存在或项目是否启用自动标注",
        }

    return {
        "success": True,
        "task_id": task_id,
        "confidence": result.overall_confidence,
        "model": result.model,
        "processing_time": result.processing_time,
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
        "high_confidence": result.overall_confidence >= 0.8,
    }


@router.post("/auto-label/batch", response_model=AutoLabelResponse)
async def batch_process(
    request: AutoLabelRequest,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """批量自动标注（LLM/OCR 未接入时返回 501）。"""
    from fastapi import HTTPException

    service = get_auto_label_service(db)
    try:
        stats = await service.batch_process(request.project_id, request.batch_size)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e)) from e

    return AutoLabelResponse(
        success=True,
        processed=stats['processed'],
        high_confidence=stats.get('high_confidence', 0),
        low_confidence=stats['success'] - stats.get('high_confidence', 0),
        failed=stats['failed']
    )


@router.get("/auto-label/status/{project_id}")
def get_auto_label_status(
    project_id: int,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    获取项目自动标注状态
    
    统计已标注、高置信度、低置信度任务数量
    """
    from sqlalchemy import func
    from app.models.task import Task
    from app.models.project import Project
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "项目不存在"}
    
    # 统计各状态任务数
    total_tasks = db.query(Task).filter(Task.project_id == project_id).count()
    
    prelabeled_tasks = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence.isnot(None)
    ).count()
    
    high_confidence = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence >= 0.8
    ).count()
    
    low_confidence = db.query(Task).filter(
        Task.project_id == project_id,
        Task.pre_label_confidence < 0.8,
        Task.pre_label_confidence.isnot(None)
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
        "high_confidence_rate": round(high_confidence / prelabeled_tasks * 100, 2) if prelabeled_tasks > 0 else 0
    }


@router.post("/auto-label/enable/{project_id}")
def enable_auto_label(
    project_id: int,
    model: Optional[str] = "default",
    threshold: float = 0.8,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    启用项目的自动标注功能
    
    Args:
        model: 使用的模型（default/gpt-4/claude等）
        threshold: 置信度阈值
    """
    from app.models.project import Project
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "项目不存在"}
    
    project.auto_label_enabled = True
    project.auto_label_model = model
    project.auto_label_threshold = threshold
    db.commit()
    
    return {
        "success": True,
        "message": f"项目 '{project.name}' 已启用自动标注",
        "model": model,
        "threshold": threshold
    }


@router.post("/auto-label/disable/{project_id}")
def disable_auto_label(
    project_id: int,
    current_user = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """禁用项目的自动标注功能"""
    from app.models.project import Project
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return {"error": "项目不存在"}
    
    project.auto_label_enabled = False
    db.commit()
    
    return {
        "success": True,
        "message": f"项目 '{project.name}' 已禁用自动标注"
    }
