"""
组织计费账本：积分余额存在 quota.credits，流水写入 org_billing_ledger。
支持管理员 topup 与 Stripe Checkout 入账（幂等）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization
from app.models.org_billing import OrgBillingLedger
from app.services.org_quota import normalize_quota


def get_credits(org: Organization) -> int:
    q = normalize_quota(getattr(org, "quota", None))
    return int(q.get("credits", 0))


def set_credits(org: Organization, value: int) -> None:
    q = normalize_quota(getattr(org, "quota", None))
    q["credits"] = max(0, int(value))
    raw = dict(org.quota) if isinstance(org.quota, dict) else {}
    raw.update(q)
    org.quota = raw


def append_ledger(
    db: Session,
    org: Organization,
    *,
    delta: int,
    reason: str,
    created_by_id: Optional[int] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    note: Optional[str] = None,
) -> OrgBillingLedger:
    bal = get_credits(org) + int(delta)
    if bal < 0:
        bal = 0
    set_credits(org, bal)
    row = OrgBillingLedger(
        organization_id=org.id,
        delta=int(delta),
        balance_after=bal,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
        created_by_id=created_by_id,
        note=note,
    )
    db.add(row)
    return row


def find_ledger_by_ref(
    db: Session, *, ref_type: str, ref_id: str
) -> Optional[OrgBillingLedger]:
    return (
        db.query(OrgBillingLedger)
        .filter(
            OrgBillingLedger.ref_type == ref_type,
            OrgBillingLedger.ref_id == ref_id,
        )
        .first()
    )


def check_can_spend(org: Optional[Organization], amount: int) -> Tuple[bool, str]:
    if org is None or not getattr(settings, "BILLING_ENABLED", True):
        return True, ""
    need = max(0, int(amount))
    if need == 0:
        return True, ""
    have = get_credits(org)
    if have < need:
        return False, f"组织积分不足（需要 {need}，当前 {have}）"
    return True, ""


def spend(
    db: Session,
    org: Optional[Organization],
    amount: int,
    *,
    reason: str,
    created_by_id: Optional[int] = None,
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
) -> Tuple[bool, str]:
    if org is None or not getattr(settings, "BILLING_ENABLED", True):
        return True, ""
    need = max(0, int(amount))
    if need == 0:
        return True, ""
    ok, msg = check_can_spend(org, need)
    if not ok:
        return False, msg
    append_ledger(
        db,
        org,
        delta=-need,
        reason=reason,
        created_by_id=created_by_id,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    return True, ""


def topup(
    db: Session,
    org: Organization,
    amount: int,
    *,
    created_by_id: Optional[int] = None,
    note: Optional[str] = None,
    reason: str = "topup",
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
) -> OrgBillingLedger:
    amt = max(0, int(amount))
    return append_ledger(
        db,
        org,
        delta=amt,
        reason=reason,
        created_by_id=created_by_id,
        ref_type=ref_type,
        ref_id=ref_id,
        note=note or reason,
    )


def stripe_topup_idempotent(
    db: Session,
    org: Organization,
    amount: int,
    *,
    session_id: str,
    created_by_id: Optional[int] = None,
    note: Optional[str] = None,
    ref_type: str = "stripe_session",
    reason: str = "stripe",
) -> Tuple[OrgBillingLedger, bool]:
    """Stripe 入账；同一 ref 只入账一次。Returns (row, created_new)."""
    existing = find_ledger_by_ref(db, ref_type=ref_type, ref_id=session_id)
    if existing is not None:
        return existing, False
    row = topup(
        db,
        org,
        amount,
        created_by_id=created_by_id,
        note=note or f"{reason} {session_id}",
        reason=reason,
        ref_type=ref_type,
        ref_id=session_id,
    )
    return row, True


def list_ledger(
    db: Session, org_id: int, *, limit: int = 50
) -> List[Dict[str, Any]]:
    rows = (
        db.query(OrgBillingLedger)
        .filter(OrgBillingLedger.organization_id == org_id)
        .order_by(OrgBillingLedger.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": r.id,
            "delta": r.delta,
            "balance_after": r.balance_after,
            "reason": r.reason,
            "ref_type": r.ref_type,
            "ref_id": r.ref_id,
            "created_by_id": r.created_by_id,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def import_cost(task_count: int) -> int:
    per = int(getattr(settings, "BILLING_CREDIT_PER_IMPORT_TASK", 1) or 1)
    return max(0, int(task_count)) * per


def export_cost() -> int:
    return int(getattr(settings, "BILLING_CREDIT_PER_EXPORT", 10) or 10)
