"""任务级共编文档快照（Automerge save 字节；晚加入 / 无 WS 兜底）"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TaskCollabDoc(Base, TimestampMixin):
    __tablename__ = "task_collab_docs"
    __table_args__ = (UniqueConstraint("task_id", name="uq_task_collab_doc"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    # Automerge.save 原始字节（旧 Yjs 快照会被客户端丢弃并重建）
    state: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    engine: Mapped[str] = mapped_column(String(32), default="automerge")
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
