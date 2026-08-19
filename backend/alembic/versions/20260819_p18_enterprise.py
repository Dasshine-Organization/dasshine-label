"""P18: enterprise — invites, API keys, webhooks, audit, OIDC columns

Revision ID: 20260819_p18_enterprise
Revises: 20260819_p17_daily
Create Date: 2026-08-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_p18_enterprise"
down_revision: Union[str, None] = "20260819_p17_daily"
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
    if _has_table("users") and not _has_column("users", "oidc_sub"):
        op.add_column("users", sa.Column("oidc_sub", sa.String(255), nullable=True))
        op.add_column("users", sa.Column("oidc_issuer", sa.String(500), nullable=True))
        op.create_index("ix_users_oidc_sub", "users", ["oidc_sub"])

    if not _has_table("org_invites"):
        op.create_table(
            "org_invites",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("email", sa.String(255), nullable=False, index=True),
            sa.Column("role", sa.String(50), nullable=False, server_default="member"),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("invited_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("accepted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    if not _has_table("org_api_keys"):
        op.create_table(
            "org_api_keys",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("prefix", sa.String(16), nullable=False, index=True),
            sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    if not _has_table("org_webhooks"):
        op.create_table(
            "org_webhooks",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("url", sa.String(1000), nullable=False),
            sa.Column("secret", sa.String(128), nullable=False),
            sa.Column("events", sa.JSON(), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )

    if not _has_table("audit_events"):
        op.create_table(
            "audit_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("action", sa.String(80), nullable=False, index=True),
            sa.Column("resource_type", sa.String(80), nullable=True),
            sa.Column("resource_id", sa.String(80), nullable=True),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column("ip", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )


def downgrade() -> None:
    for table in ("audit_events", "org_webhooks", "org_api_keys", "org_invites"):
        if _has_table(table):
            op.drop_table(table)
    if _has_table("users") and _has_column("users", "oidc_sub"):
        op.drop_index("ix_users_oidc_sub", table_name="users")
        op.drop_column("users", "oidc_issuer")
        op.drop_column("users", "oidc_sub")
