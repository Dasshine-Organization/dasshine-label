"""
自动标注异步任务：单条 / 批量调用 AutoLabelService。
"""

from typing import Optional

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def auto_label_task(self, task_id: int, user_id: Optional[int] = None):
    from app.core.database import SessionLocal
    from app.services.auto_label import AutoLabelService

    db = SessionLocal()
    try:
        out = AutoLabelService(db).process_task(task_id, user_id=user_id)
        return {
            "task_id": task_id,
            "success": True,
            "confidence": out.overall_confidence,
            "model": out.model,
            "adapter": out.adapter,
            "recommended": out.recommended,
        }
    except Exception as e:
        logger.exception("auto_label_task failed task_id=%s", task_id)
        return {"task_id": task_id, "success": False, "reason": str(e)}
    finally:
        db.close()


@shared_task(bind=True, max_retries=0)
def batch_auto_label_task(self, project_id: int, batch_size: int = 100, user_id: Optional[int] = None):
    from app.core.database import SessionLocal
    from app.services.auto_label import AutoLabelService

    db = SessionLocal()
    try:
        stats = AutoLabelService(db).batch_process(project_id, batch_size, user_id=user_id)
        stats["project_id"] = project_id
        stats["success"] = True
        return stats
    except Exception as e:
        logger.exception("batch_auto_label_task failed project_id=%s", project_id)
        return {
            "project_id": project_id,
            "success": False,
            "reason": str(e),
        }
    finally:
        db.close()
