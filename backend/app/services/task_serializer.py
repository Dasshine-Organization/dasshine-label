"""任务 API 序列化"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.task import Task


def task_list_item(task: Task, schema: Optional[dict] = None) -> Dict[str, Any]:
    schema = schema or {}
    assignee_name = task.assignee.username if task.assignee else None
    data = task.data or {}
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project": task.project.name if task.project else "",
        "category": schema.get("category"),
        "ann_type": schema.get("ann_type"),
        "type": schema.get("ann_type") or "",
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "priority": task.priority,
        "assignee_id": task.assignee_id,
        "assignee_name": assignee_name,
        "data_url": task.data_url,
        "filename": data.get("filename") or data.get("file_name"),
        "pre_label_confidence": task.pre_label_confidence,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "reward": schema.get("price_per_task", 0.1),
    }
