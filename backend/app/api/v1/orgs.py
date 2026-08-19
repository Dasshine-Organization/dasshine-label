"""组织（多租户）API"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
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
    credits: Optional[int] = Field(None, ge=0)


class OrgTopupBody(BaseModel):
    amount: int = Field(..., ge=1, le=10_000_000)
    note: Optional[str] = None


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


class InviteAccept(BaseModel):
    token: str = Field(..., min_length=8)


@router.post("/invites/accept")
def accept_org_invite(
    body: InviteAccept,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """须挂在 /{org_id} 之前，避免 path 冲突"""
    from app.services.org_invites import accept_invite

    ok, msg, org = accept_invite(db, body.token, current_user)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    if org:
        OrganizationService(db).activate(current_user, org.id)
    db.commit()
    return {"ok": True, "message": msg, "organization_id": org.id if org else None}


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
    from app.services import audit

    audit.record(
        db,
        action="org.quota.update",
        actor_user_id=current_user.id,
        organization_id=org_id,
        detail=patch,
    )
    db.commit()
    db.refresh(org)
    return OrganizationService.to_dict(org, db)


@router.get("/{org_id}/billing")
def get_org_billing(
    org_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_billing import get_credits, list_ledger

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not current_user.is_admin and not svc.user_in_org(current_user.id, org_id):
        raise HTTPException(status_code=403, detail="无权查看计费")
    return {
        "organization_id": org_id,
        "credits": get_credits(org),
        "quota": normalize_quota(getattr(org, "quota", None)),
        "ledger": list_ledger(db, org_id, limit=limit),
    }


@router.post("/{org_id}/billing/topup")
def topup_org_billing(
    org_id: int,
    body: OrgTopupBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_billing import get_credits, topup

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可充值")
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    row = topup(db, org, body.amount, created_by_id=current_user.id, note=body.note)
    db.commit()
    return {
        "ok": True,
        "credits": get_credits(org),
        "entry": {
            "id": row.id,
            "delta": row.delta,
            "balance_after": row.balance_after,
            "reason": row.reason,
        },
    }


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
    from app.services import audit

    audit.record(
        db,
        action="org.member.add",
        actor_user_id=current_user.id,
        organization_id=org_id,
        resource_type="user",
        resource_id=body.user_id,
        detail={"role": body.role},
    )
    db.commit()
    return {"ok": True}


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=120)


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=8, max_length=1000)
    events: Optional[List[str]] = None
    secret: Optional[str] = None


@router.post("/{org_id}/invites", status_code=201)
def create_org_invite(
    org_id: int,
    body: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_invites import create_invite, invite_to_dict

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权管理该组织")
    invite, token = create_invite(
        db, org, email=str(body.email), role=body.role, invited_by=current_user
    )
    db.commit()
    return invite_to_dict(invite, include_token=True, token=token)


@router.get("/{org_id}/invites")
def list_org_invites(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_invites import invite_to_dict, list_invites

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权查看邀请")
    return {"items": [invite_to_dict(i) for i in list_invites(db, org_id)]}


@router.get("/{org_id}/api-keys")
def list_org_api_keys(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_api_keys import api_key_to_dict, list_api_keys

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权查看 API Key")
    return {"items": [api_key_to_dict(k) for k in list_api_keys(db, org_id)]}


@router.post("/{org_id}/api-keys", status_code=201)
def create_org_api_key(
    org_id: int,
    body: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_api_keys import api_key_to_dict, create_api_key

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权创建 API Key")
    row, raw = create_api_key(db, org, name=body.name, created_by=current_user)
    db.commit()
    out = api_key_to_dict(row)
    out["key"] = raw  # 仅创建时返回一次
    return out


@router.delete("/{org_id}/api-keys/{key_id}")
def revoke_org_api_key(
    org_id: int,
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.org_api_keys import revoke_api_key

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权撤销 API Key")
    if not revoke_api_key(db, org, key_id, current_user):
        raise HTTPException(status_code=404, detail="Key 不存在或已撤销")
    db.commit()
    return {"ok": True}


@router.get("/{org_id}/webhooks")
def list_org_webhooks(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.webhooks import list_webhooks, webhook_to_dict

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权查看 Webhook")
    return {"items": [webhook_to_dict(w) for w in list_webhooks(db, org_id)]}


@router.post("/{org_id}/webhooks", status_code=201)
def create_org_webhook(
    org_id: int,
    body: WebhookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.webhooks import create_webhook, webhook_to_dict

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权创建 Webhook")
    row = create_webhook(
        db,
        org,
        url=body.url,
        events=body.events or [],
        created_by=current_user,
        secret=body.secret,
    )
    db.commit()
    out = webhook_to_dict(row)
    out["secret"] = row.secret
    return out


@router.delete("/{org_id}/webhooks/{webhook_id}")
def delete_org_webhook(
    org_id: int,
    webhook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.webhooks import delete_webhook

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org):
        raise HTTPException(status_code=403, detail="无权删除 Webhook")
    if not delete_webhook(db, org, webhook_id, current_user):
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    db.commit()
    return {"ok": True}


@router.get("/{org_id}/audit")
def list_org_audit(
    org_id: int,
    action: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.audit import list_events, to_dict

    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="组织不存在")
    if not svc.can_manage_org(current_user, org) and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="无权查看审计日志")
    items = list_events(db, organization_id=org_id, action=action, limit=limit)
    return {"total": len(items), "items": [to_dict(e) for e in items]}
