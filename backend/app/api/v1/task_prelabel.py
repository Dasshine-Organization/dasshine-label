"""
2D 图像任务：预标注模型注册表、加载、推理（本地 / 云服务 / HTTP）
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.project import ProjectType
from app.models.user import User
from app.services.prelabel.manager import (
    get_loaded_model_id,
    list_models_with_status,
    load_model,
    run_prelabel,
    unload_model,
)
from app.services.prelabel.registry import get_descriptor, probe_availability
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter()

META_LOADED_MODEL = "loaded_prelabel_model_id"


class _PrelabelBodyBase(BaseModel):
    """允许 model_id 字段（Pydantic 默认保护 model_ 命名空间）"""
    model_config = ConfigDict(protected_namespaces=())


class PrelabelRegisterBody(_PrelabelBodyBase):
    model_id: str = Field(..., min_length=1)


class PrelabelRunBody(_PrelabelBodyBase):
    model_id: Optional[str] = None
    frame_index: int = Field(0, ge=0, description="当前帧索引")
    image_url: Optional[str] = Field(None, description="待检测图片 URL，缺省用任务 data_url")


def _ensure_image_project(project) -> None:
    if project.type not in (
        ProjectType.OBJECT_DETECTION,
        ProjectType.IMAGE_SEGMENTATION,
        ProjectType.IMAGE_CLASSIFICATION,
        ProjectType.MULTIMODAL,
    ):
        raise HTTPException(status_code=400, detail="当前项目类型不支持 2D 图像预标注")


@router.get("/prelabel-models")
def list_prelabel_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出预标注模型及真实可用状态（配置探测 + 内存加载状态）"""
    loaded = get_loaded_model_id(current_user.id)
    return {"models": list_models_with_status(current_user.id, loaded)}


@router.get("/tasks/{task_id}/prelabel/status")
def task_prelabel_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问")

    meta = task.task_metadata or {}
    registered = meta.get(META_LOADED_MODEL)
    in_memory = get_loaded_model_id(current_user.id)
    model_id = in_memory or registered
    status_info: Optional[Dict[str, Any]] = None
    if model_id:
        avail, msg = probe_availability(model_id)
        desc = get_descriptor(model_id)
        status_info = {
            "model_id": model_id,
            "status": "loaded" if in_memory else avail.value,
            "status_message": msg,
            "label": desc.label if desc else model_id,
            "in_memory": bool(in_memory),
        }
    return {
        "task_id": task_id,
        "loaded_model": status_info,
        "models": list_models_with_status(current_user.id, model_id),
    }


@router.post("/tasks/{task_id}/prelabel/load")
def register_prelabel_model(
    task_id: int,
    body: PrelabelRegisterBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """加载预标注模型到服务端会话（本地权重 / 云 API 预热 / HTTP 校验）"""
    task, project = get_task_and_project(db, task_id)
    if not task or not project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")
    _ensure_image_project(project)

    try:
        result = load_model(current_user.id, body.model_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型加载失败: {e}") from e

    meta = dict(task.task_metadata or {})
    meta[META_LOADED_MODEL] = body.model_id
    meta["loaded_prelabel_model_at"] = time.time()
    meta["loaded_prelabel_provider"] = result.get("provider")
    task.task_metadata = meta
    db.commit()
    return result


@router.post("/tasks/{task_id}/prelabel/unload")
def unload_prelabel_model(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task, project = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")

    meta = dict(task.task_metadata or {})
    model_id = meta.get(META_LOADED_MODEL)
    if model_id:
        unload_model(current_user.id, model_id)
    meta.pop(META_LOADED_MODEL, None)
    task.task_metadata = meta
    db.commit()
    return {"success": True}


@router.post("/tasks/{task_id}/prelabel/run")
async def run_task_prelabel(
    task_id: int,
    body: PrelabelRunBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对当前图片执行预标注推理"""
    task, project = get_task_and_project(db, task_id)
    if not task or not project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")
    _ensure_image_project(project)

    meta = dict(task.task_metadata or {})
    model_id = body.model_id or meta.get(META_LOADED_MODEL) or get_loaded_model_id(current_user.id)
    if not model_id:
        raise HTTPException(status_code=400, detail="请先加载预标注模型")

    image_url = body.image_url or task.data_url
    if not image_url:
        data = task.data or {}
        image_url = data.get("image_url") or data.get("url")
    if not image_url:
        raise HTTPException(status_code=400, detail="缺少图片 URL，请传入 image_url 或配置任务 data_url")

    try:
        result = await run_prelabel(
            current_user.id, model_id, image_url, body.frame_index
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预标注推理失败: {e}") from e

    task.pre_label_result = {
        "model_id": result.model_id,
        "frame_index": body.frame_index,
        "annotations2d": result.annotations2d,
        "generated_at": time.time(),
        "inference_source": result.inference_source,
        "message": result.message,
    }
    task.pre_label_confidence = result.confidence
    db.commit()

    return {
        "success": True,
        "task_id": task_id,
        "model_id": result.model_id,
        "confidence": result.confidence,
        "annotations2d": result.annotations2d,
        "inference_source": result.inference_source,
        "message": result.message,
        "image_width": result.image_width,
        "image_height": result.image_height,
    }
