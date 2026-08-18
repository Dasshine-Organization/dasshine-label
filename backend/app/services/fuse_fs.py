"""用户态存储 FUSE：把允许的本地目录以只读（默认）POSIX 视图导出。

不在 API 进程内挂载；由 `python -m app.cli.fuse_mount` 调用。
测试直接调用 StorageFuseFS，无需内核 FUSE。
"""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


def _safe_join(root: Path, rel: str) -> Path:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts:
        raise OSError(errno.EPERM, "path escapes root")
    full = (root / rel).resolve()
    root_r = root.resolve()
    if full != root_r and root_r not in full.parents:
        raise OSError(errno.EPERM, "path escapes root")
    return full


class StorageFuseFS:
    """最小 getattr / readdir / read / open，写操作在只读时拒绝。"""

    def __init__(self, root: str | Path, *, read_only: bool = True) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"FUSE 根不是目录: {self.root}")
        self.read_only = bool(read_only)

    def getattr(self, path: str) -> Dict[str, Any]:
        target = _safe_join(self.root, path)
        if not target.exists():
            raise OSError(errno.ENOENT, "not found")
        if target.is_symlink():
            raise OSError(errno.EPERM, "symlink denied")
        st = target.stat()
        mode = st.st_mode
        if self.read_only:
            mode &= ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        return {
            "st_mode": mode,
            "st_size": st.st_size,
            "st_mtime": int(st.st_mtime),
            "st_atime": int(st.st_atime),
            "st_ctime": int(getattr(st, "st_ctime", st.st_mtime)),
            "st_nlink": st.st_nlink,
            "st_uid": st.st_uid,
            "st_gid": st.st_gid,
        }

    def readdir(self, path: str) -> List[str]:
        target = _safe_join(self.root, path)
        if not target.is_dir():
            raise OSError(errno.ENOTDIR, "not a directory")
        names = [".", ".."]
        for child in sorted(target.iterdir()):
            if child.is_symlink():
                continue
            names.append(child.name)
        return names

    def open(self, path: str, flags: int = 0) -> None:
        if self.read_only and (flags & os.O_WRONLY or flags & os.O_RDWR or flags & os.O_APPEND):
            raise OSError(errno.EROFS, "read-only")
        target = _safe_join(self.root, path)
        if target.is_symlink():
            raise OSError(errno.EPERM, "symlink denied")
        if not target.is_file():
            raise OSError(errno.EISDIR if target.is_dir() else errno.ENOENT, "not a file")

    def read(self, path: str, size: int, offset: int) -> bytes:
        target = _safe_join(self.root, path)
        if target.is_symlink():
            raise OSError(errno.EPERM, "symlink denied")
        if not target.is_file():
            raise OSError(errno.EISDIR if target.is_dir() else errno.ENOENT, "not a file")
        with target.open("rb") as f:
            f.seek(max(0, int(offset)))
            return f.read(max(0, int(size)))

    def write(self, path: str, data: bytes, offset: int) -> int:
        if self.read_only:
            raise OSError(errno.EROFS, "read-only")
        target = _safe_join(self.root, path)
        with target.open("r+b") as f:
            f.seek(max(0, int(offset)))
            f.write(data)
        return len(data)

    def truncate(self, path: str, length: int) -> None:
        if self.read_only:
            raise OSError(errno.EROFS, "read-only")
        target = _safe_join(self.root, path)
        os.truncate(target, int(length))

    def iter_files(self, path: str = "") -> Iterator[str]:
        target = _safe_join(self.root, path)
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if not (Path(dirpath) / d).is_symlink()]
            for name in filenames:
                p = Path(dirpath) / name
                if p.is_symlink():
                    continue
                yield str(p.relative_to(self.root)).replace("\\", "/")


def mount_fuse(
    mountpoint: str,
    root: str,
    *,
    read_only: bool = True,
    foreground: bool = True,
) -> None:
    try:
        from fuse import FUSE, Operations  # type: ignore
    except ImportError as e:
        raise RuntimeError("未安装 fusepy，请执行: pip install fusepy（并安装 libfuse / macFUSE）") from e

    fs = StorageFuseFS(root, read_only=read_only)

    class Ops(Operations):
        def getattr(self, path, fh=None):  # noqa: ANN001
            return fs.getattr(path)

        def readdir(self, path, fh):  # noqa: ANN001
            return fs.readdir(path)

        def open(self, path, flags):  # noqa: ANN001
            fs.open(path, flags)
            return 0

        def read(self, path, size, offset, fh):  # noqa: ANN001
            return fs.read(path, size, offset)

        def write(self, path, data, offset, fh):  # noqa: ANN001
            return fs.write(path, data, offset)

        def truncate(self, path, length, fh=None):  # noqa: ANN001
            fs.truncate(path, length)

        def create(self, path, mode, fi=None):  # noqa: ANN001
            if fs.read_only:
                raise OSError(errno.EROFS, "read-only")
            target = _safe_join(fs.root, path)
            fd = os.open(target, os.O_WRONLY | os.O_CREAT, mode)
            os.close(fd)
            return 0

    os.makedirs(mountpoint, exist_ok=True)
    FUSE(
        Ops(),
        mountpoint,
        foreground=foreground,
        ro=read_only,
        allow_other=False,
        nothreads=True,
    )
