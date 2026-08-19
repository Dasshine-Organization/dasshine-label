"""站内通知"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(50))  # task_rejected | task_assigned | golden_paused | lock_stolen
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship("User")
