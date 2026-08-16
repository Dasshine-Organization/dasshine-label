"""
任务标注占用锁服务。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_lock import TaskAnnotationLock
from app.models.user import User

DEFAULT_TTL_SECONDS = 120


class TaskLockService:
    def __init__(self, db: Session, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.db = db
        self.ttl = ttl_seconds

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def get_lock(self, task_id: int) -> Optional[TaskAnnotationLock]:
        row = (
            self.db.query(TaskAnnotationLock)
            .filter(TaskAnnotationLock.task_id == task_id)
            .first()
        )
        if not row:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < self._now():
            self.db.delete(row)
            self.db.commit()
            return None
        return row

    def acquire(self, task: Task, user: User) -> Dict[str, Any]:
        now = self._now()
        row = (
            self.db.query(TaskAnnotationLock)
            .filter(TaskAnnotationLock.task_id == task.id)
            .with_for_update()
            .first()
        )
        if row:
            exp = row.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp >= now and row.user_id != user.id:
                holder = self.db.query(User).filter(User.id == row.user_id).first()
                return {
                    "acquired": False,
                    "locked": True,
                    "task_id": task.id,
                    "holder_user_id": row.user_id,
                    "holder_username": holder.username if holder else None,
                    "expires_at": exp.isoformat(),
                }
            row.user_id = user.id
            row.expires_at = now + timedelta(seconds=self.ttl)
            row.heartbeat_at = now
        else:
            row = TaskAnnotationLock(
                task_id=task.id,
                user_id=user.id,
                expires_at=now + timedelta(seconds=self.ttl),
                heartbeat_at=now,
            )
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return {
            "acquired": True,
            "locked": True,
            "task_id": task.id,
            "holder_user_id": user.id,
            "holder_username": user.username,
            "expires_at": row.expires_at.isoformat(),
        }

    def heartbeat(self, task_id: int, user: User) -> Dict[str, Any]:
        row = self.get_lock(task_id)
        if not row or row.user_id != user.id:
            return {"ok": False, "reason": "not_holder"}
        now = self._now()
        row.expires_at = now + timedelta(seconds=self.ttl)
        row.heartbeat_at = now
        self.db.commit()
        return {"ok": True, "expires_at": row.expires_at.isoformat()}

    def release(self, task_id: int, user: User) -> bool:
        row = (
            self.db.query(TaskAnnotationLock)
            .filter(TaskAnnotationLock.task_id == task_id)
            .first()
        )
        if not row:
            return True
        if row.user_id != user.id and not getattr(user, "is_admin", False):
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def status(self, task_id: int) -> Dict[str, Any]:
        row = self.get_lock(task_id)
        if not row:
            return {"locked": False, "task_id": task_id}
        holder = self.db.query(User).filter(User.id == row.user_id).first()
        return {
            "locked": True,
            "task_id": task_id,
            "holder_user_id": row.user_id,
            "holder_username": holder.username if holder else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
