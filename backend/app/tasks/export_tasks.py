"""
数据导出任务（调用与 HTTP 相同的 exporters registry）。
产物经 FileStorageService 落盘：local → UPLOAD_DIR；s3 → 对象桶。
"""

from __future__ import annotations

import logging
from datetime import datetime

from celery import shared_task
from sqlalchemy.orm import joinedload

from app.core.database import SessionLocal
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.services.exporters import build_export, default_format_for
from app.services.file_storage import FileStorageService
from app.services.project_service import _get_schema, _resolve_project_category

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def export_project_data(self, project_id: int, format: str, user_id: int, status: str = "approved"):
    """异步导出项目数据，写入统一存储并返回公网 download_url。"""
    import time

    from app.core.metrics import observe_export

    db = SessionLocal()
    started = time.perf_counter()
    ok = False
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"project {project_id} not found")

        category = _resolve_project_category(project)
        fmt = (format or default_format_for(category)).strip().lower()
        query = (
            db.query(Task)
            .options(joinedload(Task.annotations))
            .filter(Task.project_id == project_id)
        )
        if status and status != "all":
            try:
                st = TaskStatus(status)
            except ValueError as e:
                raise ValueError(f"无效状态: {status}") from e
            query = query.filter(Task.status == st)
        else:
            query = query.filter(Task.status == TaskStatus.APPROVED)
        tasks = query.order_by(Task.id.asc()).all()
        if not tasks:
            raise ValueError("没有可导出的数据")

        schema = _get_schema(project)
        label_classes = schema.get("label_classes") or schema.get("labels") or []
        artifact = build_export(
            category,
            fmt,
            tasks,
            project.name,
            label_classes if isinstance(label_classes, list) else [],
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)[:40]
        filename = f"{safe}_{timestamp}{artifact.filename_suffix}"

        storage = FileStorageService()
        rel_or_key, download_url = storage.save_bytes(
            project_id,
            filename,
            artifact.content,
            subdir="exports",
        )

        logger.info(
            "export done project=%s format=%s user=%s backend=%s url=%s",
            project_id,
            fmt,
            user_id,
            storage.backend_name,
            download_url,
        )
        snap_version = None
        snap_id = None
        try:
            from app.services import audit
            from app.services.export_snapshots import create_snapshot
            from app.services.webhooks import emit

            org_id = getattr(project, "organization_id", None)
            snap = create_snapshot(
                db,
                project_id=project_id,
                tasks=tasks,
                fmt=fmt,
                status_filter=status or "approved",
                storage_path=rel_or_key,
                download_url=download_url,
                size_bytes=len(artifact.content),
                created_by_id=user_id,
            )
            snap_version = snap.version
            snap_id = snap.id
            payload = {
                "project_id": project_id,
                "format": fmt,
                "download_url": download_url,
                "user_id": user_id,
                "bytes": len(artifact.content),
                "snapshot_version": snap_version,
                "snapshot_id": snap_id,
            }
            emit(db, org_id, "export.done", payload)
            audit.record(
                db,
                action="export.done",
                actor_user_id=user_id,
                organization_id=org_id,
                resource_type="export_snapshot",
                resource_id=snap_id,
                detail={"format": fmt, "bytes": len(artifact.content), "version": snap_version},
            )
            db.commit()
        except Exception:
            logger.exception("export webhook/audit/snapshot failed")
        ok = True
        return {
            "project_id": project_id,
            "format": fmt,
            "category": category,
            "path": rel_or_key,
            "download_url": download_url,
            "storage_backend": storage.backend_name,
            "status": "completed",
            "bytes": len(artifact.content),
            "snapshot_version": snap_version,
            "snapshot_id": snap_id,
        }
    except Exception as exc:
        logger.error("导出失败: %s", exc)
        # Don't retry ValueError (no data / bad status)
        if isinstance(exc, ValueError):
            raise
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        observe_export("celery", "ok" if ok else "error", time.perf_counter() - started)
        db.close()
