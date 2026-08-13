"""
数据导出 API：按项目类别导出三种主流训练格式 + raw_json。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.exporters import build_export, default_format_for, list_formats
from app.services.project_acl import can_administrate_project, can_review_project
from app.services.project_service import _get_schema, _resolve_project_category

router = APIRouter()


def _load_exportable_tasks(db: Session, project_id: int, status: Optional[str]) -> list:
    query = (
        db.query(Task)
        .options(joinedload(Task.annotations))
        .filter(Task.project_id == project_id)
    )
    if status and status != "all":
        try:
            st = TaskStatus(status)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效状态: {status}") from e
        query = query.filter(Task.status == st)
    else:
        query = query.filter(Task.status == TaskStatus.APPROVED)
    return query.order_by(Task.id.asc()).all()


@router.get("/export/{project_id}")
def export_project(
    project_id: int,
    format: Optional[str] = Query(None, description="导出格式 id，见 /export/{id}/stats"),
    status: Optional[str] = Query("approved"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按项目 category 导出对应主流格式。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (
        can_review_project(db, project, current_user)
        or can_administrate_project(db, project, current_user)
    ):
        raise HTTPException(status_code=403, detail="无权导出该项目")

    category = _resolve_project_category(project)
    fmt = (format or default_format_for(category)).strip().lower()

    tasks = _load_exportable_tasks(db, project_id, status)
    if not tasks:
        raise HTTPException(status_code=404, detail="没有可导出的数据")

    schema = _get_schema(project)
    label_classes = schema.get("label_classes") or schema.get("labels") or []

    try:
        artifact = build_export(
            category,
            fmt,
            tasks,
            project.name,
            label_classes if isinstance(label_classes, list) else [],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)[:40]
    filename = f"{safe_name}_{timestamp}{artifact.filename_suffix}"

    return StreamingResponse(
        iter([artifact.content]),
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{project_id}/stats")
def get_export_stats(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (
        can_review_project(db, project, current_user)
        or can_administrate_project(db, project, current_user)
    ):
        raise HTTPException(status_code=403, detail="无权查看")

    category = _resolve_project_category(project)
    formats = list_formats(category, include_raw=True)

    approved = (
        db.query(Task)
        .filter(Task.project_id == project_id, Task.status == TaskStatus.APPROVED)
        .count()
    )
    submitted = (
        db.query(Task)
        .filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.SUBMITTED, TaskStatus.REVIEWING]),
        )
        .count()
    )
    return {
        "project_id": project_id,
        "project_name": project.name,
        "category": category,
        "total_tasks": project.total_items,
        "approved_tasks": approved,
        "submitted_tasks": submitted,
        "ready_for_export": approved,
        "default_format": default_format_for(category),
        "export_formats": [f.id for f in formats],
        "formats": [
            {
                "id": f.id,
                "label": f.label,
                "ext": f.ext,
                "description": f.description,
                "primary": f.primary,
            }
            for f in formats
        ],
    }
