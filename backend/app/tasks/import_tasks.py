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

        success = int(data.get("success") or data.get("created") or data.get("imported") or 0)
        if success > 0 and org is not None:
            from app.services.org_billing import import_cost, spend

            ok_b, msg_b = spend(
                db,
                org,
                import_cost(success),
                reason="import",
                created_by_id=user_id,
                ref_type="async_import",
                ref_id=f"{kind}:{project_id}",
            )
            if not ok_b:
                logger.warning("async import charge failed: %s", msg_b)
            else:
                db.commit()

        logger.info(
            "import done project=%s kind=%s user=%s created=%s",
            project_id,
            kind,
            user_id,
            success,
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


@shared_task(bind=True, max_retries=1)
def import_from_storage_prefix(
    self,
    project_id: int,
    prefix: str,
    user_id: int,
    options: dict | None = None,
):
    """从存储前缀递归列文件并导入为任务。"""
    options = options or {}
    db = SessionLocal()
    try:
        from app.models.project import Project
        from app.services.dataset_service import DatasetImportService
        from app.services.file_storage import IMAGE_EXTS, FileStorageService
        from app.services.org_billing import import_cost, spend
        from app.services.org_quota import check_can_add_tasks

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"project {project_id} not found")
        org = project.organization

        limit = int(options.get("limit") or 500)
        mount_id = options.get("mount_id")
        exts_raw = options.get("extensions") or list(IMAGE_EXTS)
        exts = {
            e.lower() if str(e).startswith(".") else f".{str(e).lower()}"
            for e in exts_raw
        }
        urls = []
        if mount_id:
            from app.services.storage_mounts import get_mount, ingest_os_mount_files

            mount = get_mount(db, int(mount_id))
            if not mount or not mount.enabled:
                raise ValueError("挂载不存在或已禁用")
            urls = ingest_os_mount_files(
                mount,
                options.get("path") or "",
                project_id=project_id,
                extensions=exts,
                limit=limit,
            )
        else:
            items = FileStorageService().list_prefix(prefix, max_keys=limit, delimiter=False)
            for it in items:
                if it.get("is_dir"):
                    continue
                key = (it.get("key") or "").lower()
                if not any(key.endswith(ext) for ext in exts):
                    continue
                if it.get("url"):
                    urls.append(it["url"])
        if not urls:
            raise ValueError("前缀下没有匹配的文件")

        ok, msg = check_can_add_tasks(db, org, add_count=len(urls))
        if not ok:
            raise ValueError(msg)

        svc = DatasetImportService(db, file_server_base_url=None)
        result = svc.import_from_urls(
            project_id,
            urls,
            priority=int(options.get("priority") or 5),
            golden_ratio=float(options.get("golden_ratio") or 0.05),
        )
        data = result.to_dict() if hasattr(result, "to_dict") else dict(result)
        success = int(data.get("success") or 0)
        if success > 0 and org is not None:
            ok_b, msg_b = spend(
                db,
                org,
                import_cost(success),
                reason="import",
                created_by_id=user_id,
                ref_type="async_from_storage",
                ref_id=f"{project_id}:{prefix}",
            )
            if ok_b:
                db.commit()
            else:
                logger.warning("from-storage charge failed: %s", msg_b)
        return {
            "status": "completed",
            "project_id": project_id,
            "kind": "from-storage",
            "matched": len(urls),
            "result": data,
        }
    except Exception as exc:
        logger.error("from-storage import failed: %s", exc)
        if isinstance(exc, ValueError):
            raise
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
