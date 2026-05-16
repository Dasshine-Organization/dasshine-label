"""项目管理 API"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin as require_admin
from app.api.deps import get_current_user, get_db
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.schemas.project_schemas import (
    AddMemberRequest,
    DispatchRequest,
    DispatchResult,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.project_acl import can_administrate_project
from app.services.project_service import ProjectService, _get_schema

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(p: Project, db: Session) -> dict:
    schema = _get_schema(p)
    member_count = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).count()
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    return {
        "id": p.id,
        "name": p.name,
        "cover_color": schema.get("cover_color", "#00d4ff"),
        "category": schema.get("category"),
        "ann_type": schema.get("ann_type"),
        "status": status_val,
        "total_items": p.total_items or 0,
        "approved_items": p.approved_items or 0,
        "price_per_task": schema.get("price_per_task", 0.1),
        "member_count": member_count,
        "created_at": p.created_at,
    }


def _to_out(p: Project) -> dict:
    schema = _get_schema(p)
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "cover_color": schema.get("cover_color", "#00d4ff"),
        "category": schema.get("category"),
        "ann_type": schema.get("ann_type"),
        "status": status_val,
        "dispatch_strategy": schema.get("dispatch_strategy", "smart"),
        "tasks_per_annotator": schema.get("tasks_per_annotator", 10),
        "cross_validate_count": schema.get("cross_validate_count", 1),
        "price_per_task": schema.get("price_per_task", 0.1),
        "auto_label_enabled": p.auto_label_enabled or False,
        "auto_label_model": p.auto_label_model,
        "auto_label_threshold": p.auto_label_threshold or 0.8,
        "total_items": p.total_items or 0,
        "labeled_items": p.labeled_items or 0,
        "approved_items": p.approved_items or 0,
        "created_at": p.created_at,
    }


def _meta_categories() -> list:
    """与前端 CreateProjectModal fallback 对齐"""
    return [
        {
            "id": "image_2d",
            "label": "图像 2D",
            "icon": "image",
            "color": "#00d4ff",
            "types": [
                {"id": "bbox_2d", "label": "矩形框", "desc": "目标检测"},
                {"id": "polygon", "label": "多边形", "desc": "实例分割"},
                {"id": "classification", "label": "图像分类", "desc": "整图标签"},
            ],
        },
        {
            "id": "pointcloud_3d",
            "label": "3D 点云",
            "icon": "cube",
            "color": "#a78bfa",
            "types": [
                {"id": "bbox_3d", "label": "3D 包围盒", "desc": "自动驾驶检测"},
                {"id": "lidar_seg", "label": "点云分割", "desc": "语义分割"},
            ],
        },
        {
            "id": "video",
            "label": "视频",
            "icon": "video",
            "color": "#f59e0b",
            "types": [
                {"id": "video_tracking", "label": "目标追踪", "desc": "多帧 ID"},
                {"id": "video_action", "label": "动作识别", "desc": "时序片段"},
                {"id": "video_caption", "label": "视频描述", "desc": "字幕/描述"},
            ],
        },
        {
            "id": "audio",
            "label": "语音",
            "icon": "mic",
            "color": "#10b981",
            "types": [
                {"id": "asr", "label": "语音转写", "desc": "ASR"},
                {"id": "speaker_diarize", "label": "说话人分离", "desc": "多人对话"},
                {"id": "emotion_audio", "label": "情绪识别", "desc": "语音情感"},
            ],
        },
        {
            "id": "nlp",
            "label": "语料",
            "icon": "text",
            "color": "#ec4899",
            "types": [
                {"id": "ner", "label": "命名实体识别", "desc": "NER"},
                {"id": "sentiment", "label": "情感分析", "desc": "情感极性"},
                {"id": "text_classify", "label": "文本分类", "desc": "多标签"},
                {"id": "qa_pair", "label": "问答对", "desc": "SFT"},
            ],
        },
        {
            "id": "embodied",
            "label": "具身机器人",
            "icon": "robot",
            "color": "#f97316",
            "types": [{"id": "robot_action", "label": "动作序列", "desc": "操作步骤"}],
        },
        {
            "id": "ocr",
            "label": "OCR",
            "icon": "scan",
            "color": "#06b6d4",
            "types": [{"id": "ocr_text", "label": "文字检测识别", "desc": "OCR"}],
        },
        {
            "id": "multimodal",
            "label": "多模态",
            "icon": "layers",
            "color": "#8b5cf6",
            "types": [
                {"id": "image_caption", "label": "图文描述", "desc": "Caption"},
                {"id": "vqa", "label": "视觉问答", "desc": "VQA"},
            ],
        },
    ]


@router.get("/meta/types")
def get_project_meta_types():
    return {"categories": _meta_categories()}


@router.post("", status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).create(payload, current_user.id)
    return _to_out(project)


@router.get("")
def list_projects(
    skip: int = 0,
    limit: int = Query(50, le=200),
    status: Optional[str] = None,
    category: Optional[str] = None,
    my_projects: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id if (my_projects or not current_user.is_admin) else None
    projects = ProjectService(db).list_all(
        skip=skip, limit=limit, status=status, category=category, user_id=user_id
    )
    return [_to_summary(p, db) for p in projects]


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _to_out(project)


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权修改项目")
    updated = ProjectService(db).update(project_id, payload)
    return _to_out(updated)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权删除项目")
    ProjectService(db).delete(project_id)
    return {"message": "删除成功"}


@router.post("/{project_id}/dispatch", response_model=DispatchResult)
def dispatch_project(
    project_id: int,
    payload: DispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权分发任务")
    result = ProjectService(db).dispatch(project_id, payload, current_user.id)
    return DispatchResult(**result)


@router.post("/{project_id}/members")
def add_member(
    project_id: int,
    body: AddMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权添加成员")
    ok = ProjectService(db).add_member(project_id, body.user_id, body.role)
    if not ok:
        raise HTTPException(status_code=400, detail="添加成员失败")
    return {"message": "成员已添加"}


@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权移除成员")
    ProjectService(db).remove_member(project_id, user_id)
    return {"message": "成员已移除"}
