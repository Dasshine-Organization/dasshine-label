"""
标注工作台草稿（多帧 2D、标签集等），按任务 + 用户唯一存储。
"""

from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class AnnotationDraft(Base, TimestampMixin):
    """任务标注过程草稿（与最终提交的 Annotation 记录区分）"""

    __tablename__ = "annotation_drafts"
    __table_args__ = (UniqueConstraint("task_id", "user_id", name="uq_annotation_draft_task_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 与前端 imageAnnotationSession 对齐的 JSON：v, currentIdx, frames, label_classes 等
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    task: Mapped["Task"] = relationship("Task", back_populates="annotation_drafts")
    user: Mapped["User"] = relationship("User", back_populates="annotation_drafts")
