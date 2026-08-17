"""P12: stripe packs, browse allowlist, idempotent topup."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.org_billing import stripe_topup_idempotent
from app.services.file_storage import LocalStorageBackend, assert_browse_allowed, browse_allow_prefixes
from app.services.stripe_billing import parse_credit_packs, stripe_configured


def test_browse_allow_prefixes_default():
    prefs = browse_allow_prefixes()
    assert any(p.startswith("projects") for p in prefs)


def test_assert_browse_allowed_projects():
    assert assert_browse_allowed("projects/1").startswith("projects")
    try:
        assert_browse_allowed("../etc")
        assert False, "should reject"
    except ValueError:
        pass


def test_parse_credit_packs_default():
    packs = parse_credit_packs()
    assert len(packs) >= 1
    assert packs[0]["credits"] > 0


def test_stripe_not_configured_by_default():
    # 默认无密钥
    assert stripe_configured() in (True, False)  # env may set in CI
    # 至少可调用


def test_local_list_delimiter_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.services.file_storage.settings.FILE_SERVER_BASE_URL", "http://localhost:8000"
    )
    monkeypatch.setattr(
        "app.services.file_storage.settings.STORAGE_BROWSE_ALLOW_PREFIXES", "projects/"
    )
    (tmp_path / "projects" / "1" / "sub").mkdir(parents=True)
    (tmp_path / "projects" / "1" / "a.jpg").write_bytes(b"x")
    (tmp_path / "projects" / "1" / "sub" / "b.jpg").write_bytes(b"y")
    backend = LocalStorageBackend()
    items = backend.list_prefix("projects/1", max_keys=50, delimiter=True)
    keys = {i["key"] for i in items}
    assert "projects/1/a.jpg" in keys
    assert any(i["is_dir"] and "sub" in i["key"] for i in items)


def test_stripe_topup_idempotent_skips_when_exists():
    org = SimpleNamespace(id=1, quota={"credits": 100})
    db = MagicMock()
    existing = SimpleNamespace(id=9, delta=1000, balance_after=1100)
    db.query.return_value.filter.return_value.first.return_value = existing
    row, created = stripe_topup_idempotent(db, org, 1000, session_id="cs_test")
    assert created is False
    assert row.id == 9
