"""
质量控制 API：交叉验证、审核队列、专家审核。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin, get_current_user, get_db
from app.models.annotation import Annotation
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.project_acl import can_review_project
from app.services.project_service import _get_schema, _resolve_project_category

router = APIRouter()


class CrossValidationRequest(BaseModel):
    task_id: int


class CrossValidationResponse(BaseModel):
    task_id: int
    annotator_count: int
    agreement_rate: float
    kappa_score: float
    is_golden: bool
    golden_accuracy: Optional[float]


class QualityScoreResponse(BaseModel):
    user_id: int
    username: str
    accuracy: float
    consistency: float
    efficiency: float
    overall_score: float
    level: str
    suggested_level: str


class ReviewRequest(BaseModel):
    task_id: int
    decision: str = Field(..., pattern="^(approved|rejected)$")
    score: Optional[float] = Field(None, ge=0, le=100)
    feedback: Optional[str] = None
    # 多人共标通过时选定导出真源（annotation UUID）
    canonical_annotation_id: Optional[str] = None


class ReviewResponse(BaseModel):
    success: bool
    message: str
    task_id: int
    task_status: str


class InsertGoldenRequest(BaseModel):
    project_id: int
    ratio: float = 0.1


class GoldenAnswerUpdate(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)
    source: str = "expert"
    confidence: float = Field(1.0, ge=0, le=1)


class QualityReportResponse(BaseModel):
    project_id: int
    project_name: str
    total_tasks: int
    approved_tasks: int
    approval_rate: float
    cross_validated: int
    golden_tasks: int
    quality_score: float


def _latest_annotation(task: Task) -> Optional[Annotation]:
    from app.services.consensus import resolve_canonical_annotation

    return resolve_canonical_annotation(task)


def _version_payloads(db: Session, task: Task) -> List[Dict[str, Any]]:
    from app.models.user import User
    from app.services.consensus import latest_annotations
    from app.services.project_service import _get_schema, _resolve_project_category

    schema = _get_schema(task.project) if task.project else {}
    category = _resolve_project_category(task.project) if task.project else None
    canon = getattr(task, "canonical_annotation_id", None)
    out: List[Dict[str, Any]] = []
    for ann in latest_annotations(task):
        user = db.query(User).filter(User.id == ann.annotator_id).first() if ann.annotator_id else None
        emb = None
        if category == "embodied" or (
            isinstance(ann.data, dict)
            and str((ann.data or {}).get("schema") or "").startswith("dasshine.embodied")
        ):
            emb = _extract_embodied_preview(task, ann)
        mod = None if emb else _extract_modality_preview(ann, category, schema.get("ann_type"))
        pc = None
        if category == "pointcloud_3d" or (
            isinstance(ann.data, dict)
            and str((ann.data or {}).get("schema") or "").startswith("dasshine.pointcloud")
        ):
            pc = _extract_pointcloud_preview(task, ann)
        out.append(
            {
                "annotation_id": ann.id,
                "annotator_id": ann.annotator_id,
                "annotator_name": user.username if user else None,
                "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
                "work_time": ann.work_time,
                "annotations2d": _extract_preview_boxes(ann),
                "modality_preview": mod,
                "pointcloud_preview": pc,
                "embodied_preview": emb,
                "is_canonical": ann.id == canon,
            }
        )
    return out


def _extract_preview_boxes(ann: Optional[Annotation]) -> List[Dict[str, Any]]:
    if not ann or not isinstance(ann.data, dict):
        return []
    data = ann.data
    session = data.get("session") if isinstance(data.get("session"), dict) else data
    frames = session.get("frames") if isinstance(session, dict) else None
    boxes: List[Dict[str, Any]] = []
    if isinstance(frames, dict):
        # 优先第 0 帧，否则合并各帧（审核预览）
        ordered_keys = sorted(frames.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)
        for key in ordered_keys[:1] or list(frames.keys())[:1]:
            items = frames.get(key) or []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        boxes.append(item)
        return boxes
    raw = data.get("annotations2d") or data.get("bbox")
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    # OCR spans with bbox
    spans = data.get("spans")
    if isinstance(spans, list):
        for s in spans:
            if not isinstance(s, dict) or not s.get("bbox"):
                continue
            bbox = s["bbox"]
            boxes.append({
                "id": s.get("id"),
                "label": s.get("label") or s.get("text") or "text",
                "text": s.get("text"),
                "bbox": bbox,
                "xywh": bbox,
            })
    return boxes


def _extract_modality_preview(
    ann: Optional[Annotation],
    category: Optional[str],
    ann_type: Optional[str],
) -> Optional[Dict[str, Any]]:
    """NLP / 音频 / 视频 / OCR / 多模态审核摘要。"""
    if not ann or not isinstance(ann.data, dict):
        return None
    data = ann.data
    modality = str(data.get("modality") or "")
    if not modality:
        if category == "ocr" or (ann_type or "").startswith("ocr_"):
            modality = "ocr"
        elif category == "nlp":
            modality = "text"
        elif category in ("audio", "video", "multimodal"):
            modality = category
        elif data.get("spans") and data.get("bbox") is None:
            modality = "text"
        else:
            return None
    if modality == "text":
        spans = data.get("spans") if isinstance(data.get("spans"), list) else []
        return {
            "modality": "text",
            "spans": spans[:40],
            "classification_labels": data.get("classification_labels") or [],
            "sentiment": data.get("sentiment"),
            "summary": (data.get("summary") or "")[:400],
            "translation": (data.get("translation") or "")[:400],
            "qa_pairs": (data.get("qa_pairs") or [])[:5],
        }
    if modality == "ocr":
        spans = data.get("spans") if isinstance(data.get("spans"), list) else []
        return {
            "modality": "ocr",
            "spans": spans[:40],
            "span_count": len(spans),
        }
    if modality == "audio":
        return {
            "modality": "audio",
            "transcript": (data.get("transcript") or "")[:800],
            "speakers": data.get("speakers") or [],
            "segments": (data.get("segments") or [])[:30],
        }
    if modality == "video":
        return {
            "modality": "video",
            "caption": (data.get("caption") or "")[:400],
            "clips": (data.get("clips") or [])[:20],
            "frame_notes": data.get("frame_notes") or {},
        }
    if modality == "multimodal":
        return {
            "modality": "multimodal",
            "caption": (data.get("caption") or "")[:400],
            "vqa": data.get("vqa") or {},
        }
    return None


def _extract_pointcloud_preview(task: Task, ann: Optional[Annotation]) -> Optional[Dict[str, Any]]:
    """点云审核预览：点云 URL + boxes3d。"""
    data = task.data if isinstance(task.data, dict) else {}
    payload = ann.data if ann and isinstance(ann.data, dict) else {}
    session = payload.get("session") if isinstance(payload.get("session"), dict) else payload
    boxes = []
    if isinstance(session, dict):
        raw = session.get("boxes3d") or session.get("annotations_3d") or []
        if isinstance(raw, list):
            boxes = [b for b in raw if isinstance(b, dict)]
    url = task.data_url or data.get("point_cloud_url") or data.get("url")
    if not url and not boxes:
        return None
    return {
        "point_cloud_url": url,
        "boxes3d": boxes[:200],
        "box_count": len(boxes),
    }


def _extract_embodied_preview(task: Task, ann: Optional[Annotation]) -> Optional[Dict[str, Any]]:
    """具身审核预览：多路相机 + VLA 摘要。"""
    data = task.data if isinstance(task.data, dict) else {}
    ep = data.get("embodied_episode") if isinstance(data.get("embodied_episode"), dict) else {}
    payload = ann.data if ann and isinstance(ann.data, dict) else {}
    streams = payload.get("streams") or ep.get("streams") or []
    cams = []
    for s in streams:
        if isinstance(s, dict) and s.get("src"):
            cams.append({"id": s.get("id"), "label": s.get("label") or s.get("id"), "src": s.get("src")})
    if not cams and task.data_url:
        cams = [{"id": "main", "label": "main", "src": task.data_url}]
    if not cams and not payload.get("schema", "").startswith("dasshine.embodied"):
        # 非具身 annotation 且无 episode
        cat_hint = str(data.get("embodied_slug") or "")
        if not ep and not cat_hint:
            return None
    return {
        "instruction": payload.get("instruction") or (data.get("embodied_vla") or {}).get("instruction") or ep.get("instruction") or "",
        "success": payload.get("success") or (data.get("embodied_vla") or {}).get("success") or "unknown",
        "segments": payload.get("segments") or (data.get("embodied_vla") or {}).get("segments") or [],
        "grasps": payload.get("grasps") or (data.get("embodied_vla") or {}).get("grasps") or [],
        "trajectory_points": len(payload.get("trajectory") or (data.get("embodied_vla") or {}).get("trajectory") or []),
        "preferences": len(payload.get("preferences") or (data.get("embodied_vla") or {}).get("preferences") or []),
        "committed_frames": payload.get("committed_frames") or [],
        "joints_source": payload.get("joints_source"),
        "force_source": payload.get("force_source"),
        "tactile_source": payload.get("tactile_source"),
        "quality": _embodied_quality_preview(payload, data, ep),
        "streams": cams[:8],
        "fps": payload.get("fps") or ep.get("fps"),
        "total_frames": payload.get("frames") and len(payload.get("frames") or []) or ep.get("total_frames"),
    }


def _embodied_quality_preview(payload, data, ep):
    from app.services.embodied_quality import compute_embodied_quality

    vla = data.get("embodied_vla") if isinstance(data.get("embodied_vla"), dict) else {}
    return compute_embodied_quality(payload, vla=vla, episode=ep)


@router.post("/quality/cross-validation", response_model=CrossValidationResponse)
def calculate_cross_validation(
    request: CrossValidationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.quality_control import get_quality_service

    service = get_quality_service(db)
    result = service.calculate_cross_validation(request.task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务不存在或无足够标注")
    return result


@router.get("/quality/score/{user_id}", response_model=QualityScoreResponse)
def get_annotator_quality(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.quality_control import get_quality_service

    service = get_quality_service(db)
    score = service.calculate_annotator_quality(user_id)
    if not score:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "user_id": score.user_id,
        "username": score.username,
        "accuracy": score.accuracy,
        "consistency": score.consistency,
        "efficiency": score.efficiency,
        "overall_score": score.overall_score,
        "level": score.level.value if hasattr(score.level, "value") else str(score.level),
        "suggested_level": (
            score.suggested_level.value
            if hasattr(score.suggested_level, "value")
            else str(score.suggested_level)
        ),
    }


@router.get("/quality/queue")
def list_review_queue(
    project_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """待审核队列：submitted / reviewing（按当前组织收窄）。"""
    from app.models.project import Project
    from app.services.org_scope import ensure_active_org_id

    q = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee), joinedload(Task.annotations))
        .join(Project, Project.id == Task.project_id)
        .filter(Task.status.in_([TaskStatus.SUBMITTED, TaskStatus.REVIEWING]))
        .order_by(Task.submitted_at.desc(), Task.id.desc())
    )
    if project_id:
        q = q.filter(Task.project_id == project_id)

    active_org = ensure_active_org_id(db, current_user)
    if not current_user.is_admin:
        if active_org is None:
            return {"total": 0, "items": []}
        q = q.filter(Project.organization_id == active_org)
    elif active_org is not None:
        q = q.filter(Project.organization_id == active_org)

    rows = q.limit(limit * 3).all()  # 多取后按权限过滤
    items: List[Dict[str, Any]] = []
    for task in rows:
        project = task.project
        if not project or not can_review_project(db, project, current_user):
            continue
        schema = _get_schema(project)
        latest = _latest_annotation(task)
        items.append(
            {
                "id": task.id,
                "project_id": task.project_id,
                "project_name": project.name,
                "category": _resolve_project_category(project) or schema.get("category"),
                "ann_type": schema.get("ann_type"),
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "data_url": task.data_url,
                "filename": (task.data or {}).get("file_name")
                or (task.data or {}).get("filename")
                or None,
                "assignee_name": task.assignee.username if task.assignee else None,
                "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
                "box_count": len(_extract_preview_boxes(latest)),
                "modality": (latest.data or {}).get("modality") if latest and isinstance(latest.data, dict) else None,
            }
        )
        if len(items) >= limit:
            break

    return {"total": len(items), "items": items}


@router.get("/quality/tasks/{task_id}")
def get_review_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核详情：图片 URL + 最新提交标注预览。"""
    task = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee), joinedload(Task.annotations))
        .filter(Task.id == task_id)
        .first()
    )
    if not task or not task.project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_review_project(db, task.project, current_user):
        raise HTTPException(status_code=403, detail="无权审核该任务")

    latest = _latest_annotation(task)
    schema = _get_schema(task.project)
    data = task.data or {}
    category = _resolve_project_category(task.project) or schema.get("category")
    versions = _version_payloads(db, task)
    # 预览默认展示当前选中 canonical，否则第一份
    preview_ann = latest
    if versions:
        # 若前端尚未选 canonical，仍用 resolve；详情顶层字段与选中版本对齐
        pass
    embodied_preview = None
    if category == "embodied" or (
        isinstance(preview_ann.data if preview_ann else None, dict)
        and str((preview_ann.data or {}).get("schema") or "").startswith("dasshine.embodied")
    ):
        embodied_preview = _extract_embodied_preview(task, preview_ann)
    modality_preview = None
    if not embodied_preview:
        modality_preview = _extract_modality_preview(preview_ann, category, schema.get("ann_type"))
    pointcloud_preview = None
    if category == "pointcloud_3d" or (
        isinstance(preview_ann.data if preview_ann else None, dict)
        and str((preview_ann.data or {}).get("schema") or "").startswith("dasshine.pointcloud")
    ):
        pointcloud_preview = _extract_pointcloud_preview(task, preview_ann)
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project_name": task.project.name,
        "category": category,
        "ann_type": schema.get("ann_type"),
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        "data_url": task.data_url or data.get("image_url") or data.get("url"),
        "filename": data.get("file_name") or data.get("filename"),
        "width": data.get("width"),
        "height": data.get("height"),
        "assignee_name": task.assignee.username if task.assignee else None,
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "annotations2d": _extract_preview_boxes(preview_ann),
        "embodied_preview": embodied_preview,
        "modality_preview": modality_preview,
        "pointcloud_preview": pointcloud_preview,
        "is_golden": bool(task.is_golden),
        "annotation_id": preview_ann.id if preview_ann else None,
        "canonical_annotation_id": getattr(task, "canonical_annotation_id", None),
        "versions": versions,
        "work_time": preview_ann.work_time if preview_ann else task.work_time,
        "last_reject_feedback": (task.task_metadata or {}).get("last_reject_feedback"),
    }


@router.post("/quality/review", response_model=ReviewResponse)
def review_task(
    request: ReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """审核任务：通过 → approved；驳回 → annotating（回流）。"""
    from app.services.quality_control import get_quality_service

    task = (
        db.query(Task)
        .options(joinedload(Task.project))
        .filter(Task.id == request.task_id)
        .first()
    )
    if not task or not task.project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_review_project(db, task.project, current_user):
        raise HTTPException(status_code=403, detail="无权审核该任务")

    service = get_quality_service(db)
    success = service.review_task(
        task_id=request.task_id,
        reviewer_id=current_user.id,
        decision=request.decision,
        score=request.score,
        feedback=request.feedback,
        canonical_annotation_id=request.canonical_annotation_id,
    )
    if not success:
        versions = [a for a in (task.annotations or []) if getattr(a, "is_latest", True)]
        if (
            request.decision == "approved"
            and len(versions) > 1
            and not request.canonical_annotation_id
            and not getattr(task, "canonical_annotation_id", None)
        ):
            raise HTTPException(
                status_code=400,
                detail="多人共标任务通过时请指定 canonical_annotation_id（导出真源）",
            )
        raise HTTPException(
            status_code=400,
            detail="审核失败：任务状态不可审核（需为已提交/审核中）或真源标注无效",
        )

    db.refresh(task)
    status = task.status.value if hasattr(task.status, "value") else str(task.status)
    return {
        "success": True,
        "message": f"任务已{'通过' if request.decision == 'approved' else '驳回并回流标注'}",
        "task_id": request.task_id,
        "task_status": status,
    }


@router.post("/quality/insert-golden")
def insert_golden_tasks(
    request: InsertGoldenRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.quality_control import get_quality_service

    service = get_quality_service(db)
    inserted = service.insert_golden_tasks(request.project_id, request.ratio)
    return {
        "success": True,
        "project_id": request.project_id,
        "inserted": inserted,
        "ratio": request.ratio,
    }


@router.put("/quality/tasks/{task_id}/golden-answer")
def update_golden_answer(
    task_id: int,
    body: GoldenAnswerUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """专家写入/更新黄金标准答案。"""
    task = (
        db.query(Task)
        .options(joinedload(Task.project))
        .filter(Task.id == task_id)
        .first()
    )
    if not task or not task.project:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_review_project(db, task.project, current_user):
        raise HTTPException(status_code=403, detail="无权编辑黄金答案")

    task.is_golden = True
    task.golden_answer = {
        "data": body.data,
        "source": body.source or "expert",
        "confidence": body.confidence,
    }
    db.commit()
    return {
        "success": True,
        "task_id": task_id,
        "is_golden": True,
        "has_golden_answer": True,
    }


@router.get("/quality/report/{project_id}", response_model=QualityReportResponse)
def get_quality_report(
    project_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    from app.services.quality_control import get_quality_service

    service = get_quality_service(db)
    report = service.get_project_quality_report(project_id)
    if not report:
        raise HTTPException(status_code=404, detail="项目不存在")
    return report


@router.get("/quality/leaderboard")
def get_quality_leaderboard(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services.quality_control import get_quality_service

    service = get_quality_service(db)
    annotators = (
        db.query(User)
        .filter(User.completed_tasks > 10)
        .order_by(User.accuracy_score.desc())
        .limit(limit)
        .all()
    )
    leaderboard = []
    for i, user in enumerate(annotators, 1):
        score = service.calculate_annotator_quality(user.id)
        if score:
            leaderboard.append(
                {
                    "rank": i,
                    "user_id": user.id,
                    "username": user.username,
                    "accuracy": score.accuracy,
                    "completed_tasks": user.completed_tasks,
                    "level": user.level.value if hasattr(user.level, "value") else str(user.level),
                    "overall_score": score.overall_score,
                }
            )
    return {"total": len(leaderboard), "data": leaderboard}
