"""站内通知 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services import notifications as notif_svc

router = APIRouter()


@router.get("/notifications")
def list_my_notifications(
    unread_only: bool = False,
    limit: int = Query(40, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = notif_svc.list_notifications(
        db, current_user.id, unread_only=unread_only, limit=limit
    )
    return {
        "unread": notif_svc.unread_count(db, current_user.id),
        "items": [notif_svc.to_dict(r) for r in rows],
    }


@router.get("/notifications/unread-count")
def notifications_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"unread": notif_svc.unread_count(db, current_user.id)}


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not notif_svc.mark_read(db, current_user.id, notification_id):
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"success": True}


@router.post("/notifications/read-all")
def read_all_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = notif_svc.mark_all_read(db, current_user.id)
    return {"success": True, "marked": n}
