"""
具身序列标注：工作区、动作标签、逐帧标注
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class EmbodiedWorkspace(Base, TimestampMixin):
    """每个任务 + 标注员一条工作区（标签库、已保存帧列表）"""

    __tablename__ = "embodied_workspaces"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_embodied_workspace_task_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    action_labels: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    committed_frames: Mapped[List[int]] = mapped_column(JSON, nullable=False, default=list)

    task: Mapped["Task"] = relationship("Task", back_populates="embodied_workspaces")
    user: Mapped["User"] = relationship("User", back_populates="embodied_workspaces")
    frame_annotations: Mapped[List["EmbodiedFrameAnnotation"]] = relationship(
        "EmbodiedFrameAnnotation",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )


class EmbodiedFrameAnnotation(Base, TimestampMixin):
    """逐帧动作与备注"""

    __tablename__ = "embodied_frame_annotations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "frame_index", name="uq_embodied_frame_workspace_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("embodied_workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    action_id: Mapped[str] = mapped_column(String(64), nullable=False, default="idle")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_committed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    workspace: Mapped["EmbodiedWorkspace"] = relationship(
        "EmbodiedWorkspace", back_populates="frame_annotations"
    )
