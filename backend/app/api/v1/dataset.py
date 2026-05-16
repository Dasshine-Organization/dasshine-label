"""
数据集导入 API
POST /api/v1/projects/{id}/import/urls       — URL 列表
POST /api/v1/projects/{id}/import/texts      — 文本列表
POST /api/v1/projects/{id}/import/zip        — ZIP 文件（图像/音频/点云）
POST /api/v1/projects/{id}/import/coco       — COCO JSON 文件
POST /api/v1/projects/{id}/import/yolo       — YOLO ZIP
POST /api/v1/projects/{id}/import/csv        — CSV 文件
POST /api/v1/projects/{id}/import/jsonl      — JSONL 文件
GET  /api/v1/projects/{id}/import/stats      — 导入统计
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin as require_admin
from app.models.user import User
from app.services.project_service import ProjectService
from app.services.dataset_service import DatasetImportService

router = APIRouter(prefix="/projects", tags=["dataset-import"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UrlImportRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1)
    priority: int = Field(5, ge=1, le=10)
    golden_ratio: float = Field(0.05, ge=0, le=0.3)


class TextImportRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)
    priority: int = Field(5, ge=1, le=10)
    golden_ratio: float = Field(0.05, ge=0, le=0.3)


class CocoImportRequest(BaseModel):
    coco_json: dict
    import_annotations: bool = True
    priority: int = 5


class JsonlImportRequest(BaseModel):
    content: str
    priority: int = 5
    golden_ratio: float = 0.05


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_project_access(project_id: int, current_user: User, db: Session):
    """Verify project exists and user has access."""
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if project.created_by_id != current_user.id and not current_user.is_admin:
        # Check if member
        from app.models.project import ProjectMember
        member = db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        ).first()
        if not member or member.role not in ("owner", "manager"):
            raise HTTPException(403, "No permission to import data")
    return project


# ── URL import ────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/urls")
def import_urls(
    project_id: int,
    payload: UrlImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    svc = DatasetImportService(db)
    result = svc.import_from_urls(
        project_id, payload.urls,
        priority=payload.priority,
        golden_ratio=payload.golden_ratio,
    )
    return result.to_dict()


# ── Text import ───────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/texts")
def import_texts(
    project_id: int,
    payload: TextImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    svc = DatasetImportService(db)
    result = svc.import_from_texts(
        project_id, payload.texts,
        priority=payload.priority,
        golden_ratio=payload.golden_ratio,
    )
    return result.to_dict()


# ── ZIP file upload ───────────────────────────────────────────────────────────

@router.post("/{project_id}/import/zip")
async def import_zip(
    project_id: int,
    file: UploadFile = File(...),
    base_url_prefix: str = Form(""),
    priority: int = Form(5),
    golden_ratio: float = Form(0.05),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "Only .zip files are supported")

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:  # 500MB limit
        raise HTTPException(413, "File too large (max 500MB)")

    svc = DatasetImportService(db)
    result = svc.import_zip(
        project_id, content,
        base_url_prefix=base_url_prefix,
        priority=priority,
        golden_ratio=golden_ratio,
    )
    return result.to_dict()


# ── COCO JSON ─────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/coco")
async def import_coco(
    project_id: int,
    file: Optional[UploadFile] = File(None),
    payload: Optional[CocoImportRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    import json

    if file:
        content = await file.read()
        try:
            coco_json = json.loads(content)
        except Exception:
            raise HTTPException(400, "Invalid JSON file")
        import_anns = True
    elif payload:
        coco_json = payload.coco_json
        import_anns = payload.import_annotations
    else:
        raise HTTPException(400, "Provide either a file or JSON body")

    svc = DatasetImportService(db)
    result = svc.import_coco_json(project_id, coco_json, import_annotations=import_anns)
    return result.to_dict()


# ── YOLO ZIP ──────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/yolo")
async def import_yolo(
    project_id: int,
    file: UploadFile = File(...),
    class_names: str = Form(""),          # comma-separated
    base_url_prefix: str = Form(""),
    priority: int = Form(5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    if not file.filename.endswith(".zip"):
        raise HTTPException(400, "Only .zip files are supported")

    content = await file.read()
    classes = [c.strip() for c in class_names.split(",") if c.strip()]

    svc = DatasetImportService(db)
    result = svc.import_yolo(project_id, content, classes, base_url_prefix, priority)
    return result.to_dict()


# ── CSV ───────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/csv")
async def import_csv(
    project_id: int,
    file: UploadFile = File(...),
    text_column: str = Form("text"),
    label_column: str = Form(""),
    priority: int = Form(5),
    golden_ratio: float = Form(0.05),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    content = await file.read()
    try:
        csv_str = content.decode("utf-8-sig")  # handle BOM
    except Exception:
        raise HTTPException(400, "Cannot decode file as UTF-8")

    svc = DatasetImportService(db)
    result = svc.import_csv(
        project_id, csv_str,
        text_column=text_column,
        label_column=label_column or None,
        priority=priority,
        golden_ratio=golden_ratio,
    )
    return result.to_dict()


# ── JSONL ─────────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/jsonl")
async def import_jsonl(
    project_id: int,
    file: Optional[UploadFile] = File(None),
    payload: Optional[JsonlImportRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)

    if file:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8")
        priority, golden_ratio = 5, 0.05
    elif payload:
        content = payload.content
        priority, golden_ratio = payload.priority, payload.golden_ratio
    else:
        raise HTTPException(400, "Provide a file or JSON body")

    svc = DatasetImportService(db)
    result = svc.import_jsonl(project_id, content, priority=priority, golden_ratio=golden_ratio)
    return result.to_dict()


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/import/stats")
def import_stats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    return DatasetImportService(db).get_import_stats(project_id)
