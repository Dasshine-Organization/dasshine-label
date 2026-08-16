"""组织（多租户）API"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.organization_service import OrganizationService
from app.services.org_quota import normalize_quota

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = None


class OrgMemberAdd(BaseModel):
    user_id: int
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class OrgQuotaUpdate(BaseModel):
    max_projects: Optional[int] = Field(None, ge=0)
    max_tasks: Optional[int] = Field(None, ge=0)
    max_members: Optional[int] = Field(None, ge=0)


@router.get("")
def list_orgs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = OrganizationService(db)
    svc.ensure_personal_org(current_user)
    orgs = svc.list_for_user(current_user)
    return {
        "active_org_id": current_user.active_org_id,
        "items": [OrganizationService.to_dict(o, db) for o in orgs],
    }


@router.post("", status_code=201)
def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = OrganizationService(db).create(body.name, current_user, slug=body.slug)
    return OrganizationService.to_dict(org, db)


@router.post("/{org_id}/activate")
def activate_org(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = OrganizationService(db).activate(current_user, org_id)
    if not ok:
        raise HTTPException(status_code=403, detail="无权切换到该组织")
    return {"ok": True, "active_org_id": current_user.active_org_id}


@router.get("/{org_id}/quota")
def get_org_quota(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not current_user.is_admin and not svc.user_in_org(current_user.id, org_id):
        raise HTTPException(status_code=403, detail="无权查看配额")
    return OrganizationService.to_dict(org, db)


@router.put("/{org_id}/quota")
def update_org_quota(
    org_id: int,
    body: OrgQuotaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可调整配额")
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    current = normalize_quota(getattr(org, "quota", None))
    patch: Dict[str, Any] = body.model_dump(exclude_none=True)
    current.update(patch)
    org.quota = current
    db.commit()
    db.refresh(org)
    return OrganizationService.to_dict(org, db)


@router.get("/{org_id}/members")
def list_org_members(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not current_user.is_admin and not svc.user_in_org(current_user.id, org_id):
        raise HTTPException(status_code=403, detail="无权查看成员")
    return {"items": svc.get_members(org_id)}


@router.post("/{org_id}/members", status_code=201)
def add_org_member(
    org_id: int,
    body: OrgMemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权管理该组织")
    ok = svc.add_member(org_id, body.user_id, body.role)
    if not ok:
        raise HTTPException(status_code=400, detail="添加成员失败（可能已达配额上限）")
    return {"ok": True}
