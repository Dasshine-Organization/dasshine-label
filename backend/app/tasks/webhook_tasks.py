"""出站 Webhook Celery 投递"""

from __future__ import annotations

import logging
from typing import Any, Dict

from celery import shared_task

from app.core.database import SessionLocal
from app.models.enterprise import OrgWebhook

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def deliver_webhook_task(self, webhook_id: int, event: str, payload: Dict[str, Any]):
    from app.services.webhooks import deliver_one

    db = SessionLocal()
    try:
        hook = db.query(OrgWebhook).filter(OrgWebhook.id == webhook_id).first()
        if not hook or not hook.active:
            return {"ok": False, "reason": "missing"}
        ok = deliver_one(hook, event, payload)
        if not ok:
            raise Exception("webhook delivery failed")
        return {"ok": True, "webhook_id": webhook_id}
    except Exception as exc:
        logger.warning("webhook retry id=%s: %s", webhook_id, exc)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"ok": False, "webhook_id": webhook_id}
    finally:
        db.close()
