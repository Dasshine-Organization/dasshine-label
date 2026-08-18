"""
数据集导入 API
POST /api/v1/projects/{id}/import/urls       — URL 列表
POST /api/v1/projects/{id}/import/texts      — 文本列表
POST /api/v1/projects/{id}/import/files      — 本地图像文件
POST /api/v1/projects/{id}/import/zip        — ZIP 文件（图像/音频/点云）
POST /api/v1/projects/{id}/import/coco       — COCO JSON 文件
POST /api/v1/projects/{id}/import/yolo       — YOLO ZIP
POST /api/v1/projects/{id}/import/csv        — CSV 文件
POST /api/v1/projects/{id}/import/jsonl      — JSONL 文件
GET  /api/v1/projects/{id}/import/stats      — 导入统计
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from app.core.config import settings
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

def _is_zip_bytes(content: bytes, filename: Optional[str] = None) -> bool:
    if filename and filename.lower().endswith(".zip"):
        return True
    return len(content) >= 4 and content[:2] == b"PK"


def _import_service(db: Session, file_server_base_url: str = "") -> DatasetImportService:
    """构建导入服务。显式传入的前缀优先；S3 模式下空前缀交给 S3_PUBLIC_BASE_URL。"""
    base = (file_server_base_url or "").strip()
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if not base:
        if backend in ("s3", "minio", "oss"):
            return DatasetImportService(db, file_server_base_url=None)
        base = (settings.FILE_SERVER_BASE_URL or "").strip()
    return DatasetImportService(db, file_server_base_url=base or None)


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


def _enforce_task_quota(db: Session, project, add_count: int = 1):
    from app.services.org_quota import check_can_add_tasks

    org = getattr(project, "organization", None)
    if org is None and getattr(project, "organization_id", None):
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    ok, msg = check_can_add_tasks(db, org, add_count=add_count)
    if not ok:
        raise HTTPException(403, msg)


def _project_org(db: Session, project):
    org = getattr(project, "organization", None)
    if org is None and getattr(project, "organization_id", None):
        from app.models.organization import Organization

        org = db.query(Organization).filter(Organization.id == project.organization_id).first()
    return org


def _enforce_import_credits(db: Session, project, add_count: int = 1):
    from app.services.org_billing import check_can_spend, import_cost

    org = _project_org(db, project)
    ok, msg = check_can_spend(org, import_cost(add_count))
    if not ok:
        raise HTTPException(402, msg)


def _charge_import_success(
    db: Session,
    project,
    success: int,
    *,
    user_id: int,
    ref_id: str,
):
    from app.services.org_billing import import_cost, spend

    if success <= 0:
        return
    org = _project_org(db, project)
    ok, msg = spend(
        db,
        org,
        import_cost(success),
        reason="import",
        created_by_id=user_id,
        ref_type="project",
        ref_id=ref_id,
    )
    if not ok:
        # 已导入完成时仅记警告，避免回滚大批量任务
        import logging

        logging.getLogger("dasshine.billing").warning("import charge failed: %s", msg)
    else:
        db.commit()


def _stage_upload(content: bytes, suffix: str = ".zip") -> str:
    from pathlib import Path
    import uuid

    staging = Path(settings.UPLOAD_DIR) / "import_staging"
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return str(path)


@router.get("/import-jobs/{job_id}")
def get_import_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """查询异步导入任务状态。"""
    try:
        from celery.result import AsyncResult
        from app.celery_app import celery_app

        result = AsyncResult(job_id, app=celery_app)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"无法查询导入任务（{e}）") from e

    state = (result.state or "PENDING").upper()
    payload = {
        "job_id": job_id,
        "state": state,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
    }
    if result.successful():
        data = result.result if isinstance(result.result, dict) else {}
        payload.update({"status": "completed", **data})
    elif result.failed():
        payload["status"] = "failed"
        payload["error"] = str(result.result)
    return payload


# ── URL import ────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/urls")
def import_urls(
    project_id: int,
    payload: UrlImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _check_project_access(project_id, current_user, db)
    n = len(payload.urls)
    _enforce_task_quota(db, project, add_count=n)
    _enforce_import_credits(db, project, add_count=n)
    svc = _import_service(db)
    result = svc.import_from_urls(
        project_id, payload.urls,
        priority=payload.priority,
        golden_ratio=payload.golden_ratio,
    )
    out = result.to_dict()
    _charge_import_success(
        db, project, int(out.get("success") or 0),
        user_id=current_user.id, ref_id=f"urls:{project_id}",
    )
    return out


# ── Text import ───────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/texts")
def import_texts(
    project_id: int,
    payload: TextImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _check_project_access(project_id, current_user, db)
    n = len(payload.texts)
    _enforce_task_quota(db, project, add_count=n)
    _enforce_import_credits(db, project, add_count=n)
    svc = _import_service(db)
    result = svc.import_from_texts(
        project_id, payload.texts,
        priority=payload.priority,
        golden_ratio=payload.golden_ratio,
    )
    out = result.to_dict()
    _charge_import_success(
        db, project, int(out.get("success") or 0),
        user_id=current_user.id, ref_id=f"texts:{project_id}",
    )
    return out


# ── ZIP file upload ───────────────────────────────────────────────────────────

@router.post("/{project_id}/import/files")
async def import_local_files(
    project_id: int,
    files: List[UploadFile] = File(...),
    file_server_base_url: str = Form(""),
    priority: int = Form(5),
    golden_ratio: float = Form(0.05),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入本地图像文件（支持多选或文件夹拖入）"""
    project = _check_project_access(project_id, current_user, db)
    if not files:
        raise HTTPException(400, "请至少上传一个文件")
    _enforce_task_quota(db, project, add_count=len(files))
    _enforce_import_credits(db, project, add_count=len(files))

    max_size = settings.MAX_UPLOAD_SIZE
    payload: List[tuple] = []
    for f in files:
        content = await f.read()
        if len(content) > max_size:
            raise HTTPException(413, f"文件 {f.filename} 超过大小限制")
        name = f.filename or "image.jpg"
        payload.append((name, content))

    svc = _import_service(db, file_server_base_url)
    result = svc.import_local_files(
        project_id, payload, priority=priority, golden_ratio=golden_ratio
    )
    out = result.to_dict()
    _charge_import_success(
        db, project, int(out.get("success") or 0),
        user_id=current_user.id, ref_id=f"files:{project_id}",
    )
    return out


@router.post("/{project_id}/import/zip")
async def import_zip(
    project_id: int,
    file: UploadFile = File(...),
    base_url_prefix: str = Form(""),
    file_server_base_url: str = Form(""),
    priority: int = Form(5),
    golden_ratio: float = Form(0.05),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _check_project_access(project_id, current_user, db)
    _enforce_task_quota(db, project, add_count=1)
    _enforce_import_credits(db, project, add_count=1)

    content = await file.read()
    if not content:
        raise HTTPException(400, "ZIP 文件为空")
    if not _is_zip_bytes(content, file.filename):
        raise HTTPException(400, "请上传有效的 ZIP 压缩包（.zip）")
    if len(content) > 500 * 1024 * 1024:  # 500MB limit
        raise HTTPException(413, "File too large (max 500MB)")

    svc = _import_service(db, file_server_base_url)
    result = svc.import_zip(
        project_id, content,
        base_url_prefix=base_url_prefix,
        priority=priority,
        golden_ratio=golden_ratio,
    )
    payload = result.to_dict()
    _charge_import_success(
        db,
        project,
        int(payload.get("success") or 0),
        user_id=current_user.id,
        ref_id=f"zip:{project_id}",
    )
    return payload


@router.post("/{project_id}/import/zip/jobs")
async def import_zip_job(
    project_id: int,
    file: UploadFile = File(...),
    base_url_prefix: str = Form(""),
    file_server_base_url: str = Form(""),
    priority: int = Form(5),
    golden_ratio: float = Form(0.05),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """异步 ZIP 导入：落盘后入队 Celery。"""
    project = _check_project_access(project_id, current_user, db)
    _enforce_task_quota(db, project, add_count=1)
    _enforce_import_credits(db, project, add_count=1)

    content = await file.read()
    if not content or not _is_zip_bytes(content, file.filename):
        raise HTTPException(400, "请上传有效的 ZIP 压缩包（.zip）")
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 500MB)")

    staging = _stage_upload(content, ".zip")
    try:
        from app.tasks.import_tasks import import_project_archive

        async_result = import_project_archive.delay(
            project_id,
            "zip",
            staging,
            current_user.id,
            {
                "base_url_prefix": base_url_prefix,
                "file_server_base_url": file_server_base_url,
                "priority": priority,
                "golden_ratio": golden_ratio,
            },
        )
    except Exception as e:
        Path = __import__("pathlib").Path
        try:
            Path(staging).unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(
            status_code=503,
            detail=f"后台导入不可用，请使用同步导入或启动 Celery/Redis（{e}）",
        ) from e

    return {
        "job_id": async_result.id,
        "status": "queued",
        "project_id": project_id,
        "kind": "zip",
    }


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

    svc = _import_service(db)
    result = svc.import_coco_json(project_id, coco_json, import_annotations=import_anns)
    return result.to_dict()


# ── YOLO ZIP ──────────────────────────────────────────────────────────────────

@router.post("/{project_id}/import/yolo")
async def import_yolo(
    project_id: int,
    file: UploadFile = File(...),
    class_names: str = Form(""),          # comma-separated
    base_url_prefix: str = Form(""),
    file_server_base_url: str = Form(""),
    priority: int = Form(5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _check_project_access(project_id, current_user, db)
    _enforce_task_quota(db, project, add_count=1)
    _enforce_import_credits(db, project, add_count=1)

    content = await file.read()
    if not content or not _is_zip_bytes(content, file.filename):
        raise HTTPException(400, "请上传有效的 YOLO ZIP 压缩包")
    classes = [c.strip() for c in class_names.split(",") if c.strip()]

    svc = _import_service(db, file_server_base_url)
    result = svc.import_yolo(project_id, content, classes, base_url_prefix, priority)
    out = result.to_dict()
    _charge_import_success(
        db, project, int(out.get("success") or 0),
        user_id=current_user.id, ref_id=f"yolo:{project_id}",
    )
    return out


@router.post("/{project_id}/import/yolo/jobs")
async def import_yolo_job(
    project_id: int,
    file: UploadFile = File(...),
    class_names: str = Form(""),
    base_url_prefix: str = Form(""),
    file_server_base_url: str = Form(""),
    priority: int = Form(5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _check_project_access(project_id, current_user, db)
    _enforce_task_quota(db, project, add_count=1)
    _enforce_import_credits(db, project, add_count=1)

    content = await file.read()
    if not content or not _is_zip_bytes(content, file.filename):
        raise HTTPException(400, "请上传有效的 YOLO ZIP 压缩包")

    staging = _stage_upload(content, ".zip")
    try:
        from app.tasks.import_tasks import import_project_archive

        async_result = import_project_archive.delay(
            project_id,
            "yolo",
            staging,
            current_user.id,
            {
                "class_names": class_names,
                "base_url_prefix": base_url_prefix,
                "file_server_base_url": file_server_base_url,
                "priority": priority,
            },
        )
    except Exception as e:
        from pathlib import Path

        try:
            Path(staging).unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(
            status_code=503,
            detail=f"后台导入不可用，请使用同步导入或启动 Celery/Redis（{e}）",
        ) from e

    return {
        "job_id": async_result.id,
        "status": "queued",
        "project_id": project_id,
        "kind": "yolo",
    }


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

    svc = _import_service(db)
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

    svc = _import_service(db)
    result = svc.import_jsonl(project_id, content, priority=priority, golden_ratio=golden_ratio)
    return result.to_dict()


# ── Embodied episodes ─────────────────────────────────────────────────────────

@router.post("/{project_id}/import/embodied")
async def import_embodied(
    project_id: int,
    file: Optional[UploadFile] = File(None),
    priority: int = Form(5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导入具身 Episode JSON / JSONL（含 streams，可选 proprioception）。"""
    _check_project_access(project_id, current_user, db)
    if not file:
        raise HTTPException(400, "请上传 episode JSON 或 JSONL 文件")
    content = (await file.read()).decode("utf-8")
    svc = _import_service(db)
    result = svc.import_embodied_episodes(project_id, content, priority=priority)
    return result.to_dict()


# ── From storage prefix (P11 mount) ───────────────────────────────────────────

class FromStorageImportRequest(BaseModel):
    prefix: str = Field("", max_length=512)
    mount_id: Optional[int] = None
    path: str = Field("", max_length=512)
    extensions: Optional[List[str]] = None
    limit: int = Field(500, ge=1, le=5000)
    priority: int = Field(5, ge=1, le=10)
    golden_ratio: float = Field(0.05, ge=0, le=0.3)


def _resolve_from_storage_prefix(db: Session, payload: FromStorageImportRequest, current_user: User) -> str:
    if payload.mount_id:
        from app.services.organization_service import OrganizationService
        from app.services.storage_mounts import get_mount, resolve_mount_prefix

        m = get_mount(db, payload.mount_id)
        if not m or not m.enabled:
            raise HTTPException(404, "挂载不存在或已禁用")
        svc = OrganizationService(db)
        if not current_user.is_admin and not svc.user_in_org(current_user.id, m.organization_id):
            raise HTTPException(403, "无权使用该挂载")
        try:
            return resolve_mount_prefix(m, payload.path or "")
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
    prefix = (payload.prefix or "").strip()
    if not prefix:
        raise HTTPException(400, "请提供 prefix 或 mount_id")
    return prefix


@router.post("/{project_id}/import/from-storage")
def import_from_storage(
    project_id: int,
    payload: FromStorageImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从当前存储后端前缀浏览结果批量建任务（local / S3 / NFS / FUSE）。"""
    from app.services.file_storage import IMAGE_EXTS, FileStorageService
    from app.services.storage_mounts import get_mount, ingest_os_mount_files

    project = _check_project_access(project_id, current_user, db)

    prefix = _resolve_from_storage_prefix(db, payload, current_user)
    exts = {
        e.lower() if e.startswith(".") else f".{e.lower()}"
        for e in (payload.extensions or list(IMAGE_EXTS))
    }
    urls: List[str] = []
    try:
        mount = get_mount(db, payload.mount_id) if payload.mount_id else None
        if mount and mount.kind in ("nfs", "fuse"):
            urls = ingest_os_mount_files(
                mount,
                payload.path or "",
                project_id=project_id,
                extensions=exts,
                limit=payload.limit,
            )
        else:
            items = FileStorageService().list_prefix(
                prefix, max_keys=payload.limit, delimiter=False
            )
            for it in items:
                if it.get("is_dir"):
                    continue
                key = (it.get("key") or "").lower()
                if not any(key.endswith(ext) for ext in exts):
                    continue
                url = it.get("url")
                if url:
                    urls.append(url)
    except Exception as e:
        raise HTTPException(400, f"浏览存储失败: {e}") from e

    if not urls:
        raise HTTPException(400, "前缀下没有匹配的文件")

    _enforce_task_quota(db, project, add_count=len(urls))
    _enforce_import_credits(db, project, add_count=len(urls))

    svc = _import_service(db)
    result = svc.import_from_urls(
        project_id,
        urls,
        priority=payload.priority,
        golden_ratio=payload.golden_ratio,
    )
    out = result.to_dict()
    out["source_prefix"] = prefix
    out["matched"] = len(urls)
    _charge_import_success(
        db,
        project,
        int(out.get("success") or 0),
        user_id=current_user.id,
        ref_id=f"from-storage:{project_id}",
    )
    return out


@router.post("/{project_id}/import/from-storage/jobs")
def import_from_storage_job(
    project_id: int,
    payload: FromStorageImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """大前缀异步导入（Celery）。"""
    project = _check_project_access(project_id, current_user, db)
    prefix = _resolve_from_storage_prefix(db, payload, current_user)
    _enforce_task_quota(db, project, add_count=1)
    _enforce_import_credits(db, project, add_count=1)
    try:
        from app.tasks.import_tasks import import_from_storage_prefix

        async_result = import_from_storage_prefix.delay(
            project_id,
            prefix,
            current_user.id,
            {
                "extensions": payload.extensions,
                "limit": payload.limit,
                "priority": payload.priority,
                "golden_ratio": payload.golden_ratio,
                "mount_id": payload.mount_id,
                "path": payload.path,
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"后台导入不可用，请使用同步导入或启动 Celery/Redis（{e}）",
        ) from e
    return {
        "job_id": async_result.id,
        "status": "queued",
        "project_id": project_id,
        "kind": "from-storage",
        "prefix": prefix,
    }


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/import/stats")
def import_stats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_project_access(project_id, current_user, db)
    return _import_service(db).get_import_stats(project_id)
