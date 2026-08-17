"""组织积分流水"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrgBillingLedger(Base, TimestampMixin):
    __tablename__ = "org_billing_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    delta: Mapped[int] = mapped_column(Integer)  # 正=充值，负=扣款
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String(80))
    ref_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ref_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
