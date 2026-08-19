"""OIDC Authorization Code 登录（OpenID Connect）"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus

logger = logging.getLogger(__name__)


def oidc_configured() -> bool:
    return bool(
        settings.OIDC_ENABLED
        and settings.OIDC_ISSUER
        and settings.OIDC_CLIENT_ID
        and settings.OIDC_CLIENT_SECRET
    )


def _discovery(issuer: str) -> Dict[str, Any]:
    base = issuer.rstrip("/")
    url = f"{base}/.well-known/openid-configuration"
    with httpx.Client(timeout=15.0) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.json()


def build_authorize_url(state: Optional[str] = None) -> Tuple[str, str]:
    if not oidc_configured():
        raise RuntimeError("OIDC 未配置")
    meta = _discovery(settings.OIDC_ISSUER or "")
    st = state or secrets.token_urlsafe(24)
    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "response_type": "code",
        "scope": settings.OIDC_SCOPES,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "state": st,
    }
    auth_ep = meta.get("authorization_endpoint")
    if not auth_ep:
        raise RuntimeError("OIDC discovery 缺少 authorization_endpoint")
    return f"{auth_ep}?{urlencode(params)}", st


def exchange_code(code: str) -> Dict[str, Any]:
    if not oidc_configured():
        raise RuntimeError("OIDC 未配置")
    meta = _discovery(settings.OIDC_ISSUER or "")
    token_ep = meta.get("token_endpoint")
    userinfo_ep = meta.get("userinfo_endpoint")
    if not token_ep:
        raise RuntimeError("OIDC discovery 缺少 token_endpoint")

    with httpx.Client(timeout=20.0) as client:
        tr = client.post(
            token_ep,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OIDC_REDIRECT_URI,
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
            },
            headers={"Accept": "application/json"},
        )
        tr.raise_for_status()
        tokens = tr.json()
        access = tokens.get("access_token")
        if not access or not userinfo_ep:
            # 无 userinfo 时尝试 id_token 粗解析（仅取 claims 需 JWT 库；这里要求 userinfo）
            raise RuntimeError("OIDC 未返回 access_token 或无 userinfo_endpoint")
        ur = client.get(
            userinfo_ep,
            headers={"Authorization": f"Bearer {access}"},
        )
        ur.raise_for_status()
        return ur.json()


def upsert_oidc_user(db: Session, claims: Dict[str, Any]) -> User:
    sub = str(claims.get("sub") or "")
    email = (claims.get("email") or "").strip().lower()
    if not sub:
        raise ValueError("OIDC claims 缺少 sub")
    issuer = (settings.OIDC_ISSUER or "").rstrip("/")

    user = (
        db.query(User)
        .filter(User.oidc_sub == sub, User.oidc_issuer == issuer)
        .first()
    )
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oidc_sub = sub
            user.oidc_issuer = issuer

    if not user:
        base = (claims.get("preferred_username") or (email.split("@")[0] if email else f"oidc_{sub[:8]}"))
        username = str(base)[:50]
        i = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{str(base)[:40]}_{i}"
            i += 1
        user = User(
            username=username,
            email=email or f"{sub}@oidc.local",
            hashed_password=get_password_hash(secrets.token_urlsafe(32)),
            full_name=claims.get("name"),
            role=UserRole.ANNOTATOR,
            status=UserStatus.ACTIVE,
            oidc_sub=sub,
            oidc_issuer=issuer,
        )
        db.add(user)
        db.flush()
        from app.services.organization_service import OrganizationService

        OrganizationService(db).ensure_personal_org(user)
    return user
