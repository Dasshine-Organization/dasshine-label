"""任务级 Yjs 共编文档快照（晚加入 / 无 WS 兜底）"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, LargeBinary, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TaskCollabDoc(Base, TimestampMixin):
    __tablename__ = "task_collab_docs"
    __table_args__ = (UniqueConstraint("task_id", name="uq_task_collab_doc"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    # Y.encodeStateAsUpdate 原始字节
    state: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
