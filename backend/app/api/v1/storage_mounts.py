"""组织存储挂载 API（含 NFS/FUSE 内核挂载）。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.file_storage import FileStorageService
from app.services.organization_service import OrganizationService
from app.services.os_mounts import list_kernel_mounts, os_mount_enabled, run_os_mount, run_os_umount
from app.services.storage_mounts import (
    attach_os_mount,
    create_mount,
    delete_mount,
    get_mount,
    list_mounts,
    list_os_mount_entries,
    mount_to_dict,
    resolve_mount_prefix,
)

router = APIRouter(tags=["storage-mounts"])


class MountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    root_prefix: str = Field(..., min_length=1, max_length=512)
    kind: str = Field(default="local_prefix")
    read_only: bool = True
    options: Optional[Dict[str, Any]] = None


class OsAttachBody(BaseModel):
    os_mount_point: str = Field(..., min_length=1, max_length=512)


class OsMountBody(BaseModel):
    nfs_export: str = Field(..., min_length=3, max_length=512)
    os_mount_point: str = Field(..., min_length=1, max_length=512)
    options: str = Field(default="ro,hard,intr", max_length=120)


def _require_org_member(db: Session, org_id: int, user: User):
    svc = OrganizationService(db)
    org = svc.get(org_id)
    if not org:
        raise HTTPException(404, "组织不存在")
    if not user.is_admin and not svc.user_in_org(user.id, org_id):
        raise HTTPException(403, "无权访问该组织")
    return org, svc


@router.get("/storage/os-mounts")
def get_kernel_mounts(current_user: User = Depends(get_current_user)):
    return {
        "os_mount_enabled": os_mount_enabled(),
        "items": list_kernel_mounts(),
    }


@router.get("/orgs/{org_id}/storage-mounts")
def get_org_mounts(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_member(db, org_id, current_user)
    items = list_mounts(db, org_id)
    return {"items": [mount_to_dict(m) for m in items]}


@router.post("/orgs/{org_id}/storage-mounts", status_code=201)
def post_org_mount(
    org_id: int,
    body: MountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, svc = _require_org_member(db, org_id, current_user)
    if not current_user.is_admin and not svc.can_manage_org(current_user, org):
        raise HTTPException(403, "无权管理该组织挂载")
    try:
        row = create_mount(
            db,
            org_id=org_id,
            name=body.name,
            root_prefix=body.root_prefix,
            kind=body.kind,
            read_only=body.read_only,
            created_by_id=current_user.id,
            options=body.options,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return mount_to_dict(row)


@router.post("/orgs/{org_id}/storage-mounts/{mount_id}/os-attach")
def post_os_attach(
    org_id: int,
    mount_id: int,
    body: OsAttachBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, svc = _require_org_member(db, org_id, current_user)
    if not current_user.is_admin and not svc.can_manage_org(current_user, org):
        raise HTTPException(403, "无权管理该组织挂载")
    m = get_mount(db, mount_id)
    if not m or m.organization_id != org_id:
        raise HTTPException(404, "挂载不存在")
    try:
        row = attach_os_mount(db, m, body.os_mount_point)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return mount_to_dict(row)


@router.post("/orgs/{org_id}/storage-mounts/{mount_id}/os-mount")
def post_os_mount(
    org_id: int,
    mount_id: int,
    body: OsMountBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, svc = _require_org_member(db, org_id, current_user)
    if not current_user.is_admin and not svc.can_manage_org(current_user, org):
        raise HTTPException(403, "无权执行内核挂载")
    m = get_mount(db, mount_id)
    if not m or m.organization_id != org_id:
        raise HTTPException(404, "挂载不存在")
    try:
        result = run_os_mount(body.nfs_export, body.os_mount_point, options=body.options)
        row = attach_os_mount(db, m, body.os_mount_point)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e
    return {"mount": mount_to_dict(row), **result}


@router.post("/orgs/{org_id}/storage-mounts/{mount_id}/os-umount")
def post_os_umount(
    org_id: int,
    mount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, svc = _require_org_member(db, org_id, current_user)
    if not current_user.is_admin and not svc.can_manage_org(current_user, org):
        raise HTTPException(403, "无权执行 umount")
    m = get_mount(db, mount_id)
    if not m or m.organization_id != org_id:
        raise HTTPException(404, "挂载不存在")
    point = (m.options or {}).get("os_mount_point") if isinstance(m.options, dict) else None
    point = point or m.root_prefix
    try:
        return run_os_umount(str(point).rstrip("/"))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/orgs/{org_id}/storage-mounts/{mount_id}")
def delete_org_mount(
    org_id: int,
    mount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org, svc = _require_org_member(db, org_id, current_user)
    if not current_user.is_admin and not svc.can_manage_org(current_user, org):
        raise HTTPException(403, "无权管理该组织挂载")
    m = get_mount(db, mount_id)
    if not m or m.organization_id != org_id:
        raise HTTPException(404, "挂载不存在")
    delete_mount(db, m)
    return {"ok": True}


@router.get("/storage/mounts/{mount_id}/browse")
def browse_mount(
    mount_id: int,
    path: str = Query("", max_length=512),
    limit: int = Query(200, ge=1, le=1000),
    delimiter: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = get_mount(db, mount_id)
    if not m or not m.enabled:
        raise HTTPException(404, "挂载不存在或已禁用")
    _require_org_member(db, m.organization_id, current_user)
    try:
        if m.kind in ("nfs", "fuse"):
            items = list_os_mount_entries(m, path, max_keys=limit, delimiter=delimiter)
            prefix = resolve_mount_prefix(m, path)
        else:
            prefix = resolve_mount_prefix(m, path)
            items = FileStorageService().list_prefix(prefix, max_keys=limit, delimiter=delimiter)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(400, f"浏览失败: {e}") from e
    return {
        "mount_id": mount_id,
        "kind": m.kind,
        "root_prefix": m.root_prefix,
        "path": path,
        "prefix": prefix,
        "count": len(items),
        "items": items,
    }
