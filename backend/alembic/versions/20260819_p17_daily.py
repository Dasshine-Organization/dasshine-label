"""P17: project member meta + in-app notifications

Revision ID: 20260819_p17_daily
Revises: 20260818_p14_fuse_connect
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_p17_daily"
down_revision: Union[str, None] = "20260818_p14_fuse_connect"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table in inspector.get_table_names()


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if _has_table("project_members") and not _has_column("project_members", "meta"):
        op.add_column("project_members", sa.Column("meta", sa.JSON(), nullable=True))

    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("type", sa.String(50), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )


def downgrade() -> None:
    if _has_table("notifications"):
        op.drop_table("notifications")
    if _has_table("project_members") and _has_column("project_members", "meta"):
        op.drop_column("project_members", "meta")
