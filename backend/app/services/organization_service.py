"""
组织服务：创建、成员、当前组织、项目作用域。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.organization import Organization, OrganizationMember
from app.models.user import User, UserRole


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\-]+", "-", (name or "").strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return (s or "org")[:72]


class OrganizationService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user: User) -> List[Organization]:
        if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            return self.db.query(Organization).order_by(Organization.id.asc()).all()
        rows = (
            self.db.query(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .filter(OrganizationMember.user_id == user.id)
            .order_by(Organization.id.asc())
            .all()
        )
        return rows

    def get(self, org_id: int) -> Optional[Organization]:
        return self.db.query(Organization).filter(Organization.id == org_id).first()

    def user_in_org(self, user_id: int, org_id: int) -> bool:
        return (
            self.db.query(OrganizationMember)
            .filter(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == org_id,
            )
            .first()
            is not None
        )

    def can_manage_org(self, user: User, org: Organization) -> bool:
        if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            return True
        m = (
            self.db.query(OrganizationMember)
            .filter(
                OrganizationMember.user_id == user.id,
                OrganizationMember.organization_id == org.id,
            )
            .first()
        )
        return bool(m and m.role in ("owner", "admin"))

    def create(self, name: str, creator: User, slug: Optional[str] = None) -> Organization:
        base = _slugify(slug or name)
        candidate = base
        i = 1
        while self.db.query(Organization).filter(Organization.slug == candidate).first():
            candidate = f"{base}-{i}"[:80]
            i += 1
        org = Organization(name=name.strip() or candidate, slug=candidate, created_by_id=creator.id)
        self.db.add(org)
        self.db.flush()
        self.db.add(
            OrganizationMember(organization_id=org.id, user_id=creator.id, role="owner")
        )
        if creator.active_org_id is None:
            creator.active_org_id = org.id
        self.db.commit()
        self.db.refresh(org)
        return org

    def ensure_personal_org(self, user: User) -> Organization:
        existing = self.list_for_user(user)
        if existing:
            if user.active_org_id is None:
                user.active_org_id = existing[0].id
                self.db.commit()
            return existing[0]
        return self.create(f"{user.username} 的组织", user, slug=f"user-{user.id}")

    def add_member(self, org_id: int, user_id: int, role: str = "member") -> bool:
        if not self.get(org_id):
            return False
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        if self.user_in_org(user_id, org_id):
            return True
        self.db.add(
            OrganizationMember(organization_id=org_id, user_id=user_id, role=role or "member")
        )
        self.db.commit()
        return True

    def activate(self, user: User, org_id: int) -> bool:
        if user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
            if not self.user_in_org(user.id, org_id):
                return False
        if not self.get(org_id):
            return False
        user.active_org_id = org_id
        self.db.commit()
        return True

    def get_members(self, org_id: int) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(OrganizationMember)
            .filter(OrganizationMember.organization_id == org_id)
            .all()
        )
        out = []
        for m in rows:
            u = self.db.query(User).filter(User.id == m.user_id).first()
            if not u:
                continue
            out.append(
                {
                    "user_id": u.id,
                    "username": u.username,
                    "role": m.role,
                    "email": u.email,
                }
            )
        return out

    @staticmethod
    def to_dict(org: Organization) -> Dict[str, Any]:
        return {
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "created_by_id": org.created_by_id,
        }
