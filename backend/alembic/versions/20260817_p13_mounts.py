"""P13: storage_mounts virtual mount registry

Revision ID: 20260817_p13_mounts
Revises: 20260816_p11_collab_billing
Create Date: 2026-08-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_p13_mounts"
down_revision: Union[str, None] = "20260816_p11_collab_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "storage_mounts" in set(inspector.get_table_names()):
        return
    op.create_table(
        "storage_mounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False, server_default="local_prefix"),
        sa.Column("root_prefix", sa.String(512), nullable=False),
        sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("organization_id", "name", name="uq_storage_mount_org_name"),
    )
    op.create_index("ix_storage_mounts_organization_id", "storage_mounts", ["organization_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "storage_mounts" in set(inspector.get_table_names()):
        op.drop_table("storage_mounts")
