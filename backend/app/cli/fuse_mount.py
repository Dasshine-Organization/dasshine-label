"""把本地存储目录挂到 FUSE 挂载点。

用法:
  python -m app.cli.fuse_mount --root ./uploads/projects --mountpoint /tmp/dasshine-fuse
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dasshine 存储 FUSE 挂载")
    parser.add_argument("--root", required=True, help="后端存储根目录（绝对或相对）")
    parser.add_argument("--mountpoint", required=True, help="内核 FUSE 挂载点")
    parser.add_argument("--read-write", action="store_true", help="允许写入（默认只读）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    root = str(Path(args.root).resolve())
    mp = str(Path(args.mountpoint).resolve())
    from app.services.fuse_fs import mount_fuse

    logging.info("fuse mount root=%s mountpoint=%s ro=%s", root, mp, not args.read_write)
    try:
        mount_fuse(mp, root, read_only=not args.read_write, foreground=True)
    except RuntimeError as e:
        logging.error("%s", e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
