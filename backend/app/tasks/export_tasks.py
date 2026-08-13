"""
数据导出任务（调用与 HTTP 相同的 exporters registry）。
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.services.exporters import build_export, default_format_for
from app.services.project_service import _get_schema, _resolve_project_category

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def export_project_data(self, project_id: int, format: str, user_id: int):
    """异步导出项目数据到 UPLOAD_DIR/exports。"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"project {project_id} not found")

        category = _resolve_project_category(project)
        fmt = (format or default_format_for(category)).strip().lower()
        tasks = (
            db.query(Task)
            .options(joinedload(Task.annotations))
            .filter(Task.project_id == project_id, Task.status == TaskStatus.APPROVED)
            .order_by(Task.id.asc())
            .all()
        )
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

        out_dir = Path(settings.UPLOAD_DIR) / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)[:40]
        filename = f"{safe}_{timestamp}{artifact.filename_suffix}"
        path = out_dir / filename
        path.write_bytes(artifact.content)

        logger.info(
            "export done project=%s format=%s user=%s path=%s",
            project_id,
            fmt,
            user_id,
            path,
        )
        return {
            "project_id": project_id,
            "format": fmt,
            "category": category,
            "path": str(path),
            "download_url": f"/uploads/exports/{filename}",
            "status": "completed",
            "bytes": len(artifact.content),
        }
    except Exception as exc:
        logger.error("导出失败: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()
