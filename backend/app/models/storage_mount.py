"""组织存储挂载：应用级前缀 + NFS/FUSE 内核挂载登记。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StorageMount(Base, TimestampMixin):
    __tablename__ = "storage_mounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_storage_mount_org_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    # local_prefix | s3_prefix | fuse | nfs
    kind: Mapped[str] = mapped_column(String(40), default="local_prefix")
    root_prefix: Mapped[str] = mapped_column(String(512))
    read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # {nfs_export, os_mount_point, source_root, ...}
    options: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
