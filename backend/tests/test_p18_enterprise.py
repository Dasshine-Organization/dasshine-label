"""P18：企业接入 — 注册开关、邀请/API Key hash、Webhook 签名、OIDC 探测。"""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

from app.core.config import settings
from app.services.org_api_keys import _hash_key, api_key_to_dict
from app.services.org_invites import _hash_token
from app.services.oidc import oidc_configured
from app.services.webhooks import SUPPORTED_EVENTS, _sign, deliver_one
from app.services.audit import to_dict


def test_register_flag_default_on():
    assert settings.AUTH_REGISTER_ENABLED is True


def test_oidc_configured_false_without_env(monkeypatch):
    monkeypatch.setattr(settings, "OIDC_ENABLED", True)
    monkeypatch.setattr(settings, "OIDC_ISSUER", None)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "x")
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "y")
    assert oidc_configured() is False


def test_invite_token_hash():
    raw = "invite-token-example"
    assert _hash_token(raw) == hashlib.sha256(raw.encode()).hexdigest()


def test_api_key_hash_stable():
    raw = "ds_testkey_abcdefghijklmnopqrstuvwxyz012345"
    assert _hash_key(raw) == hashlib.sha256(raw.encode()).hexdigest()
    row = SimpleNamespace(
        id=1,
        name="default",
        prefix=raw[:10],
        created_by_id=7,
        last_used_at=None,
        revoked_at=None,
        created_at=None,
    )
    assert api_key_to_dict(row)["prefix"] == raw[:10]


def test_webhook_events_and_signature():
    body = b'{"event":"task.submitted"}'
    secret = "s3cret"
    sig = _sign(secret, body)
    assert hmac.compare_digest(
        sig,
        hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
    )
    assert set(SUPPORTED_EVENTS) >= {"task.submitted", "review.decided", "export.done"}


def test_deliver_one_posts_signed(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 204
        text = ""

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def post(self, url, content=None, headers=None):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return FakeResp()

    monkeypatch.setattr("app.services.webhooks.httpx.Client", FakeClient)
    hook = SimpleNamespace(id=1, organization_id=9, url="https://hooks.example/x", secret="abc")
    ok = deliver_one(hook, "export.done", {"project_id": 1})
    assert ok
    assert captured["headers"]["X-Dasshine-Event"] == "export.done"
    assert captured["headers"]["X-Dasshine-Signature"].startswith("sha256=")
    payload = json.loads(captured["content"])
    assert payload["event"] == "export.done"
    assert payload["organization_id"] == 9


def test_audit_to_dict():
    ev = SimpleNamespace(
        id=1,
        organization_id=2,
        actor_user_id=3,
        action="auth.login",
        resource_type=None,
        resource_id=None,
        detail={"method": "password"},
        ip="127.0.0.1",
        created_at=None,
    )
    d = to_dict(ev)
    assert d["action"] == "auth.login"
    assert d["detail"]["method"] == "password"
