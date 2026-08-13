"""add projects.category and projects.ann_type columns

Revision ID: 20260813_p1_category
Revises:
Create Date: 2026-08-13

现有库靠 create_all 建表；本迁移为可重复执行的增量变更：
- 新增 category / ann_type 列
- 从 annotation_schema JSON 回填
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_p1_category"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("projects")} if "projects" in inspector.get_table_names() else set()

    if "category" not in cols:
        op.add_column("projects", sa.Column("category", sa.String(length=50), nullable=True))
    if "ann_type" not in cols:
        op.add_column("projects", sa.Column("ann_type", sa.String(length=50), nullable=True))

    # 回填（PostgreSQL JSON / JSONB 均可用 ->>）
    op.execute(
        sa.text(
            """
            UPDATE projects
            SET
              category = COALESCE(
                NULLIF(TRIM(category), ''),
                NULLIF(TRIM(annotation_schema->>'category'), '')
              ),
              ann_type = COALESCE(
                NULLIF(TRIM(ann_type), ''),
                NULLIF(TRIM(annotation_schema->>'ann_type'), '')
              )
            WHERE annotation_schema IS NOT NULL
            """
        )
    )

    # 索引（若不存在）
    indexes = {ix["name"] for ix in inspector.get_indexes("projects")} if cols else set()
    # refresh cols after add
    inspector = sa.inspect(conn)
    indexes = {ix["name"] for ix in inspector.get_indexes("projects")}
    if "ix_projects_category" not in indexes:
        op.create_index("ix_projects_category", "projects", ["category"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    indexes = {ix["name"] for ix in inspector.get_indexes("projects")}
    if "ix_projects_category" in indexes:
        op.drop_index("ix_projects_category", table_name="projects")
    cols = {c["name"] for c in inspector.get_columns("projects")}
    if "ann_type" in cols:
        op.drop_column("projects", "ann_type")
    if "category" in cols:
        op.drop_column("projects", "category")
