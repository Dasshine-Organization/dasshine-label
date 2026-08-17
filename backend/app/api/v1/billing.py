"""
Stripe / 计费公开 API：积分包、Checkout、Webhook。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.organization import Organization
from app.models.user import User
from app.services.org_billing import get_credits, stripe_topup_idempotent
from app.services.organization_service import OrganizationService
from app.services.stripe_billing import (
    construct_webhook_event,
    create_checkout_session,
    parse_credit_packs,
    stripe_configured,
)

logger = logging.getLogger("dasshine.stripe")

router = APIRouter(tags=["billing"])


class CheckoutBody(BaseModel):
    pack_id: str = Field(..., min_length=1, max_length=64)


@router.get("/billing/packs")
def list_credit_packs(current_user: User = Depends(get_current_user)):
    return {
        "configured": stripe_configured(),
        "items": parse_credit_packs() if stripe_configured() else [],
    }


@router.post("/orgs/{org_id}/billing/checkout")
def create_org_checkout(
    org_id: int,
    body: CheckoutBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not current_user.is_admin and not svc.user_in_org(current_user.id, org_id):
        raise HTTPException(status_code=403, detail="无权为该组织充值")
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="未配置 Stripe，请使用管理员充值")
    try:
        session = create_checkout_session(
            org_id=org_id,
            pack_id=body.pack_id,
            user_id=current_user.id,
            customer_email=getattr(current_user, "email", None),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return session


@router.post("/billing/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="缺少 Stripe-Signature")
    payload = await request.body()
    try:
        event = construct_webhook_event(payload, stripe_signature)
    except Exception as e:
        logger.warning("stripe webhook verify failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Webhook 校验失败: {e}") from e

    if event["type"] != "checkout.session.completed":
        return {"ok": True, "ignored": event["type"]}

    session = event["data"]["object"]
    session_id = session.get("id") or ""
    meta = session.get("metadata") or {}
    try:
        org_id = int(meta.get("org_id") or 0)
        credits = int(meta.get("credits") or 0)
        user_id = int(meta.get("user_id") or 0) or None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="metadata 无效")

    if not session_id or org_id <= 0 or credits <= 0:
        raise HTTPException(status_code=400, detail="session 数据不完整")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")

    row, created = stripe_topup_idempotent(
        db,
        org,
        credits,
        session_id=session_id,
        created_by_id=user_id,
        note=f"pack={meta.get('pack_id')}",
    )
    db.commit()
    logger.info(
        "stripe topup org=%s credits=%s session=%s new=%s balance=%s",
        org_id,
        credits,
        session_id,
        created,
        get_credits(org),
    )
    return {
        "ok": True,
        "created": created,
        "credits": get_credits(org),
        "ledger_id": row.id,
    }
