"""具身：原生 JSON / LeRobot JSONL / 力矩 CSV。"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional

from app.services.exporters.common import dumps_json, dumps_jsonl, primary_payload
from app.services.exporters.types import ExportArtifact


def _embodied_docs(tasks: List[Any]) -> List[Dict[str, Any]]:
    docs = []
    for task in tasks:
        payload = primary_payload(task)
        if payload.get("schema") == "dasshine.embodied_sequence.v3" or payload.get("frames"):
            docs.append(payload)
            continue
        # wrap minimal
        docs.append(
            {
                "schema": "dasshine.embodied_sequence.v3",
                "task_db_id": task.id,
                "frames": [],
                "raw": payload,
            }
        )
    return docs


def export_embodied_json(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    docs = _embodied_docs(tasks)
    payload = {"schema": "dasshine.embodied_project_export.v1", "project": project_name, "episodes": docs}
    return ExportArtifact(
        content=dumps_json(payload),
        filename_suffix="_embodied.json",
        media_type="application/json",
    )


def export_embodied_lerobot(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for doc in _embodied_docs(tasks):
        episode_id = doc.get("task_db_id") or doc.get("task_id") or doc.get("case_id")
        for fr in doc.get("frames") or []:
            if not isinstance(fr, dict):
                continue
            joints = fr.get("joints") or []
            state = [j.get("position_rad") for j in joints if isinstance(j, dict)]
            torque = [j.get("torque_nm") for j in joints if isinstance(j, dict)]
            action = fr.get("action") if isinstance(fr.get("action"), dict) else {}
            rows.append(
                {
                    "episode_index": episode_id,
                    "frame_index": fr.get("index"),
                    "timestamp": (fr.get("timestamp_ms") or 0) / 1000.0,
                    "action": action.get("id"),
                    "action_label": action.get("label"),
                    "observation.state": state,
                    "observation.torque": torque,
                    "task": project_name,
                    "note": fr.get("note") or "",
                }
            )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_lerobot.jsonl",
        media_type="application/x-ndjson",
    )


def export_embodied_torque_csv(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["task_id", "frame_index", "timestamp_ms", "joint", "torque_nm", "position_rad"])
    for doc in _embodied_docs(tasks):
        tid = doc.get("task_db_id") or doc.get("task_id") or ""
        for fr in doc.get("frames") or []:
            if not isinstance(fr, dict):
                continue
            for j in fr.get("joints") or []:
                if not isinstance(j, dict):
                    continue
                w.writerow(
                    [
                        tid,
                        fr.get("index"),
                        fr.get("timestamp_ms"),
                        j.get("name"),
                        j.get("torque_nm"),
                        j.get("position_rad"),
                    ]
                )
    return ExportArtifact(
        content=buf.getvalue().encode("utf-8"),
        filename_suffix="_torque.csv",
        media_type="text/csv",
    )
