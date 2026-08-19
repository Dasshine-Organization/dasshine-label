"""项目管理 API"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin as require_admin
from app.api.deps import get_current_user, get_db
from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User
from sqlalchemy.orm import joinedload
from app.schemas.project_schemas import (
    AddMemberRequest,
    DispatchRequest,
    DispatchResult,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.project_acl import can_administrate_project, can_review_project
from app.services.project_service import (
    ProjectService,
    _get_schema,
    _resolve_project_ann_type,
    _resolve_project_category,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_summary(p: Project, db: Session) -> dict:
    schema = _get_schema(p)
    member_count = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).count()
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    type_val = p.type.value if hasattr(p.type, "value") else str(p.type or "")
    return {
        "id": p.id,
        "name": p.name,
        "cover_color": schema.get("cover_color", "#00d4ff"),
        "category": _resolve_project_category(p) or None,
        "ann_type": _resolve_project_ann_type(p) or None,
        "type": type_val,
        "status": status_val,
        "total_items": p.total_items or 0,
        "approved_items": p.approved_items or 0,
        "price_per_task": schema.get("price_per_task", 0.1),
        "cross_validate_count": schema.get("cross_validate_count", 1),
        "member_count": member_count,
        "organization_id": getattr(p, "organization_id", None),
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
        "category": _resolve_project_category(p) or None,
        "ann_type": _resolve_project_ann_type(p) or None,
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
        "organization_id": getattr(p, "organization_id", None),
        "created_at": p.created_at,
    }


def _meta_categories() -> list:
    """与工作台工具对齐：能选的类型必须能标。lane_3d 无 3D 折线工具，不开放。"""
    return [
        {
            "id": "image_2d",
            "label": "图像 2D",
            "icon": "image",
            "color": "#00d4ff",
            "types": [
                {"id": "bbox_2d", "label": "矩形框", "desc": "目标检测"},
                {"id": "polygon", "label": "多边形", "desc": "实例轮廓"},
                {"id": "polyline", "label": "折线", "desc": "车道线/骨架"},
                {"id": "keypoint", "label": "关键点", "desc": "姿态 · 可插 COCO-17"},
                {"id": "segmentation", "label": "语义分割", "desc": "像素画笔"},
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
                {"id": "lidar_seg", "label": "点云分割", "desc": "逐点语义刷"},
            ],
        },
        {
            "id": "video",
            "label": "视频",
            "icon": "video",
            "color": "#f59e0b",
            "types": [
                {"id": "video_tracking", "label": "目标追踪", "desc": "帧上画框 + track_id + 插值"},
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
                {"id": "tts_label", "label": "语音质量", "desc": "TTS MOS"},
            ],
        },
        {
            "id": "nlp",
            "label": "语料",
            "icon": "text",
            "color": "#ec4899",
            "types": [
                {"id": "ner", "label": "命名实体识别", "desc": "NER"},
                {"id": "re", "label": "关系抽取", "desc": "实体关系"},
                {"id": "sentiment", "label": "情感分析", "desc": "情感极性"},
                {"id": "text_classify", "label": "文本分类", "desc": "多标签"},
                {"id": "qa_pair", "label": "问答对", "desc": "SFT"},
                {"id": "summarization", "label": "摘要", "desc": "文本压缩"},
                {"id": "translation", "label": "翻译", "desc": "双语对齐"},
            ],
        },
        {
            "id": "embodied",
            "label": "具身机器人",
            "icon": "robot",
            "color": "#f97316",
            "types": [
                {"id": "robot_traj", "label": "轨迹标注", "desc": "运动路径"},
                {"id": "robot_action", "label": "动作序列", "desc": "操作步骤"},
                {"id": "robot_grasp", "label": "抓取标注", "desc": "抓取点/姿态"},
                {"id": "robot_scene", "label": "场景理解", "desc": "空间关系"},
            ],
        },
        {
            "id": "ocr",
            "label": "OCR",
            "icon": "scan",
            "color": "#06b6d4",
            "types": [
                {"id": "ocr_text", "label": "文字检测识别", "desc": "端到端 OCR"},
                {"id": "ocr_layout", "label": "版面分析", "desc": "区域分类"},
                {"id": "ocr_table", "label": "表格识别", "desc": "行列单元格"},
            ],
        },
        {
            "id": "multimodal",
            "label": "多模态",
            "icon": "layers",
            "color": "#8b5cf6",
            "types": [
                {"id": "image_caption", "label": "图文描述", "desc": "Caption"},
                {"id": "vqa", "label": "视觉问答", "desc": "VQA"},
                {"id": "rlhf", "label": "RLHF 偏好", "desc": "成对回复选择"},
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
    try:
        project = ProjectService(db).create(payload, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return _to_out(project)


@router.get("")
def list_projects(
    skip: int = 0,
    limit: int = Query(50, le=200),
    status: Optional[str] = None,
    category: Optional[str] = None,
    org_id: Optional[int] = Query(None, description="按组织过滤；默认当前 active_org"),
    my_projects: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.organization_service import OrganizationService

    org_svc = OrganizationService(db)
    effective_org = org_id
    if effective_org is None:
        org_svc.ensure_personal_org(current_user)
        if current_user.is_admin:
            # 超管：有当前组织则按组织筛；无则看全部
            effective_org = current_user.active_org_id
        else:
            effective_org = current_user.active_org_id

    user_id = current_user.id if (my_projects or not current_user.is_admin) else None
    projects = ProjectService(db).list_all(
        skip=skip,
        limit=limit,
        status=status,
        category=category,
        user_id=user_id,
        org_id=effective_org,
    )
    return [_to_summary(p, db) for p in projects]


@router.get("/{project_id}/tasks")
def list_project_tasks(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出项目下已导入的任务（含预览 URL）"""
    from app.services.org_scope import user_can_access_org_project
    from app.services.project_service import _get_schema
    from app.services.task_serializer import task_list_item

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user_can_access_org_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权查看该项目")

    query = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .filter(Task.project_id == project_id)
    )
    if status:
        query = query.filter(Task.status == status)

    total = query.count()
    tasks = (
        query.order_by(Task.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    schema = _get_schema(project)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [task_list_item(t, schema) for t in tasks],
    }


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_scope import user_can_access_org_project

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user_can_access_org_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权查看该项目")
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
    try:
        updated = ProjectService(db).update(project_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_out(updated)


@router.post("/{project_id}/archive")
def archive_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档项目（只读保留，可恢复）"""
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权归档项目")
    try:
        updated = ProjectService(db).archive(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "项目已归档", "project": _to_out(updated)}


@router.post("/{project_id}/restore")
def restore_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从归档恢复项目"""
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权恢复项目")
    try:
        updated = ProjectService(db).restore(project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "项目已恢复", "project": _to_out(updated)}


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
    result = ProjectService(db).delete(project_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {
        "message": "删除成功",
        "deleted_tasks": result.get("deleted_tasks", 0),
    }


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


@router.get("/{project_id}/dispatch-logs")
def get_dispatch_logs(
    project_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分发可观测：最近分发批次日志。"""
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权查看分发日志")
    schema = _get_schema(project)
    logs = list(schema.get("dispatch_logs") or [])
    logs = logs[-limit:]
    logs.reverse()
    return {
        "project_id": project_id,
        "total": len(schema.get("dispatch_logs") or []),
        "logs": logs,
    }


@router.get("/{project_id}/stats")
def get_project_stats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    try:
        return ProjectService(db).get_stats(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{project_id}/analytics")
def get_project_analytics(
    project_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.project_analytics import get_project_analytics as analytics
    from app.services.project_acl import can_administrate_project, get_project_member

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    is_member = get_project_member(db, project_id, current_user.id) is not None
    if not (
        current_user.is_admin
        or can_administrate_project(db, project, current_user)
        or can_review_project(db, project, current_user)
        or is_member
    ):
        raise HTTPException(status_code=403, detail="无权查看分析")
    return analytics(db, project, days=days)


class ActiveLearningRelabel(BaseModel):
    task_ids: List[int] = Field(default_factory=list)


@router.get("/{project_id}/active-learning")
def get_active_learning_pool(
    project_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.active_learning import list_pool, pool_count, task_pool_item, _threshold
    from app.services.project_acl import can_administrate_project, get_project_member

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (
        current_user.is_admin
        or can_administrate_project(db, project, current_user)
        or get_project_member(db, project_id, current_user.id)
    ):
        raise HTTPException(status_code=403, detail="无权查看主动学习池")
    rows = list_pool(db, project_id, limit=limit)
    return {
        "project_id": project_id,
        "threshold": _threshold(project),
        "total": pool_count(db, project_id),
        "items": [task_pool_item(t) for t in rows],
    }


@router.post("/{project_id}/active-learning/sync")
def sync_active_learning_pool(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.active_learning import sync_pool
    from app.services.project_acl import can_administrate_project

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (current_user.is_admin or can_administrate_project(db, project, current_user)):
        raise HTTPException(status_code=403, detail="仅项目管理员可同步主动学习池")
    result = sync_pool(db, project)
    db.commit()
    return {"ok": True, **result}


@router.post("/{project_id}/active-learning/relabel")
def relabel_active_learning(
    project_id: int,
    body: ActiveLearningRelabel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.active_learning import promote_for_relabel
    from app.services.project_acl import can_administrate_project

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (current_user.is_admin or can_administrate_project(db, project, current_user)):
        raise HTTPException(status_code=403, detail="仅项目管理员可重标")
    n = promote_for_relabel(db, project_id, body.task_ids)
    db.commit()
    return {"ok": True, "promoted": n}


@router.get("/{project_id}/golden-tasks")
def list_golden_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """黄金题列表；答案仅审核/管理可见。"""
    from app.services.golden_blind import can_see_golden
    from app.services.project_acl import can_administrate_project, get_project_member

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    is_member = get_project_member(db, project_id, current_user.id) is not None
    if not (
        current_user.is_admin
        or can_administrate_project(db, project, current_user)
        or can_review_project(db, project, current_user)
        or is_member
    ):
        raise HTTPException(status_code=403, detail="无权查看")

    show_answer = can_review_project(db, project, current_user) or current_user.is_admin
    rows = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.is_golden.is_(True))
        .order_by(Task.id.desc())
        .limit(200)
        .all()
    )
    items = []
    for t in rows:
        ans = t.golden_answer if isinstance(t.golden_answer, dict) else None
        has_ans = bool(ans and (ans.get("data") or ans))
        row = {
            "id": t.id,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "is_golden": True,
            "has_golden_answer": has_ans,
            "data_url": t.data_url,
            "filename": (t.data or {}).get("filename") or (t.data or {}).get("file_name"),
        }
        if show_answer:
            row["golden_answer"] = ans
        items.append(row)
    return {"project_id": project_id, "total": len(items), "items": items}


@router.get("/{project_id}/quality-config")
def get_quality_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user) and not can_review_project(
        db, project, current_user
    ):
        raise HTTPException(status_code=403, detail="无权查看")
    return {"project_id": project_id, "quality_config": project.quality_config or {}}


@router.put("/{project_id}/quality-config")
def put_quality_config(
    project_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """合并更新 quality_config（如 golden_rotation / golden_ratio）。"""
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权修改")
    current = dict(project.quality_config or {})
    patch = body if isinstance(body, dict) else {}
    # 允许嵌套在 quality_config 键下
    if "quality_config" in patch and isinstance(patch["quality_config"], dict):
        patch = patch["quality_config"]
    current.update({k: v for k, v in patch.items() if k != "quality_config"})
    project.quality_config = current
    db.commit()
    return {"project_id": project_id, "quality_config": project.quality_config}


@router.get("/{project_id}/guidelines")
def get_guidelines(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.guidelines import guidelines_payload
    from app.services.project_acl import get_project_member

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    member = get_project_member(db, project.id, current_user.id)
    if not (
        member
        or can_administrate_project(db, project, current_user)
        or can_review_project(db, project, current_user)
        or project.created_by_id == current_user.id
        or current_user.is_admin
    ):
        has_task = (
            db.query(Task)
            .filter(Task.project_id == project_id, Task.assignee_id == current_user.id)
            .first()
        )
        if not has_task:
            raise HTTPException(status_code=403, detail="无权查看标注规范")
    return guidelines_payload(project, current_user, db)


@router.put("/{project_id}/guidelines")
def put_guidelines(
    project_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.guidelines import guidelines_payload, update_guidelines

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权编辑标注规范")
    md = str(
        body.get("guidelines_md")
        if body.get("guidelines_md") is not None
        else body.get("markdown") or ""
    )
    must = body.get("must_read")
    bump = bool(body.get("bump", True))
    update_guidelines(
        project,
        markdown=md,
        must_read=must if must is not None else None,
        bump=bump,
    )
    db.commit()
    return guidelines_payload(project, current_user, db)


@router.post("/{project_id}/guidelines/ack")
def ack_guidelines_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.guidelines import ack_guidelines

    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    ok, payload = ack_guidelines(db, project, current_user)
    if not ok:
        raise HTTPException(status_code=400, detail=payload.get("error") or "确认失败")
    db.commit()
    return {"success": True, **payload}


@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 项目成员或可管理者可查看
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == current_user.id)
        .first()
    )
    if not member and not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权查看成员")
    return ProjectService(db).get_members(project_id)


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
