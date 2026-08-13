"""
数据导出 API：JSON / CSV / COCO（2D image_export.v1）。
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_admin, get_current_user, get_db
from app.models.annotation import Annotation
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User
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


def _iter_frame_boxes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    session = payload.get("session") if isinstance(payload.get("session"), dict) else payload
    frames = session.get("frames") if isinstance(session, dict) else None
    boxes: List[Dict[str, Any]] = []
    if isinstance(frames, dict):
        for items in frames.values():
            if isinstance(items, list):
                boxes.extend([x for x in items if isinstance(x, dict)])
        return boxes
    raw = payload.get("annotations2d")
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _bbox_xywh(ann: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    if ann.get("type") and ann["type"] not in ("bbox", "rectangle", "box"):
        # polygon 等：尝试从 points 求外接矩形
        if ann.get("type") == "polygon":
            pts = ann.get("points") or []
            if len(pts) < 3:
                return None
            xs, ys = [], []
            for p in pts:
                if isinstance(p, dict):
                    xs.append(float(p.get("x", 0)))
                    ys.append(float(p.get("y", 0)))
                elif isinstance(p, (list, tuple)) and len(p) >= 2:
                    xs.append(float(p[0]))
                    ys.append(float(p[1]))
            if not xs:
                return None
            x, y = min(xs), min(ys)
            return x, y, max(xs) - x, max(ys) - y
        return None

    if "bbox" in ann and isinstance(ann["bbox"], (list, tuple)) and len(ann["bbox"]) >= 4:
        x, y, w, h = ann["bbox"][:4]
        return float(x), float(y), float(w), float(h)

    pts = ann.get("points") or []
    if len(pts) >= 2:
        def _xy(p):
            if isinstance(p, dict):
                return float(p.get("x", 0)), float(p.get("y", 0))
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                return float(p[0]), float(p[1])
            return 0.0, 0.0

        (x0, y0), (x1, y1) = _xy(pts[0]), _xy(pts[1])
        x, y = min(x0, x1), min(y0, y1)
        return x, y, abs(x1 - x0), abs(y1 - y0)
    return None


def export_to_coco(tasks: List[Task], project_name: str, label_classes: Optional[List[Dict]] = None) -> dict:
    """从 dasshine.image_export.v1 / session.frames 构建 COCO。"""
    categories: List[Dict[str, Any]] = []
    cat_map: Dict[str, int] = {}

    if label_classes:
        for i, lc in enumerate(label_classes):
            name = str(lc.get("name") or lc.get("id") or f"class_{i + 1}")
            cid = i + 1
            cat_map[name] = cid
            cat_map[str(lc.get("id") or name)] = cid
            categories.append({"id": cid, "name": name, "supercategory": "object"})

    coco = {
        "info": {
            "description": project_name,
            "version": "1.0",
            "year": datetime.now().year,
            "date_created": datetime.now().isoformat(),
            "contributor": "Dasshine Label",
        },
        "images": [],
        "annotations": [],
        "categories": categories,
    }

    ann_id = 1
    for task in tasks:
        data = task.data or {}
        file_name = (
            data.get("file_name")
            or data.get("filename")
            or (task.data_url.split("/")[-1] if task.data_url else f"{task.id}.jpg")
        )
        coco["images"].append(
            {
                "id": task.id,
                "file_name": file_name,
                "coco_url": task.data_url,
                "height": int(data.get("height") or 0),
                "width": int(data.get("width") or 0),
            }
        )

        for ann in _latest_anns(task):
            payload = _ann_payload(ann)
            for box in _iter_frame_boxes(payload):
                xywh = _bbox_xywh(box)
                if not xywh:
                    continue
                x, y, w, h = xywh
                label = str(box.get("label") or box.get("category") or "object")
                if label not in cat_map:
                    cid = len(cat_map) + 1
                    cat_map[label] = cid
                    coco["categories"].append(
                        {"id": cid, "name": label, "supercategory": "object"}
                    )
                category_id = cat_map[label]
                entry: Dict[str, Any] = {
                    "id": ann_id,
                    "image_id": task.id,
                    "category_id": category_id,
                    "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                    "area": round(max(0.0, w) * max(0.0, h), 2),
                    "iscrowd": 0,
                }
                if box.get("score") is not None:
                    entry["score"] = box.get("score")
                coco["annotations"].append(entry)
                ann_id += 1

    return coco


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
