"""
Stripe / 计费公开 API：积分包、订阅、Portal、Webhook。
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
    apply_connect_account_updated,
    connect_enabled,
    construct_webhook_event,
    create_checkout_session,
    create_connect_login,
    create_connect_onboarding,
    create_portal_session,
    create_subscription_checkout,
    ensure_customer,
    get_billing_profile,
    get_plan,
    get_plan_by_price,
    parse_credit_packs,
    parse_price_plans,
    patch_billing_profile,
    stripe_configured,
    tax_enabled,
)

logger = logging.getLogger("dasshine.stripe")

router = APIRouter(tags=["billing"])


class CheckoutBody(BaseModel):
    pack_id: str = Field(..., min_length=1, max_length=64)


class SubscribeBody(BaseModel):
    plan_id: str = Field(..., min_length=1, max_length=64)


def _org_access(db: Session, org_id: int, user: User) -> Organization:
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not user.is_admin and not svc.user_in_org(user.id, org_id):
        raise HTTPException(status_code=403, detail="无权操作该组织计费")
    return org


@router.get("/billing/packs")
def list_credit_packs(current_user: User = Depends(get_current_user)):
    return {
        "configured": stripe_configured(),
        "items": parse_credit_packs() if stripe_configured() else [],
    }


@router.get("/billing/plans")
def list_subscription_plans(current_user: User = Depends(get_current_user)):
    return {
        "configured": stripe_configured(),
        "items": parse_price_plans() if stripe_configured() else [],
    }


@router.post("/orgs/{org_id}/billing/checkout")
def create_org_checkout(
    org_id: int,
    body: CheckoutBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="未配置 Stripe，请使用管理员充值")
    try:
        customer_id = None
        try:
            customer_id = ensure_customer(
                db, org, email=getattr(current_user, "email", None)
            )
        except Exception:
            customer_id = None
        session = create_checkout_session(
            org_id=org_id,
            pack_id=body.pack_id,
            user_id=current_user.id,
            customer_email=getattr(current_user, "email", None),
            customer_id=customer_id,
            org=org,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return session


@router.post("/orgs/{org_id}/billing/subscribe")
def create_org_subscribe(
    org_id: int,
    body: SubscribeBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="未配置 Stripe")
    if not parse_price_plans():
        raise HTTPException(status_code=503, detail="未配置 STRIPE_PRICE_PLANS")
    try:
        return create_subscription_checkout(
            org=org,
            plan_id=body.plan_id,
            user_id=current_user.id,
            customer_email=getattr(current_user, "email", None),
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/orgs/{org_id}/billing/portal")
def create_org_portal(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="未配置 Stripe")
    try:
        return create_portal_session(org=org, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/billing/features")
def billing_features(current_user: User = Depends(get_current_user)):
    return {
        "configured": stripe_configured(),
        "tax_enabled": tax_enabled() and stripe_configured(),
        "connect_enabled": connect_enabled(),
    }


@router.post("/orgs/{org_id}/billing/connect/onboard")
def org_connect_onboard(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    try:
        return create_connect_onboarding(
            db, org, email=getattr(current_user, "email", None)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/orgs/{org_id}/billing/connect/login")
def org_connect_login(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    try:
        return create_connect_login(org)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.get("/orgs/{org_id}/billing/subscription")
def get_org_subscription(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _org_access(db, org_id, current_user)
    profile = get_billing_profile(org)
    plan = get_plan(profile.get("subscription_plan_id") or "") if profile.get("subscription_plan_id") else None
    return {
        **profile,
        "plan": plan,
        "credits": get_credits(org),
        "tax_enabled": tax_enabled() and stripe_configured(),
        "connect_enabled": connect_enabled(),
    }


def _handle_checkout_completed(db: Session, session: dict):
    meta = session.get("metadata") or {}
    kind = meta.get("kind") or "one_time"
    session_id = session.get("id") or ""
    if kind == "subscription":
        # 订阅创建由 subscription.* / invoice.paid 处理；此处仅绑定 customer
        try:
            org_id = int(meta.get("org_id") or 0)
        except (TypeError, ValueError):
            return {"ok": True, "ignored": "bad_meta"}
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if org and session.get("customer"):
            patch_billing_profile(
                org,
                stripe_customer_id=session.get("customer"),
                subscription_plan_id=meta.get("plan_id"),
                subscription_status="incomplete",
            )
            db.commit()
        return {"ok": True, "kind": "subscription_checkout"}

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
    if session.get("customer"):
        patch_billing_profile(org, stripe_customer_id=session.get("customer"))
    row, created = stripe_topup_idempotent(
        db,
        org,
        credits,
        session_id=session_id,
        created_by_id=user_id,
        note=f"pack={meta.get('pack_id')}",
    )
    db.commit()
    return {
        "ok": True,
        "created": created,
        "credits": get_credits(org),
        "ledger_id": row.id,
    }


def _handle_invoice_paid(db: Session, invoice: dict):
    invoice_id = invoice.get("id") or ""
    sub_id = invoice.get("subscription")
    customer = invoice.get("customer")
    # 从 line items 推断 price
    lines = (invoice.get("lines") or {}).get("data") or []
    price_id = None
    org_id = None
    credits = 0
    plan_id = None
    for line in lines:
        price = (line.get("price") or {}) if isinstance(line.get("price"), dict) else {}
        price_id = price.get("id") or price_id
        meta = line.get("metadata") or {}
        if meta.get("org_id"):
            try:
                org_id = int(meta["org_id"])
            except (TypeError, ValueError):
                pass
        if meta.get("plan_id"):
            plan_id = meta.get("plan_id")
        if meta.get("credits_per_month"):
            try:
                credits = int(meta["credits_per_month"])
            except (TypeError, ValueError):
                pass
    plan = get_plan(plan_id) if plan_id else (get_plan_by_price(price_id) if price_id else None)
    if plan:
        credits = credits or int(plan.get("credits_per_month") or 0)
        plan_id = plan_id or plan.get("id")

    org = None
    if org_id:
        org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None and customer:
        # 按 customer 反查
        for o in db.query(Organization).all():
            if get_billing_profile(o).get("stripe_customer_id") == customer:
                org = o
                break
    if not org or credits <= 0 or not invoice_id:
        return {"ok": True, "ignored": "invoice_no_org_or_credits"}

    row, created = stripe_topup_idempotent(
        db,
        org,
        credits,
        session_id=invoice_id,
        note=f"plan={plan_id} subscription={sub_id} tax={invoice.get('tax')}",
        ref_type="stripe_invoice",
        reason="stripe_subscription",
    )
    patch_billing_profile(
        org,
        stripe_customer_id=customer or get_billing_profile(org).get("stripe_customer_id"),
        subscription_id=sub_id or get_billing_profile(org).get("subscription_id"),
        subscription_plan_id=plan_id or get_billing_profile(org).get("subscription_plan_id"),
        subscription_status="active",
    )
    db.commit()
    return {"ok": True, "created": created, "credits": get_credits(org), "invoice_id": invoice_id}


def _handle_subscription_event(db: Session, sub: dict, deleted: bool = False):
    meta = sub.get("metadata") or {}
    try:
        org_id = int(meta.get("org_id") or 0)
    except (TypeError, ValueError):
        org_id = 0
    org = db.query(Organization).filter(Organization.id == org_id).first() if org_id else None
    if org is None and sub.get("customer"):
        for o in db.query(Organization).all():
            if get_billing_profile(o).get("stripe_customer_id") == sub.get("customer"):
                org = o
                break
    if not org:
        return {"ok": True, "ignored": "sub_no_org"}
    status = "canceled" if deleted else (sub.get("status") or "active")
    plan_id = meta.get("plan_id")
    if not plan_id:
        items = (sub.get("items") or {}).get("data") or []
        if items:
            price = (items[0].get("price") or {}) if isinstance(items[0].get("price"), dict) else {}
            plan = get_plan_by_price(price.get("id") or "")
            if plan:
                plan_id = plan["id"]
    patch_billing_profile(
        org,
        subscription_id=None if deleted else sub.get("id"),
        subscription_status=status,
        subscription_plan_id=None if deleted else plan_id,
        stripe_customer_id=sub.get("customer") or get_billing_profile(org).get("stripe_customer_id"),
    )
    db.commit()
    return {"ok": True, "status": status, "org_id": org.id}


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

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        return _handle_checkout_completed(db, obj)
    if etype == "invoice.paid":
        return _handle_invoice_paid(db, obj)
    if etype == "customer.subscription.updated":
        return _handle_subscription_event(db, obj, deleted=False)
    if etype == "customer.subscription.deleted":
        return _handle_subscription_event(db, obj, deleted=True)
    if etype == "account.updated":
        org_id = apply_connect_account_updated(db, obj)
        return {"ok": True, "org_id": org_id}

    return {"ok": True, "ignored": etype}
