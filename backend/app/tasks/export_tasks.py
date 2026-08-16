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
    db = SessionLocal()
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
        return {
            "project_id": project_id,
            "format": fmt,
            "category": category,
            "path": rel_or_key,
            "download_url": download_url,
            "storage_backend": storage.backend_name,
            "status": "completed",
            "bytes": len(artifact.content),
        }
    except Exception as exc:
        logger.error("导出失败: %s", exc)
        # Don't retry ValueError (no data / bad status)
        if isinstance(exc, ValueError):
            raise
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()
