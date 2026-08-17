"""
Stripe Checkout 一次性积分包。
未配置 STRIPE_SECRET_KEY 时不可用。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("dasshine.stripe")


def stripe_configured() -> bool:
    return bool((settings.STRIPE_SECRET_KEY or "").strip())


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


def get_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    for p in parse_credit_packs():
        if p["id"] == pack_id:
            return p
    return None


def create_checkout_session(
    *,
    org_id: int,
    pack_id: str,
    user_id: int,
    customer_email: Optional[str] = None,
) -> Dict[str, Any]:
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    pack = get_pack(pack_id)
    if not pack:
        raise ValueError(f"未知积分包: {pack_id}")

    try:
        import stripe
    except ImportError as e:
        raise RuntimeError("未安装 stripe，请执行: pip install stripe") from e

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
        line_items=[
            {
                "price_data": {
                    "currency": pack["currency"],
                    "unit_amount": pack["amount_cents"],
                    "product_data": {"name": pack["label"]},
                },
                "quantity": 1,
            }
        ],
        metadata={
            "org_id": str(org_id),
            "pack_id": pack["id"],
            "credits": str(pack["credits"]),
            "user_id": str(user_id),
        },
        client_reference_id=f"org-{org_id}",
        customer_email=customer_email or None,
    )
    return {
        "session_id": session.id,
        "url": session.url,
        "pack": pack,
    }


def construct_webhook_event(payload: bytes, sig_header: str):
    if not stripe_configured():
        raise RuntimeError("未配置 STRIPE_SECRET_KEY")
    secret = (settings.STRIPE_WEBHOOK_SECRET or "").strip()
    if not secret:
        raise RuntimeError("未配置 STRIPE_WEBHOOK_SECRET")
    try:
        import stripe
    except ImportError as e:
        raise RuntimeError("未安装 stripe") from e
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Webhook.construct_event(payload, sig_header, secret)
