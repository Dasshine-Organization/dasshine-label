"""
数据导出 API：JSON / CSV / COCO（2D image_export.v1）。
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.annotation import Annotation
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.coco_export import build_coco_from_tasks
from app.services.project_acl import can_administrate_project, can_review_project
from app.services.project_service import _get_schema

router = APIRouter()


def _ann_payload(ann: Annotation) -> Any:
    return ann.data if isinstance(ann.data, dict) else {}


def _latest_anns(task: Task) -> List[Annotation]:
    return [a for a in (task.annotations or []) if getattr(a, "is_latest", True)]


def export_to_json(tasks: List[Task]) -> str:
    data = []
    for task in tasks:
        annotations = []
        for ann in _latest_anns(task):
            annotations.append(
                {
                    "annotator_id": ann.annotator_id,
                    "result": _ann_payload(ann),
                    "version": ann.version,
                    "work_time": ann.work_time,
                }
            )
        data.append(
            {
                "task_id": task.id,
                "data": task.data,
                "data_url": task.data_url,
                "annotations": annotations,
                "status": task.status.value if hasattr(task.status, "value") else task.status,
                "is_golden": task.is_golden,
            }
        )
    return json.dumps(data, ensure_ascii=False, indent=2)


def export_to_csv(tasks: List[Task]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["task_id", "data_url", "annotation", "annotator_id", "status"])
    for task in tasks:
        anns = _latest_anns(task)
        if not anns:
            writer.writerow(
                [
                    task.id,
                    task.data_url or "",
                    "",
                    "",
                    task.status.value if hasattr(task.status, "value") else task.status,
                ]
            )
            continue
        for ann in anns:
            writer.writerow(
                [
                    task.id,
                    task.data_url or "",
                    json.dumps(_ann_payload(ann), ensure_ascii=False),
                    ann.annotator_id,
                    task.status.value if hasattr(task.status, "value") else task.status,
                ]
            )
    return output.getvalue()


def export_to_coco(tasks: List[Task], project_name: str, label_classes: Optional[List[Dict]] = None) -> dict:
    """从 dasshine.image_export.v1 / session.frames 构建 COCO。"""
    return build_coco_from_tasks(tasks, project_name, label_classes)


@router.get("/export/{project_id}")
def export_project(
    project_id: int,
    format: str = Query("coco", pattern="^(json|csv|coco)$"),
    status: Optional[str] = Query("approved"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    导出项目标注数据。

    - 默认导出已通过（approved）任务的 COCO
    - status=submitted|annotating|all 可覆盖
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not (
        can_review_project(db, project, current_user)
        or can_administrate_project(db, project, current_user)
    ):
        raise HTTPException(status_code=403, detail="无权导出该项目")

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

    tasks = query.order_by(Task.id.asc()).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="没有可导出的数据")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)[:40]
    filename = f"{safe_name}_{timestamp}"

    schema = _get_schema(project)
    label_classes = schema.get("label_classes") or schema.get("labels") or []

    if format == "json":
        content = export_to_json(tasks)
        filename += ".json"
        media_type = "application/json"
    elif format == "csv":
        content = export_to_csv(tasks)
        filename += ".csv"
        media_type = "text/csv"
    else:
        content = json.dumps(
            export_to_coco(tasks, project.name, label_classes if isinstance(label_classes, list) else []),
            ensure_ascii=False,
            indent=2,
        )
        filename += "_coco.json"
        media_type = "application/json"

    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
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
        "total_tasks": project.total_items,
        "approved_tasks": approved,
        "submitted_tasks": submitted,
        "ready_for_export": approved,
        "export_formats": ["coco", "json", "csv"],
        "default_format": "coco",
    }
