"""P14: Automerge-era pixel CRDT, FUSE FS, NFS parse, Stripe tax/connect extras."""

from pathlib import Path
from types import SimpleNamespace

from app.services.fuse_fs import StorageFuseFS
from app.services.os_mounts import nfs_mount_argv, parse_nfs_export
from app.services.pixel_crdt import paint_disk, pixel_key
from app.services.stripe_billing import (
    application_fee_cents,
    apply_checkout_extras,
)


def test_parse_nfs_export_ok():
    host, path = parse_nfs_export("nas.example.com:/exports/data")
    assert host == "nas.example.com"
    assert path == "/exports/data"


def test_parse_nfs_export_rejects_relative():
    try:
        parse_nfs_export("host:not-absolute")
        assert False, "should reject"
    except ValueError:
        pass


def test_nfs_mount_argv_darwin_or_linux():
    argv = nfs_mount_argv("nas:/export", "/mnt/dasshine/org1")
    assert "mount" in argv[0]
    assert "nas:/export" in argv
    assert "/mnt/dasshine/org1" in argv


def test_pixel_paint_and_erase():
    pix: dict[str, str] = {}
    paint_disk(pix, 10, 10, 2, "car")
    assert pixel_key(10, 10) in pix
    assert pix[pixel_key(10, 10)] == "car"
    paint_disk(pix, 10, 10, 2, "car", erase=True)
    assert pixel_key(10, 10) not in pix


def test_fuse_fs_readdir_read_and_jail(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("world", encoding="utf-8")
    fs = StorageFuseFS(tmp_path, read_only=True)
    names = fs.readdir("")
    assert "a.txt" in names
    assert "sub" in names
    data = fs.read("a.txt", 16, 0)
    assert data == b"hello"
    try:
        fs.read("../etc/passwd", 8, 0)
        assert False, "jail"
    except OSError:
        pass
    try:
        fs.write("a.txt", b"x", 0)
        assert False, "readonly"
    except OSError:
        pass


def test_application_fee_cents(monkeypatch):
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_APPLICATION_FEE_BPS", 1000)
    assert application_fee_cents(999) == 99


def test_apply_checkout_extras_tax(monkeypatch):
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_TAX_ENABLED", True)
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_CONNECT_ENABLED", False)
    kwargs = {
        "customer": "cus_1",
        "line_items": [{"price_data": {"unit_amount": 999, "currency": "usd"}}],
    }
    apply_checkout_extras(kwargs, org=None, amount_cents=999, mode="payment")
    assert kwargs["automatic_tax"]["enabled"] is True
    assert kwargs["line_items"][0]["price_data"]["tax_behavior"] == "exclusive"


def test_apply_checkout_extras_connect_destination(monkeypatch):
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_TAX_ENABLED", False)
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_CONNECT_ENABLED", True)
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr("app.services.stripe_billing.settings.STRIPE_APPLICATION_FEE_BPS", 1000)
    org = SimpleNamespace(
        quota={
            "stripe_connect_account_id": "acct_1",
            "connect_charges_enabled": True,
        }
    )
    kwargs: dict = {}
    apply_checkout_extras(kwargs, org=org, amount_cents=1000, mode="payment")
    assert kwargs["payment_intent_data"]["transfer_data"]["destination"] == "acct_1"
    assert kwargs["payment_intent_data"]["application_fee_amount"] == 100
