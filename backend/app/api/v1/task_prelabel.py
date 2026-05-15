"""
2D 图像任务：预标注模型列表、加载登记、执行预标注（与前端「先加载模型再预标注」对齐）。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.project import ProjectType
from app.models.user import User
from app.services.project_acl import can_access_task_workspace, get_task_and_project

router = APIRouter()

# 与前端 PRELABEL_MODELS 对齐；后续可改为读配置或模型注册表
PRELABEL_MODEL_REGISTRY: List[Dict[str, Any]] = [
    {"id": "yolov8_coco", "label": "YOLOv8 · COCO 检测", "kind": "supervised"},
    {"id": "sam_vit_h", "label": "SAM · 无监督分割", "kind": "unsupervised"},
    {"id": "clip_cluster", "label": "CLIP · 无监督聚类", "kind": "unsupervised"},
    {"id": "detr_generic", "label": "DETR · 通用检测", "kind": "supervised"},
]

META_LOADED_MODEL = "loaded_prelabel_model_id"


class PrelabelRegisterBody(BaseModel):
    model_id: str = Field(..., min_length=1)


class PrelabelRunBody(BaseModel):
    model_id: Optional[str] = None
    frame_index: int = Field(0, ge=0, description="当前帧索引，用于演示多帧")


@router.get("/prelabel-models")
def list_prelabel_models(
    current_user: User = Depends(get_current_user),
):
    """列出可选预标注 / 无监督模型"""
    return {"models": PRELABEL_MODEL_REGISTRY}


@router.post("/tasks/{task_id}/prelabel/load")
def register_prelabel_model(
    task_id: int,
    body: PrelabelRegisterBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """登记当前任务要使用的预标注模型（写入任务 metadata）"""
    task, project = get_task_and_project(db, task_id)
    if not task or not project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")

    valid_ids = {m["id"] for m in PRELABEL_MODEL_REGISTRY}
    if body.model_id not in valid_ids:
        raise HTTPException(status_code=400, detail="未知的模型 ID")

    meta = dict(task.task_metadata or {})
    meta[META_LOADED_MODEL] = body.model_id
    meta["loaded_prelabel_model_at"] = time.time()
    task.task_metadata = meta
    db.commit()
    return {"success": True, "model_id": body.model_id}


@router.post("/tasks/{task_id}/prelabel/run")
def run_task_prelabel(
    task_id: int,
    body: PrelabelRunBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    执行预标注：必须先 load 登记模型，或通过 body.model_id 显式指定（与前端一致时仍以已登记为准）。
    返回 2D 候选框列表（演示数据），写入 task.pre_label_result。
    """
    task, project = get_task_and_project(db, task_id)
    if not task or not project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权操作该任务")

    meta = dict(task.task_metadata or {})
    model_id = body.model_id or meta.get(META_LOADED_MODEL)
    if not model_id:
        raise HTTPException(status_code=400, detail="请先加载预标注模型（POST .../prelabel/load）")

    valid_ids = {m["id"] for m in PRELABEL_MODEL_REGISTRY}
    if model_id not in valid_ids:
        raise HTTPException(status_code=400, detail="未知的模型 ID")

    # 仅图像类项目做 2D 框演示；其它类型返回提示
    if project.type not in (
        ProjectType.OBJECT_DETECTION,
        ProjectType.IMAGE_SEGMENTATION,
        ProjectType.IMAGE_CLASSIFICATION,
        ProjectType.MULTIMODAL,
    ):
        raise HTTPException(status_code=400, detail="当前项目类型不支持 2D 图像预标注演示")

    fi = body.frame_index
    templates: List[List[Dict[str, Any]]] = [
        [
            {"label": "car", "color": "#00d4ff", "points": [{"x": 120, "y": 200}, {"x": 360, "y": 380}], "score": 0.94},
            {"label": "person", "color": "#7c3aed", "points": [{"x": 440, "y": 120}, {"x": 510, "y": 310}], "score": 0.88},
        ],
        [
            {"label": "person", "color": "#7c3aed", "points": [{"x": 80, "y": 150}, {"x": 160, "y": 350}], "score": 0.82},
            {"label": "car", "color": "#00d4ff", "points": [{"x": 300, "y": 240}, {"x": 550, "y": 400}], "score": 0.95},
        ],
    ]
    tpl = templates[fi % len(templates)]
    annotations2d = [
        {
            "id": str(uuid.uuid4()),
            "type": "bbox",
            "label": b["label"],
            "color": b["color"],
            "points": b["points"],
            "visible": True,
            "locked": False,
            "score": b["score"],
            "isAI": True,
        }
        for b in tpl
    ]
    overall = sum(float(b["score"]) for b in tpl) / max(len(tpl), 1)
    task.pre_label_result = {
        "model_id": model_id,
        "frame_index": fi,
        "annotations2d": annotations2d,
        "generated_at": time.time(),
    }
    task.pre_label_confidence = overall
    db.commit()

    return {
        "success": True,
        "task_id": task_id,
        "model_id": model_id,
        "confidence": overall,
        "annotations2d": annotations2d,
    }
