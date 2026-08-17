"""P11: billing ledger, storage browse, collab helpers."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.org_billing import (
    check_can_spend,
    export_cost,
    get_credits,
    import_cost,
    set_credits,
    spend,
)
from app.services.org_quota import DEFAULT_QUOTA, normalize_quota
from app.services.file_storage import LocalStorageBackend


def test_quota_includes_default_credits():
    assert "credits" in DEFAULT_QUOTA
    assert normalize_quota(None)["credits"] == DEFAULT_QUOTA["credits"]
    assert normalize_quota({"credits": 42})["credits"] == 42


def test_billing_credits_and_check():
    org = SimpleNamespace(id=1, quota={"credits": 100, "max_projects": 10})
    assert get_credits(org) == 100
    set_credits(org, 70)
    assert get_credits(org) == 70
    ok, _ = check_can_spend(org, 30)
    assert ok
    ok2, msg = check_can_spend(org, 1000)
    assert not ok2
    assert "不足" in msg


def test_billing_spend_when_disabled(monkeypatch):
    monkeypatch.setattr("app.services.org_billing.settings.BILLING_ENABLED", False)
    org = SimpleNamespace(id=1, quota={"credits": 0})
    ok, msg = spend(MagicMock(), org, 50, reason="import")
    assert ok and msg == ""


def test_import_export_cost():
    assert import_cost(10) >= 10
    assert export_cost() >= 1


def test_local_list_prefix(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.services.file_storage.settings.FILE_SERVER_BASE_URL", "http://localhost:8000"
    )
    monkeypatch.setattr(
        "app.services.file_storage.settings.STORAGE_BROWSE_ALLOW_PREFIXES", "projects/"
    )
    root = tmp_path / "projects" / "1"
    root.mkdir(parents=True)
    (root / "a.jpg").write_bytes(b"x")
    (root / "b.txt").write_text("t", encoding="utf-8")
    backend = LocalStorageBackend()
    items = backend.list_prefix("projects/1", max_keys=50, delimiter=False)
    keys = {i["key"] for i in items}
    assert "projects/1/a.jpg" in keys
    assert any(i["url"] and i["url"].startswith("http://localhost:8000/uploads/") for i in items)


def test_collab_b64_roundtrip():
    from app.services.collab_room import b64, from_b64

    raw = b"\x00\x01yjs"
    assert from_b64(b64(raw)) == raw


def test_set_credits_preserves_other_keys():
    org = SimpleNamespace(quota={"max_projects": 3, "credits": 1})
    set_credits(org, 9)
    assert org.quota["max_projects"] == 3
    assert org.quota["credits"] == 9
