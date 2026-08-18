"""P13: subscription plans, storage mounts resolve, billing profile."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.org_billing import stripe_topup_idempotent
from app.services.storage_mounts import resolve_mount_prefix
from app.services.stripe_billing import (
    get_billing_profile,
    get_plan,
    parse_price_plans,
    patch_billing_profile,
)


def test_parse_price_plans(monkeypatch):
    monkeypatch.setattr(
        "app.services.stripe_billing.settings.STRIPE_PRICE_PLANS",
        '[{"id":"plan_pro","price_id":"price_abc","credits_per_month":5000,"label":"Pro"}]',
    )
    plans = parse_price_plans()
    assert len(plans) == 1
    assert plans[0]["id"] == "plan_pro"
    assert plans[0]["credits_per_month"] == 5000
    assert get_plan("plan_pro")["price_id"] == "price_abc"


def test_parse_price_plans_skips_invalid(monkeypatch):
    monkeypatch.setattr(
        "app.services.stripe_billing.settings.STRIPE_PRICE_PLANS",
        '[{"id":"bad"},{"id":"ok","price_id":"price_x","credits_per_month":10}]',
    )
    plans = parse_price_plans()
    assert len(plans) == 1
    assert plans[0]["id"] == "ok"


def test_billing_profile_roundtrip():
    org = SimpleNamespace(quota={})
    patch_billing_profile(
        org,
        stripe_customer_id="cus_1",
        subscription_status="active",
        subscription_plan_id="plan_pro",
        subscription_id="sub_1",
    )
    profile = get_billing_profile(org)
    assert profile["stripe_customer_id"] == "cus_1"
    assert profile["subscription_status"] == "active"
    assert profile["subscription_plan_id"] == "plan_pro"
    assert profile["subscription_id"] == "sub_1"


def test_resolve_mount_prefix(monkeypatch):
    monkeypatch.setattr(
        "app.services.storage_mounts.assert_browse_allowed",
        lambda p: p.replace("\\", "/").lstrip("/"),
    )
    mount = SimpleNamespace(enabled=True, root_prefix="projects/1/", kind="local_prefix")
    assert resolve_mount_prefix(mount, "") == "projects/1"
    assert resolve_mount_prefix(mount, "raw/a") == "projects/1/raw/a"


def test_resolve_mount_disabled():
    mount = SimpleNamespace(enabled=False, root_prefix="projects/1/")
    try:
        resolve_mount_prefix(mount, "")
        assert False, "should raise"
    except ValueError:
        pass


def test_stripe_invoice_topup_idempotent():
    org = SimpleNamespace(id=1, quota={"credits": 100})
    db = MagicMock()
    existing = SimpleNamespace(id=9, delta=5000, balance_after=5100)
    db.query.return_value.filter.return_value.first.return_value = existing
    row, created = stripe_topup_idempotent(
        db,
        org,
        5000,
        session_id="in_test",
        ref_type="stripe_invoice",
        reason="subscription monthly",
    )
    assert created is False
    assert row.id == 9
