"""不可变导出快照（P19 数据集版本）"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class ExportSnapshot(Base):
    """导出快照：只追加，不更新 manifest。"""

    __tablename__ = "export_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_export_snapshot_project_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(40))
    status_filter: Mapped[str] = mapped_column(String(40), default="approved")
    storage_path: Mapped[str] = mapped_column(String(500))
    download_url: Mapped[Optional[str]] = mapped_column(String(1000))
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    task_count: Mapped[int] = mapped_column(Integer, default=0)
    manifest: Mapped[List[Dict[str, Any]]] = mapped_column(JSON)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    project: Mapped["Project"] = relationship("Project")
