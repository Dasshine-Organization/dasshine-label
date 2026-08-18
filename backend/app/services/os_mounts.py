"""内核 NFS / FUSE 挂载探测与（可选）执行。"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

_NFS_EXPORT_RE = re.compile(r"^([A-Za-z0-9._:-]+):(/[^ \t]+)$")


def os_mount_enabled() -> bool:
    return bool(getattr(settings, "STORAGE_OS_MOUNT_ENABLED", False))


def allow_roots() -> List[Path]:
    raw = (getattr(settings, "STORAGE_OS_MOUNT_ALLOW_ROOTS", None) or "").strip()
    if not raw:
        return [Path("/mnt/dasshine"), Path("/Volumes/dasshine")]
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def parse_nfs_export(export: str) -> Tuple[str, str]:
    s = (export or "").strip()
    m = _NFS_EXPORT_RE.match(s)
    if not m:
        raise ValueError("nfs_export 须为 host:/export 形式")
    return m.group(1), m.group(2)


def is_os_mount(path: str | Path) -> bool:
    p = Path(path)
    try:
        return os.path.ismount(str(p))
    except OSError:
        return False


def _under_allow_root(path: Path) -> bool:
    resolved = path.resolve()
    for root in allow_roots():
        try:
            rr = root.resolve()
        except OSError:
            rr = root
        if resolved == rr or rr in resolved.parents:
            return True
    return False


def assert_mount_point_allowed(mount_point: str | Path) -> Path:
    p = Path(mount_point)
    if not p.is_absolute():
        raise ValueError("挂载点须为绝对路径")
    if not _under_allow_root(p):
        raise ValueError(f"挂载点不在允许根下: {', '.join(str(r) for r in allow_roots())}")
    return p


def list_kernel_mounts() -> List[Dict[str, Any]]:
    if sys.platform.startswith("linux"):
        return _parse_proc_mounts()
    if sys.platform == "darwin":
        return _parse_darwin_mount()
    return []


def _parse_proc_mounts() -> List[Dict[str, Any]]:
    path = Path("/proc/mounts")
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        device, mount_point, fstype = parts[0], parts[1], parts[2]
        out.append(_mount_row(device, mount_point, fstype))
    return out


def _parse_darwin_mount() -> List[Dict[str, Any]]:
    try:
        proc = subprocess.run(
            ["mount"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    out: List[Dict[str, Any]] = []
    # host:/export on /mnt/foo (nfs, ...)
    row_re = re.compile(r"^(.+?) on (.+?) \(([^)]+)\)")
    for line in (proc.stdout or "").splitlines():
        m = row_re.match(line.strip())
        if not m:
            continue
        device, mount_point, meta = m.group(1), m.group(2), m.group(3)
        fstype = (meta.split(",")[0] or "").strip()
        out.append(_mount_row(device, mount_point, fstype))
    return out


def _mount_row(device: str, mount_point: str, fstype: str) -> Dict[str, Any]:
    ft = (fstype or "").lower()
    kind = "other"
    if "nfs" in ft:
        kind = "nfs"
    elif "fuse" in ft or "osxfuse" in ft or "macfuse" in ft:
        kind = "fuse"
    return {
        "device": device,
        "mount_point": mount_point,
        "fstype": fstype,
        "kind": kind,
        "is_mount": is_os_mount(mount_point),
    }


def find_mount_at(mount_point: str) -> Optional[Dict[str, Any]]:
    want = str(Path(mount_point))
    for row in list_kernel_mounts():
        if Path(row["mount_point"]) == Path(want):
            return row
    if is_os_mount(want):
        return {
            "device": "",
            "mount_point": want,
            "fstype": "unknown",
            "kind": "other",
            "is_mount": True,
        }
    return None


def verify_kind_mount(mount_point: str, kind: str) -> Dict[str, Any]:
    row = find_mount_at(mount_point)
    if not row or not row.get("is_mount"):
        raise ValueError(f"路径不是内核挂载点: {mount_point}")
    if kind == "nfs" and row.get("kind") not in ("nfs", "other"):
        raise ValueError(f"挂载点 fstype={row.get('fstype')} 不是 NFS")
    if kind == "fuse" and row.get("kind") not in ("fuse", "other"):
        raise ValueError(f"挂载点 fstype={row.get('fstype')} 不是 FUSE")
    return row


def nfs_mount_argv(export: str, mount_point: str, *, options: str = "ro,hard,intr") -> List[str]:
    parse_nfs_export(export)
    mp = assert_mount_point_allowed(mount_point)
    if sys.platform == "darwin":
        return ["mount", "-t", "nfs", "-o", options, export, str(mp)]
    return ["mount", "-t", "nfs", "-o", options, export, str(mp)]


def run_os_mount(export: str, mount_point: str, *, options: str = "ro,hard,intr") -> Dict[str, Any]:
    if not os_mount_enabled():
        raise RuntimeError("STORAGE_OS_MOUNT_ENABLED 未开启，拒绝执行内核 mount")
    mp = assert_mount_point_allowed(mount_point)
    mp.mkdir(parents=True, exist_ok=True)
    argv = nfs_mount_argv(export, str(mp), options=options)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"mount 失败: {err}")
    return {
        "ok": True,
        "argv": argv,
        "mount": find_mount_at(str(mp)),
    }


def run_os_umount(mount_point: str) -> Dict[str, Any]:
    if not os_mount_enabled():
        raise RuntimeError("STORAGE_OS_MOUNT_ENABLED 未开启，拒绝执行 umount")
    mp = assert_mount_point_allowed(mount_point)
    cmd = ["umount", str(mp)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
        raise RuntimeError(f"umount 失败: {err}")
    return {"ok": True, "mount_point": str(mp)}
