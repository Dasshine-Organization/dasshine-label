"""组织邮件邀请"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enterprise import OrgInvite
from app.models.organization import Organization
from app.models.user import User
from app.services import audit
from app.services.mailer import send_mail
from app.services.organization_service import OrganizationService


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_invite(
    db: Session,
    org: Organization,
    *,
    email: str,
    role: str,
    invited_by: User,
) -> Tuple[OrgInvite, str]:
    email_n = email.strip().lower()
    if role not in ("owner", "admin", "member"):
        role = "member"
    raw = secrets.token_urlsafe(32)
    invite = OrgInvite(
        organization_id=org.id,
        email=email_n,
        role=role,
        token_hash=_hash_token(raw),
        invited_by_id=invited_by.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=max(1, settings.ORG_INVITE_EXPIRE_DAYS)),
    )
    db.add(invite)
    db.flush()
    audit.record(
        db,
        action="org.invite.create",
        actor_user_id=invited_by.id,
        organization_id=org.id,
        resource_type="org_invite",
        resource_id=invite.id,
        detail={"email": email_n, "role": role},
    )
    accept_url = f"{settings.FRONTEND_URL.rstrip('/')}/invite/{raw}"
    send_mail(
        email_n,
        f"邀请加入组织 {org.name}",
        f"你被邀请以「{role}」加入 {org.name}。\n\n打开链接接受：\n{accept_url}\n\n"
        f"{settings.ORG_INVITE_EXPIRE_DAYS} 天内有效。",
    )
    return invite, raw


def list_invites(db: Session, org_id: int) -> List[OrgInvite]:
    return (
        db.query(OrgInvite)
        .filter(OrgInvite.organization_id == org_id)
        .order_by(OrgInvite.id.desc())
        .limit(100)
        .all()
    )


def accept_invite(db: Session, token: str, user: User) -> Tuple[bool, str, Optional[Organization]]:
    th = _hash_token(token)
    invite = db.query(OrgInvite).filter(OrgInvite.token_hash == th).first()
    if not invite:
        return False, "邀请无效", None
    if invite.accepted_at:
        return False, "邀请已使用", None
    now = datetime.now(timezone.utc)
    exp = invite.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        return False, "邀请已过期", None
    if (user.email or "").strip().lower() != invite.email:
        return False, "请使用被邀请的邮箱登录后接受", None

    org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
    if not org:
        return False, "组织不存在", None

    svc = OrganizationService(db)
    if not svc.user_in_org(user.id, org.id):
        ok = svc.add_member(org.id, user.id, invite.role)
        if not ok:
            return False, "加入失败（可能已达成员配额）", org

    invite.accepted_at = now
    invite.accepted_by_id = user.id
    audit.record(
        db,
        action="org.invite.accept",
        actor_user_id=user.id,
        organization_id=org.id,
        resource_type="org_invite",
        resource_id=invite.id,
        detail={"email": invite.email, "role": invite.role},
    )
    db.flush()
    return True, "已加入组织", org


def invite_to_dict(inv: OrgInvite, *, include_token: bool = False, token: str = "") -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "id": inv.id,
        "organization_id": inv.organization_id,
        "email": inv.email,
        "role": inv.role,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
        "invited_by_id": inv.invited_by_id,
    }
    if include_token and token:
        d["token"] = token
        d["accept_url"] = f"{settings.FRONTEND_URL.rstrip('/')}/invite/{token}"
    return d
