"""add organizations, org_id on projects, task locks

Revision ID: 20260816_p8_org
Revises: 20260813_p1_category
Create Date: 2026-08-16
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_p8_org"
down_revision: Union[str, None] = "20260813_p1_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "organizations" not in tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("slug", sa.String(80), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    if "organization_members" not in tables:
        op.create_table(
            "organization_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(50), nullable=False, server_default="member"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        )
        op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
        op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    cols = {c["name"] for c in inspector.get_columns("projects")} if "projects" in tables else set()
    if "organization_id" not in cols and "projects" in tables:
        op.add_column(
            "projects",
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    user_cols = {c["name"] for c in inspector.get_columns("users")} if "users" in tables else set()
    if "active_org_id" not in user_cols and "users" in tables:
        op.add_column(
            "users",
            sa.Column("active_org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_users_active_org_id", "users", ["active_org_id"])

    tables = set(sa.inspect(conn).get_table_names())
    if "task_annotation_locks" not in tables:
        op.create_table(
            "task_annotation_locks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.UniqueConstraint("task_id", name="uq_task_annotation_lock"),
        )
        op.create_index("ix_task_annotation_locks_task_id", "task_annotation_locks", ["task_id"])
        op.create_index("ix_task_annotation_locks_user_id", "task_annotation_locks", ["user_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "task_annotation_locks" in tables:
        op.drop_table("task_annotation_locks")
    user_cols = {c["name"] for c in inspector.get_columns("users")} if "users" in tables else set()
    if "active_org_id" in user_cols:
        op.drop_index("ix_users_active_org_id", table_name="users")
        op.drop_column("users", "active_org_id")
    proj_cols = {c["name"] for c in inspector.get_columns("projects")} if "projects" in tables else set()
    if "organization_id" in proj_cols:
        op.drop_index("ix_projects_organization_id", table_name="projects")
        op.drop_column("projects", "organization_id")
    if "organization_members" in tables:
        op.drop_table("organization_members")
    if "organizations" in tables:
        op.drop_table("organizations")
