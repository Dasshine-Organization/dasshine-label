"""
Stripe：一次性积分包 + 订阅 Checkout + Customer Portal。
未配置 STRIPE_SECRET_KEY 时不可用。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.organization import Organization

logger = logging.getLogger("dasshine.stripe")


def stripe_configured() -> bool:
    return bool((settings.STRIPE_SECRET_KEY or "").strip())


def _stripe():
    try:
        import stripe
    except ImportError as e:
        raise RuntimeError("未安装 stripe，请执行: pip install stripe") from e
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def parse_credit_packs() -> List[Dict[str, Any]]:
    raw = (settings.STRIPE_CREDIT_PACKS or "").strip() or "[]"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("STRIPE_CREDIT_PACKS invalid JSON")
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        credits = int(item.get("credits") or 0)
        cents = int(item.get("amount_cents") or 0)
        if not pid or credits <= 0 or cents <= 0:
            continue
        out.append(
            {
                "id": pid,
                "credits": credits,
                "amount_cents": cents,
                "currency": str(item.get("currency") or "usd").lower(),
                "label": str(item.get("label") or f"{credits} 积分"),
            }
        )
    return out


def parse_price_plans() -> List[Dict[str, Any]]:
    raw = (getattr(settings, "STRIPE_PRICE_PLANS", None) or "").strip() or "[]"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("STRIPE_PRICE_PLANS invalid JSON")
        return []
    if not isinstance(data, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        price_id = str(item.get("price_id") or "").strip()
        credits = int(item.get("credits_per_month") or 0)
        if not pid or not price_id:
            continue
        out.append(
            {
                "id": pid,
                "price_id": price_id,
                "credits_per_month": max(0, credits),
                "label": str(item.get("label") or pid),
            }
        )
    return out


def get_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    for p in parse_credit_packs():
        if p["id"] == pack_id:
            return p
    return None


def get_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    for p in parse_price_plans():
        if p["id"] == plan_id:
            return p
    return None


def get_plan_by_price(price_id: str) -> Optional[Dict[str, Any]]:
    for p in parse_price_plans():
        if p["price_id"] == price_id:
            return p
    return None


def _quota_dict(org: Organization) -> Dict[str, Any]:
    return dict(org.quota) if isinstance(org.quota, dict) else {}


def get_billing_profile(org: Organization) -> Dict[str, Any]:
    q = _quota_dict(org)
    return {
        "stripe_customer_id": q.get("stripe_customer_id"),
        "subscription_status": q.get("subscription_status") or "none",
        "subscription_plan_id": q.get("subscription_plan_id"),
        "subscription_id": q.get("subscription_id"),
        "stripe_connect_account_id": q.get("stripe_connect_account_id"),
        "connect_charges_enabled": bool(q.get("connect_charges_enabled")),
        "connect_payouts_enabled": bool(q.get("connect_payouts_enabled")),
        "connect_details_submitted": bool(q.get("connect_details_submitted")),
    }


def tax_enabled() -> bool:
    return bool(getattr(settings, "STRIPE_TAX_ENABLED", False))


def connect_enabled() -> bool:
    return stripe_configured() and bool(getattr(settings, "STRIPE_CONNECT_ENABLED", False))


def application_fee_cents(amount_cents: int) -> int:
    bps = int(getattr(settings, "STRIPE_APPLICATION_FEE_BPS", 0) or 0)
    return max(0, int(amount_cents) * bps // 10_000)


def apply_checkout_extras(
    kwargs: Dict[str, Any],
    *,
    org: Optional[Organization] = None,
    amount_cents: Optional[int] = None,
    mode: str = "payment",
) -> Dict[str, Any]:
    if tax_enabled():
        kwargs["automatic_tax"] = {"enabled": True}
        kwargs["tax_id_collection"] = {"enabled": True}
        kwargs["billing_address_collection"] = "required"
        if kwargs.get("customer"):
            kwargs.setdefault("customer_update", {"address": "auto", "name": "auto"})
        for item in kwargs.get("line_items") or []:
            if isinstance(item, dict) and isinstance(item.get("price_data"), dict):
                item["price_data"]["tax_behavior"] = "exclusive"
    if org is not None and connect_enabled():
        profile = get_billing_profile(org)
        dest = profile.get("stripe_connect_account_id")
        if dest and profile.get("connect_charges_enabled"):
            bps = int(getattr(settings, "STRIPE_APPLICATION_FEE_BPS", 0) or 0)
            if mode == "payment" and amount_cents:
                kwargs["payment_intent_data"] = {
                    "application_fee_amount": application_fee_cents(amount_cents),
                    "transfer_data": {"destination": dest},
                }
            elif mode == "subscription":
                sub = dict(kwargs.get("subscription_data") or {})
                if bps > 0:
                    sub["application_fee_percent"] = bps / 100.0
                sub["transfer_data"] = {"destination": dest}
                kwargs["subscription_data"] = sub
    return kwargs


def patch_billing_profile(org: Organization, **fields: Any) -> None:
    q = _quota_dict(org)
    for k, v in fields.items():
        if v is None:
            q.pop(k, None)
        else:
            q[k] = v
    org.quota = q


def ensure_customer(
    db: Session,
    org: Organization,
    *,
    email: Optional[str] = None,
) -> str:
    profile = get_billing_profile(org)
    existing = profile.get("stripe_customer_id")
    if existing:
        return str(existing)
    stripe = _stripe()
    customer = stripe.Customer.create(
        email=email or None,
        name=org.name,
        metadata={"org_id": str(org.id), "org_slug": org.slug},
    )
    patch_billing_profile(org, stripe_customer_id=customer.id)
    db.add(org)
    db.commit()
    db.refresh(org)
    return customer.id


def create_checkout_session(
    *,
    org_id: int,
    pack_id: str,
    user_id: int,
    customer_email: Optional[str] = None,
    customer_id: Optional[str] = None,
    org: Optional[Organization] = None,
) -> Dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    pack = get_pack(pack_id)
    if not pack:
        raise ValueError(f"未知积分包: {pack_id}")

    stripe = _stripe()
    kwargs: Dict[str, Any] = {
        "mode": "payment",
        "success_url": settings.STRIPE_SUCCESS_URL,
        "cancel_url": settings.STRIPE_CANCEL_URL,
        "line_items": [
            {
                "price_data": {
                    "currency": pack["currency"],
                    "unit_amount": pack["amount_cents"],
                    "product_data": {"name": pack["label"]},
                },
                "quantity": 1,
            }
        ],
        "metadata": {
            "org_id": str(org_id),
            "pack_id": pack["id"],
            "credits": str(pack["credits"]),
            "user_id": str(user_id),
            "kind": "one_time",
        },
        "client_reference_id": f"org-{org_id}",
    }
    if customer_id:
        kwargs["customer"] = customer_id
    elif customer_email:
        kwargs["customer_email"] = customer_email
    apply_checkout_extras(
        kwargs, org=org, amount_cents=pack["amount_cents"], mode="payment"
    )
    session = stripe.checkout.Session.create(**kwargs)
    return {
        "session_id": session.id,
        "url": session.url,
        "pack": pack,
    }


def create_subscription_checkout(
    *,
    org: Organization,
    plan_id: str,
    user_id: int,
    customer_email: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    plan = get_plan(plan_id)
    if not plan:
        raise ValueError(f"未知订阅计划: {plan_id}")
    if db is None:
        raise RuntimeError("db required")
    customer_id = ensure_customer(db, org, email=customer_email)
    stripe = _stripe()
    kwargs: Dict[str, Any] = {
        "mode": "subscription",
        "customer": customer_id,
        "success_url": settings.STRIPE_SUCCESS_URL,
        "cancel_url": settings.STRIPE_CANCEL_URL,
        "line_items": [{"price": plan["price_id"], "quantity": 1}],
        "metadata": {
            "org_id": str(org.id),
            "plan_id": plan["id"],
            "credits_per_month": str(plan["credits_per_month"]),
            "user_id": str(user_id),
            "kind": "subscription",
        },
        "subscription_data": {
            "metadata": {
                "org_id": str(org.id),
                "plan_id": plan["id"],
                "credits_per_month": str(plan["credits_per_month"]),
            }
        },
        "client_reference_id": f"org-{org.id}-sub",
    }
    apply_checkout_extras(kwargs, org=org, mode="subscription")
    session = stripe.checkout.Session.create(**kwargs)
    return {
        "session_id": session.id,
        "url": session.url,
        "plan": plan,
    }


def create_portal_session(*, org: Organization, db: Session) -> Dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    customer_id = get_billing_profile(org).get("stripe_customer_id")
    if not customer_id:
        raise ValueError("组织尚未绑定 Stripe 客户，请先订阅或充值")
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=getattr(settings, "STRIPE_PORTAL_RETURN_URL", None)
        or settings.STRIPE_SUCCESS_URL,
    )
    return {"url": session.url}


def construct_webhook_event(payload: bytes, sig_header: str):
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    secret = (settings.STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret:
        raise RuntimeError("未配置 STRIPE_WEBHOOK_SECRET")
    stripe = _stripe()
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def create_connect_onboarding(
    db: Session,
    org: Organization,
    *,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    if not connect_enabled():
        raise RuntimeError("未启用 Stripe Connect")
    stripe = _stripe()
    profile = get_billing_profile(org)
    account_id = profile.get("stripe_connect_account_id")
    if not account_id:
        account = stripe.Account.create(
            type="express",
            country=(getattr(settings, "STRIPE_CONNECT_COUNTRY", None) or "US"),
            email=email or None,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            metadata={"org_id": str(org.id), "org_slug": org.slug},
            business_profile={"name": org.name},
        )
        account_id = account.id
        patch_billing_profile(org, stripe_connect_account_id=account_id)
        db.add(org)
        db.commit()
        db.refresh(org)
    return_url = (
        getattr(settings, "STRIPE_CONNECT_RETURN_URL", None) or settings.STRIPE_SUCCESS_URL
    )
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=return_url,
        return_url=return_url,
        type="account_onboarding",
    )
    return {"url": link.url, "account_id": account_id}


def create_connect_login(org: Organization) -> Dict[str, Any]:
    if not connect_enabled():
        raise RuntimeError("未启用 Stripe Connect")
    account_id = get_billing_profile(org).get("stripe_connect_account_id")
    if not account_id:
        raise ValueError("尚未创建 Connect 账户")
    stripe = _stripe()
    link = stripe.Account.create_login_link(account_id)
    return {"url": link.url, "account_id": account_id}


def apply_connect_account_updated(db: Session, account: dict) -> Optional[int]:
    acc_id = account.get("id")
    if not acc_id:
        return None
    for org in db.query(Organization).all():
        if get_billing_profile(org).get("stripe_connect_account_id") != acc_id:
            continue
        patch_billing_profile(
            org,
            connect_charges_enabled=bool(account.get("charges_enabled")),
            connect_payouts_enabled=bool(account.get("payouts_enabled")),
            connect_details_submitted=bool(account.get("details_submitted")),
        )
        db.add(org)
        db.commit()
        return org.id
    return None
