"""组织 API Key（入库仅存 hash）"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.enterprise import OrgApiKey
from app.models.organization import Organization
from app.models.user import User
from app.services import audit


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_api_key(
    db: Session,
    org: Organization,
    *,
    name: str,
    created_by: User,
) -> Tuple[OrgApiKey, str]:
    raw = f"ds_{secrets.token_urlsafe(32)}"
    prefix = raw[:10]
    row = OrgApiKey(
        organization_id=org.id,
        name=(name or "default").strip()[:120],
        prefix=prefix,
        key_hash=_hash_key(raw),
        created_by_id=created_by.id,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        action="org.api_key.create",
        actor_user_id=created_by.id,
        organization_id=org.id,
        resource_type="org_api_key",
        resource_id=row.id,
        detail={"name": row.name, "prefix": prefix},
    )
    return row, raw


def list_api_keys(db: Session, org_id: int) -> List[OrgApiKey]:
    return (
        db.query(OrgApiKey)
        .filter(OrgApiKey.organization_id == org_id)
        .order_by(OrgApiKey.id.desc())
        .all()
    )


def revoke_api_key(db: Session, org: Organization, key_id: int, actor: User) -> bool:
    row = (
        db.query(OrgApiKey)
        .filter(OrgApiKey.id == key_id, OrgApiKey.organization_id == org.id)
        .first()
    )
    if not row or row.revoked_at:
        return False
    row.revoked_at = datetime.now(timezone.utc)
    audit.record(
        db,
        action="org.api_key.revoke",
        actor_user_id=actor.id,
        organization_id=org.id,
        resource_type="org_api_key",
        resource_id=row.id,
        detail={"prefix": row.prefix},
    )
    return True


def resolve_api_key(db: Session, raw: str) -> Optional[Tuple[OrgApiKey, Organization]]:
    if not raw or not raw.startswith("ds_"):
        return None
    row = (
        db.query(OrgApiKey)
        .filter(OrgApiKey.key_hash == _hash_key(raw), OrgApiKey.revoked_at.is_(None))
        .first()
    )
    if not row:
        return None
    org = db.query(Organization).filter(Organization.id == row.organization_id).first()
    if not org:
        return None
    row.last_used_at = datetime.now(timezone.utc)
    return row, org


def api_key_to_dict(row: OrgApiKey) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "prefix": row.prefix,
        "created_by_id": row.created_by_id,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
