"""P10: org quota JSON + (reuse task indexes from p9)

Revision ID: 20260816_p10_ops
Revises: 20260816_p9_consensus
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_p10_ops"
down_revision: Union[str, None] = "20260816_p9_consensus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "organizations" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "quota" not in cols:
        op.add_column("organizations", sa.Column("quota", sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "organizations" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("organizations")}
    if "quota" in cols:
        op.drop_column("organizations", "quota")
