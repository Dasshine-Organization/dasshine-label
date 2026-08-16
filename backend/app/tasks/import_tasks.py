"""异步数据集导入任务。"""

from __future__ import annotations

import logging
from pathlib import Path

from celery import shared_task

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def import_project_archive(
    self,
    project_id: int,
    kind: str,
    staging_path: str,
    user_id: int,
    options: dict | None = None,
):
    """
    kind: zip | yolo
    staging_path: 已落盘的归档绝对路径
    """
    options = options or {}
    db = SessionLocal()
    path = Path(staging_path)
    try:
        if not path.is_file():
            raise ValueError(f"staging file missing: {staging_path}")
        content = path.read_bytes()
        from app.services.dataset_service import DatasetImportService
        from app.services.org_quota import check_can_add_tasks
        from app.models.project import Project

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"project {project_id} not found")

        org = project.organization
        # 粗估：ZIP 内文件数未知，至少预留 1；导入后由服务计数
        ok, msg = check_can_add_tasks(db, org, add_count=1)
        if not ok:
            raise ValueError(msg)

        backend = (settings.STORAGE_BACKEND or "local").strip().lower()
        base = options.get("file_server_base_url") or ""
        if not base and backend not in ("s3", "minio", "oss"):
            base = (settings.FILE_SERVER_BASE_URL or "").strip()
        svc = DatasetImportService(db, file_server_base_url=base or None)

        if kind == "yolo":
            classes = options.get("class_names") or []
            if isinstance(classes, str):
                classes = [c.strip() for c in classes.split(",") if c.strip()]
            result = svc.import_yolo(
                project_id,
                content,
                classes,
                options.get("base_url_prefix") or "",
                int(options.get("priority") or 5),
            )
        else:
            result = svc.import_zip(
                project_id,
                content,
                base_url_prefix=options.get("base_url_prefix") or "",
                priority=int(options.get("priority") or 5),
                golden_ratio=float(options.get("golden_ratio") or 0.05),
            )

        data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        # 导入后二次校验任务上限（已写入则仅告警）
        ok2, msg2 = check_can_add_tasks(db, org, add_count=0)
        if not ok2:
            logger.warning("import finished but quota tight: %s", msg2)

        logger.info(
            "import done project=%s kind=%s user=%s created=%s",
            project_id,
            kind,
            user_id,
            data.get("created") or data.get("imported"),
        )
        return {
            "status": "completed",
            "project_id": project_id,
            "kind": kind,
            "result": data,
        }
    except Exception as exc:
        logger.error("async import failed: %s", exc)
        if isinstance(exc, ValueError):
            raise
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass
