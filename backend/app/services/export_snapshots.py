"""不可变导出快照（P19）。

每次同步/异步导出成功后追加一行，version 按项目递增。
manifest 只记录 task_id ↔ canonical_annotation_id，便于日后对账，写入后不再 UPDATE。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.export_snapshot import ExportSnapshot
from app.models.task import Task


def build_manifest(tasks: List[Task]) -> List[Dict[str, Any]]:
    """导出包内任务清单。无 canonical 的任务仍占位，避免版本对不齐。"""
    return [
        {
            "task_id": t.id,
            "canonical_annotation_id": getattr(t, "canonical_annotation_id", None),
        }
        for t in tasks
    ]


def next_version(db: Session, project_id: int) -> int:
    """下一版本号 = 当前 max(version)+1；无快照时从 1 起。"""
    current = (
        db.query(func.max(ExportSnapshot.version))
        .filter(ExportSnapshot.project_id == project_id)
        .scalar()
    )
    return int(current or 0) + 1


def create_snapshot(
    db: Session,
    *,
    project_id: int,
    tasks: List[Task],
    fmt: str,
    status_filter: str,
    storage_path: str,
    download_url: Optional[str],
    size_bytes: int,
    created_by_id: Optional[int],
) -> ExportSnapshot:
    """落一条快照。调用方负责 commit；失败应 rollback 以免空洞 version。"""
    snap = ExportSnapshot(
        project_id=project_id,
        version=next_version(db, project_id),
        format=fmt,
        status_filter=status_filter or "approved",
        storage_path=storage_path,
        download_url=download_url,
        bytes=size_bytes,
        task_count=len(tasks),
        manifest=build_manifest(tasks),
        created_by_id=created_by_id,
    )
    db.add(snap)
    db.flush()
    return snap


def list_snapshots(db: Session, project_id: int, limit: int = 50) -> List[ExportSnapshot]:
    return (
        db.query(ExportSnapshot)
        .filter(ExportSnapshot.project_id == project_id)
        .order_by(ExportSnapshot.version.desc())
        .limit(min(limit, 200))
        .all()
    )


def get_snapshot(db: Session, snapshot_id: int) -> Optional[ExportSnapshot]:
    return db.query(ExportSnapshot).filter(ExportSnapshot.id == snapshot_id).first()


def snapshot_to_dict(s: ExportSnapshot) -> Dict[str, Any]:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "version": s.version,
        "format": s.format,
        "status_filter": s.status_filter,
        "download_url": s.download_url,
        "bytes": s.bytes,
        "task_count": s.task_count,
        "manifest": s.manifest,
        "created_by_id": s.created_by_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
