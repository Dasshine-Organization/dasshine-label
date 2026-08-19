"""只追加审计日志"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.enterprise import AuditEvent

logger = logging.getLogger(__name__)


def record(
    db: Session,
    *,
    action: str,
    actor_user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str | int] = None,
    detail: Optional[Dict[str, Any]] = None,
    ip: Optional[str] = None,
    commit: bool = False,
) -> AuditEvent:
    ev = AuditEvent(
        action=action,
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail or {},
        ip=ip,
    )
    db.add(ev)
    if commit:
        db.commit()
        db.refresh(ev)
    else:
        db.flush()
    return ev


def list_events(
    db: Session,
    *,
    organization_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AuditEvent]:
    q = db.query(AuditEvent)
    if organization_id is not None:
        q = q.filter(AuditEvent.organization_id == organization_id)
    if action:
        q = q.filter(AuditEvent.action == action)
    return q.order_by(AuditEvent.id.desc()).limit(min(limit, 500)).all()


def to_dict(ev: AuditEvent) -> Dict[str, Any]:
    return {
        "id": ev.id,
        "organization_id": ev.organization_id,
        "actor_user_id": ev.actor_user_id,
        "action": ev.action,
        "resource_type": ev.resource_type,
        "resource_id": ev.resource_id,
        "detail": ev.detail or {},
        "ip": ev.ip,
        "created_at": ev.created_at.isoformat() if ev.created_at else None,
    }
