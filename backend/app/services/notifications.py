"""站内通知服务"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.notification import Notification


def notify(
    db: Session,
    user_id: int,
    *,
    type: str,
    title: str,
    body: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> Notification:
    row = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        payload=payload or {},
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def list_notifications(
    db: Session,
    user_id: int,
    *,
    unread_only: bool = False,
    limit: int = 50,
) -> List[Notification]:
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return q.order_by(Notification.id.desc()).limit(max(1, min(limit, 100))).all()


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .count()
    )


def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not row:
        return False
    if not row.read_at:
        row.read_at = datetime.now(timezone.utc)
        db.commit()
    return True


def mark_all_read(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .all()
    )
    for r in rows:
        r.read_at = now
    db.commit()
    return len(rows)


def to_dict(row: Notification) -> Dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "payload": row.payload or {},
        "read": bool(row.read_at),
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
