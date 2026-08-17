"""P11: collab doc + billing ledger

Revision ID: 20260816_p11_collab_billing
Revises: 20260816_p10_ops
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_p11_collab_billing"
down_revision: Union[str, None] = "20260816_p10_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "org_billing_ledger" not in tables:
        op.create_table(
            "org_billing_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("delta", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(80), nullable=False),
            sa.Column("ref_type", sa.String(40), nullable=True),
            sa.Column("ref_id", sa.String(80), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )
        op.create_index("ix_org_billing_ledger_organization_id", "org_billing_ledger", ["organization_id"])

    if "task_collab_docs" not in tables:
        op.create_table(
            "task_collab_docs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("state", sa.LargeBinary(), nullable=False),
            sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.UniqueConstraint("task_id", name="uq_task_collab_doc"),
        )
        op.create_index("ix_task_collab_docs_task_id", "task_collab_docs", ["task_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "task_collab_docs" in tables:
        op.drop_table("task_collab_docs")
    if "org_billing_ledger" in tables:
        op.drop_table("org_billing_ledger")
