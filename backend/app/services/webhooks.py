"""出站 Webhook：HMAC 签名投递"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enterprise import OrgWebhook
from app.models.organization import Organization
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services import audit

logger = logging.getLogger(__name__)

SUPPORTED_EVENTS = ("task.submitted", "review.decided", "export.done")


def create_webhook(
    db: Session,
    org: Organization,
    *,
    url: str,
    events: List[str],
    created_by: User,
    secret: Optional[str] = None,
) -> OrgWebhook:
    evs = [e for e in events if e in SUPPORTED_EVENTS]
    if not evs:
        evs = list(SUPPORTED_EVENTS)
    row = OrgWebhook(
        organization_id=org.id,
        url=url.strip(),
        secret=secret or secrets.token_urlsafe(24),
        events=evs,
        active=True,
        created_by_id=created_by.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="org.webhook.create",
        actor_user_id=created_by.id,
        organization_id=org.id,
        resource_type="org_webhook",
        resource_id=row.id,
        detail={"url": row.url, "events": evs},
    )
    return row


def list_webhooks(db: Session, org_id: int) -> List[OrgWebhook]:
    return (
        db.query(OrgWebhook)
        .filter(OrgWebhook.organization_id == org_id)
        .order_by(OrgWebhook.id.desc())
        .all()
    )


def delete_webhook(db: Session, org: Organization, webhook_id: int, actor: User) -> bool:
    row = (
        db.query(OrgWebhook)
        .filter(OrgWebhook.id == webhook_id, OrgWebhook.organization_id == org.id)
        .first()
    )
    if not row:
        return False
    audit.record(
        db,
        action="org.webhook.delete",
        actor_user_id=actor.id,
        organization_id=org.id,
        resource_type="org_webhook",
        resource_id=row.id,
        detail={"url": row.url},
    )
    db.delete(row)
    return True


def webhook_to_dict(row: OrgWebhook) -> Dict[str, Any]:
    return {
        "id": row.id,
        "url": row.url,
        "events": row.events or [],
        "active": bool(row.active),
        "secret_hint": (row.secret or "")[:4] + "…",
        "created_by_id": row.created_by_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def deliver_one(hook: OrgWebhook, event: str, payload: Dict[str, Any]) -> bool:
    body_obj = {
        "event": event,
        "organization_id": hook.organization_id,
        "payload": payload,
    }
    raw = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sig = _sign(hook.secret, raw)
    headers = {
        "Content-Type": "application/json",
        "X-Dasshine-Event": event,
        "X-Dasshine-Signature": f"sha256={sig}",
    }
    try:
        with httpx.Client(timeout=settings.WEBHOOK_TIMEOUT_SEC) as client:
            resp = client.post(hook.url, content=raw, headers=headers)
        ok = 200 <= resp.status_code < 300
        if not ok:
            logger.warning(
                "webhook fail id=%s status=%s body=%s",
                hook.id,
                resp.status_code,
                resp.text[:200],
            )
        return ok
    except Exception:
        logger.exception("webhook error id=%s url=%s", hook.id, hook.url)
        return False


def emit(db: Session, organization_id: Optional[int], event: str, payload: Dict[str, Any]) -> int:
    if not organization_id or event not in SUPPORTED_EVENTS:
        return 0
    hooks = (
        db.query(OrgWebhook)
        .filter(
            OrgWebhook.organization_id == organization_id,
            OrgWebhook.active.is_(True),
        )
        .all()
    )
    sent = 0
    for h in hooks:
        if event not in (h.events or []):
            continue
        try:
            from app.tasks.webhook_tasks import deliver_webhook_task

            deliver_webhook_task.delay(h.id, event, payload)
            sent += 1
        except Exception:
            if deliver_one(h, event, payload):
                sent += 1
    return sent


def emit_for_task(db: Session, task: Task, event: str, extra: Optional[Dict[str, Any]] = None) -> int:
    org_id = None
    project = getattr(task, "project", None)
    if project is None and getattr(task, "project_id", None):
        project = db.query(Project).filter(Project.id == task.project_id).first()
    if project is not None:
        org_id = getattr(project, "organization_id", None)
    payload = {
        "task_id": task.id,
        "project_id": task.project_id,
        "status": task.status.value if hasattr(task.status, "value") else str(task.status),
        **(extra or {}),
    }
    return emit(db, org_id, event, payload)
