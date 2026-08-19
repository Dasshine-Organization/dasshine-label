"""P19: export snapshots (immutable dataset versions)

Revision ID: 20260819_p19_dataset
Revises: 20260819_p18_enterprise
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_p19_dataset"
down_revision: Union[str, None] = "20260819_p18_enterprise"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def upgrade() -> None:
    if not _has_table("export_snapshots"):
        op.create_table(
            "export_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("format", sa.String(40), nullable=False),
            sa.Column("status_filter", sa.String(40), nullable=False, server_default="approved"),
            sa.Column("storage_path", sa.String(500), nullable=False),
            sa.Column("download_url", sa.String(1000), nullable=True),
            sa.Column("bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("manifest", sa.JSON(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint("project_id", "version", name="uq_export_snapshot_project_version"),
        )


def downgrade() -> None:
    if _has_table("export_snapshots"):
        op.drop_table("export_snapshots")
