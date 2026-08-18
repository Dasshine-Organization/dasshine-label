"""组织存储挂载：应用级前缀 + NFS/FUSE 内核挂载登记。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.storage_mount import StorageMount
from app.services.file_storage import FileStorageService, assert_browse_allowed
from app.services.os_mounts import find_mount_at, is_os_mount, parse_nfs_export, verify_kind_mount

MOUNT_KINDS = ("local_prefix", "s3_prefix", "fuse", "nfs")


def _options(m: StorageMount) -> Dict[str, Any]:
    return dict(m.options) if isinstance(m.options, dict) else {}


def mount_to_dict(m: StorageMount) -> Dict[str, Any]:
    opts = _options(m)
    os_path = opts.get("os_mount_point") or (
        m.root_prefix if m.kind in ("nfs", "fuse") else None
    )
    mounted = bool(os_path) and is_os_mount(str(os_path))
    row = find_mount_at(str(os_path)) if os_path else None
    return {
        "id": m.id,
        "organization_id": m.organization_id,
        "name": m.name,
        "kind": m.kind,
        "root_prefix": m.root_prefix,
        "read_only": bool(m.read_only),
        "enabled": bool(m.enabled),
        "options": opts,
        "os_mounted": mounted,
        "kernel": row,
        "created_by_id": m.created_by_id,
    }


def list_mounts(db: Session, org_id: int, *, enabled_only: bool = False) -> List[StorageMount]:
    q = db.query(StorageMount).filter(StorageMount.organization_id == org_id)
    if enabled_only:
        q = q.filter(StorageMount.enabled.is_(True))
    return q.order_by(StorageMount.id.asc()).all()


def get_mount(db: Session, mount_id: int) -> Optional[StorageMount]:
    return db.query(StorageMount).filter(StorageMount.id == mount_id).first()


def create_mount(
    db: Session,
    *,
    org_id: int,
    name: str,
    root_prefix: str,
    kind: str = "local_prefix",
    read_only: bool = True,
    created_by_id: Optional[int] = None,
    options: Optional[Dict[str, Any]] = None,
) -> StorageMount:
    name = (name or "").strip()
    if not name:
        raise ValueError("名称不能为空")
    kind = (kind or "local_prefix").strip()
    if kind not in MOUNT_KINDS:
        raise ValueError("kind 须为 local_prefix / s3_prefix / fuse / nfs")
    opts = dict(options or {})
    if kind in ("local_prefix", "s3_prefix"):
        prefix = assert_browse_allowed(root_prefix)
        if not prefix:
            raise ValueError("root_prefix 不能为空")
        root = prefix.rstrip("/") + "/"
    else:
        if kind == "nfs":
            export = str(opts.get("nfs_export") or "").strip()
            if not export:
                raise ValueError("nfs 挂载须提供 options.nfs_export（host:/export）")
            parse_nfs_export(export)
        os_point = str(opts.get("os_mount_point") or root_prefix or "").strip()
        if not os_point:
            raise ValueError("须提供 os_mount_point 或 root_prefix 作为内核挂载点")
        from app.core.config import settings

        if getattr(settings, "STORAGE_REQUIRE_OS_MOUNT", False):
            verify_kind_mount(os_point, kind)
        opts["os_mount_point"] = os_point
        root = os_point.rstrip("/") + "/"
    row = StorageMount(
        organization_id=org_id,
        name=name[:120],
        kind=kind,
        root_prefix=root,
        read_only=bool(read_only),
        enabled=True,
        options=opts or None,
        created_by_id=created_by_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def attach_os_mount(db: Session, mount: StorageMount, os_mount_point: str) -> StorageMount:
    if mount.kind not in ("nfs", "fuse"):
        raise ValueError("仅 nfs / fuse 可绑定内核挂载点")
    row = verify_kind_mount(os_mount_point, mount.kind)
    opts = _options(mount)
    opts["os_mount_point"] = os_mount_point.rstrip("/")
    if row.get("device"):
        opts["kernel_device"] = row["device"]
        opts["kernel_fstype"] = row.get("fstype")
    mount.options = opts
    mount.root_prefix = os_mount_point.rstrip("/") + "/"
    db.add(mount)
    db.commit()
    db.refresh(mount)
    return mount


def delete_mount(db: Session, mount: StorageMount) -> None:
    db.delete(mount)
    db.commit()


def resolve_mount_prefix(mount: StorageMount, relative: str = "") -> str:
    if not mount.enabled:
        raise ValueError("挂载已禁用")
    rel = (relative or "").lstrip("/").replace("\\", "/")
    if ".." in Path(rel).parts:
        raise ValueError("非法相对路径")
    kind = getattr(mount, "kind", None) or "local_prefix"
    if kind in ("nfs", "fuse"):
        root = Path(_options(mount).get("os_mount_point") or mount.root_prefix)
        if not str(root):
            raise ValueError("未绑定内核挂载点")
        full = root if not rel else (root / rel)
        return str(full)
    root = mount.root_prefix.rstrip("/") + "/"
    if not rel:
        full = root.rstrip("/")
    else:
        full = root + rel
    return assert_browse_allowed(full)


def _os_root(mount: StorageMount) -> Path:
    raw = _options(mount).get("os_mount_point") or mount.root_prefix
    root = Path(str(raw)).resolve()
    if not root.is_dir():
        raise ValueError(f"挂载根不是目录: {root}")
    return root


def _os_join(root: Path, relative: str) -> Path:
    rel = (relative or "").lstrip("/").replace("\\", "/")
    if ".." in Path(rel).parts:
        raise ValueError("非法相对路径")
    full = (root / rel).resolve() if rel else root
    if full != root and root not in full.parents:
        raise ValueError("路径逃逸挂载根")
    if full.is_symlink():
        raise ValueError("不允许符号链接")
    return full


def list_os_mount_entries(
    mount: StorageMount,
    relative: str = "",
    *,
    max_keys: int = 200,
    delimiter: bool = True,
) -> List[Dict[str, Any]]:
    root = _os_root(mount)
    base = _os_join(root, relative)
    if not base.exists():
        return []
    limit = max(1, min(int(max_keys), 1000))
    out: List[Dict[str, Any]] = []
    if base.is_file():
        rel = base.relative_to(root).as_posix()
        out.append({"key": rel, "is_dir": False, "size": base.stat().st_size, "url": None})
        return out
    if delimiter:
        for child in sorted(base.iterdir()):
            if len(out) >= limit:
                break
            if child.is_symlink():
                continue
            rel = child.relative_to(root).as_posix()
            out.append(
                {
                    "key": rel + ("/" if child.is_dir() else ""),
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else 0,
                    "url": None,
                }
            )
        return out
    for dirpath, dirnames, filenames in __import__("os").walk(base):
        dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
        for name in filenames:
            if len(out) >= limit:
                return out
            p = Path(dirpath) / name
            if p.is_symlink():
                continue
            rel = p.relative_to(root).as_posix()
            out.append({"key": rel, "is_dir": False, "size": p.stat().st_size, "url": None})
    return out


def ingest_os_mount_files(
    mount: StorageMount,
    relative: str,
    *,
    project_id: int,
    extensions: set[str],
    limit: int = 500,
) -> List[str]:
    """从 NFS/FUSE 根复制匹配文件到项目 uploads，返回可访问 URL。"""
    items = list_os_mount_entries(mount, relative, max_keys=limit, delimiter=False)
    root = _os_root(mount)
    storage = FileStorageService()
    urls: List[str] = []
    for it in items:
        if it.get("is_dir"):
            continue
        key = (it.get("key") or "").lower()
        if not any(key.endswith(ext) for ext in extensions):
            continue
        src = _os_join(root, it["key"])
        if not src.is_file():
            continue
        _, url = storage.save_bytes(project_id, src.name, src.read_bytes(), subdir="from-mount")
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls
