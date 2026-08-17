"""
自动标注异步任务（LLM/OCR 未接入：直接失败，不重试 mock）。
"""

from celery import shared_task
import logging

logger = logging.getLogger(__name__)

_MSG = "LLM/OCR 自动标注未接入；请使用 /tasks/{id}/prelabel/*"


@shared_task(bind=True, max_retries=0)
def auto_label_task(self, task_id: int):
    logger.warning("auto_label_task refused task_id=%s: %s", task_id, _MSG)
    return {"task_id": task_id, "success": False, "reason": "not_implemented", "detail": _MSG}


@shared_task(bind=True, max_retries=0)
def batch_auto_label_task(self, project_id: int, batch_size: int = 100):
    logger.warning("batch_auto_label_task refused project_id=%s: %s", project_id, _MSG)
    return {
        "project_id": project_id,
        "success": False,
        "reason": "not_implemented",
        "detail": _MSG,
    }
