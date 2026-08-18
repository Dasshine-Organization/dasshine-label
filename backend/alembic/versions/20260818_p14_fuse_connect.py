"""P14: fuse/nfs mount options + collab engine

Revision ID: 20260818_p14_fuse_connect
Revises: 20260817_p13_mounts
Create Date: 2026-08-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_p14_fuse_connect"
down_revision: Union[str, None] = "20260817_p13_mounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("storage_mounts", "options"):
        op.add_column("storage_mounts", sa.Column("options", sa.JSON(), nullable=True))
    if not _has_column("task_collab_docs", "engine"):
        op.add_column(
            "task_collab_docs",
            sa.Column("engine", sa.String(32), nullable=False, server_default="automerge"),
        )


def downgrade() -> None:
    if _has_column("task_collab_docs", "engine"):
        op.drop_column("task_collab_docs", "engine")
    if _has_column("storage_mounts", "options"):
        op.drop_column("storage_mounts", "options")
