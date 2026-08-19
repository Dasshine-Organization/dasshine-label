"""不可变导出快照"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.export_snapshot import ExportSnapshot
from app.models.task import Task


def build_manifest(tasks: List[Task]) -> List[Dict[str, Any]]:
    return [
        {
            "task_id": t.id,
            "canonical_annotation_id": getattr(t, "canonical_annotation_id", None),
        }
        for t in tasks
    ]


def next_version(db: Session, project_id: int) -> int:
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
