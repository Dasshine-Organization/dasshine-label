#!/usr/bin/env bash
# 将 NFS 导出挂到允许的本地路径。默认只读。
# 用法: scripts/mount_nfs.sh host:/export /mnt/dasshine/org1
set -euo pipefail
EXPORT="${1:?nfs export host:/path}"
MOUNTPOINT="${2:?absolute mount point}"
OPTS="${3:-ro,hard,intr}"
mkdir -p "$MOUNTPOINT"
if [[ "$(uname -s)" == "Darwin" ]]; then
  mount -t nfs -o "$OPTS" "$EXPORT" "$MOUNTPOINT"
else
  mount -t nfs -o "$OPTS" "$EXPORT" "$MOUNTPOINT"
fi
mount | grep -F "$MOUNTPOINT" || true
