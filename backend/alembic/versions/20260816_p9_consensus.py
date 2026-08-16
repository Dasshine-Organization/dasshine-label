"""P9: canonical annotation + task indexes for scale

Revision ID: 20260816_p9_consensus
Revises: 20260816_p8_org
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_p9_consensus"
down_revision: Union[str, None] = "20260816_p8_org"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "tasks" not in tables:
        return

    cols = {c["name"] for c in inspector.get_columns("tasks")}
    indexes = {ix["name"] for ix in inspector.get_indexes("tasks")}

    if "canonical_annotation_id" not in cols:
        op.add_column(
            "tasks",
            sa.Column(
                "canonical_annotation_id",
                sa.String(36),
                sa.ForeignKey("annotations.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_tasks_canonical_annotation_id",
            "tasks",
            ["canonical_annotation_id"],
        )

    if "ix_tasks_project_id_status" not in indexes:
        op.create_index("ix_tasks_project_id_status", "tasks", ["project_id", "status"])
    if "ix_tasks_assignee_id_status" not in indexes:
        op.create_index("ix_tasks_assignee_id_status", "tasks", ["assignee_id", "status"])
    if "ix_tasks_status" not in indexes:
        op.create_index("ix_tasks_status", "tasks", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "tasks" not in inspector.get_table_names():
        return
    indexes = {ix["name"] for ix in inspector.get_indexes("tasks")}
    cols = {c["name"] for c in inspector.get_columns("tasks")}

    for name in (
        "ix_tasks_status",
        "ix_tasks_assignee_id_status",
        "ix_tasks_project_id_status",
        "ix_tasks_canonical_annotation_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name="tasks")

    if "canonical_annotation_id" in cols:
        op.drop_column("tasks", "canonical_annotation_id")
