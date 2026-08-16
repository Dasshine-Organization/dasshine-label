"""具身：原生 JSON / LeRobot JSONL / 力矩 CSV。"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Dict, List, Optional

from app.services.exporters.common import dumps_json, dumps_jsonl, primary_payload
from app.services.exporters.types import ExportArtifact


def _embodied_docs(tasks: List[Any]) -> List[Dict[str, Any]]:
    docs = []
    for task in tasks:
        payload = primary_payload(task)
        if payload.get("schema") in (
            "dasshine.embodied_sequence.v3",
            "dasshine.embodied_sequence.v4",
            "dasshine.embodied_sequence.v5",
            "dasshine.embodied_sequence.v6",
        ) or payload.get("frames"):
            docs.append(payload)
            continue
        docs.append(
            {
                "schema": "dasshine.embodied_sequence.v6",
                "task_db_id": task.id,
                "instruction": "",
                "success": "unknown",
                "segments": [],
                "grasps": [],
                "trajectory": [],
                "preferences": [],
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
        instruction = doc.get("instruction") or project_name
        success = doc.get("success") or "unknown"
        segments = doc.get("segments") or []
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
                    "task": instruction,
                    "instruction": instruction,
                    "success": success,
                    "action": action.get("id"),
                    "action_label": action.get("label"),
                    "observation.state": state,
                    "observation.torque": torque,
                    "joints_source": fr.get("joints_source") or doc.get("joints_source"),
                    "segments": segments,
                    "note": fr.get("note") or "",
                }
            )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_lerobot.jsonl",
        media_type="application/x-ndjson",
    )


def export_embodied_lerobot_dataset(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    from app.services.embodied_service import build_lerobot_dataset_zip

    docs = _embodied_docs(tasks)
    return ExportArtifact(
        content=build_lerobot_dataset_zip(docs, project_name),
        filename_suffix="_lerobot_dataset.zip",
        media_type="application/zip",
    )


def export_embodied_rlds(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    from app.services.embodied_service import build_rlds_dataset_zip

    docs = _embodied_docs(tasks)
    return ExportArtifact(
        content=build_rlds_dataset_zip(docs, project_name),
        filename_suffix="_rlds.zip",
        media_type="application/zip",
    )


def export_embodied_torque_csv(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["task_id", "frame_index", "timestamp_ms", "joint", "torque_nm", "position_rad", "joints_source"])
    for doc in _embodied_docs(tasks):
        tid = doc.get("task_db_id") or doc.get("task_id") or ""
        for fr in doc.get("frames") or []:
            if not isinstance(fr, dict):
                continue
            src = fr.get("joints_source") or doc.get("joints_source") or ""
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
                        src,
                    ]
                )
    return ExportArtifact(
        content=buf.getvalue().encode("utf-8"),
        filename_suffix="_torque.csv",
        media_type="text/csv",
    )


def export_embodied_hdf5(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    """多 episode 时打成 ZIP（每任务一个 .hdf5）；单任务直接返回 hdf5。"""
    _ = label_classes
    docs_bytes = []
    for task in tasks:
        # 优先用已提交 annotation 重建；否则用空 workspace 结构走 docs 路径
        payload = None
        for ann in getattr(task, "annotations", None) or []:
            if getattr(ann, "is_latest", True) and isinstance(getattr(ann, "data", None), dict):
                if (ann.data or {}).get("frames") is not None:
                    payload = ann.data
                    break
        if payload and payload.get("frames"):
            # 从已导出 doc 写临时 hdf5（绕过 workspace）
            raw = _hdf5_from_doc(payload, project_name)
            docs_bytes.append((f"episode_{task.id:06d}.hdf5", raw))
            continue
        # fallback: minimal empty
        raw = _hdf5_from_doc(
            {
                "schema": "dasshine.embodied_sequence.v6",
                "task_id": str(task.id),
                "task_db_id": task.id,
                "instruction": "",
                "success": "unknown",
                "fps": 12,
                "frames": [],
                "segments": [],
                "preferences": [],
                "grasps": [],
            },
            project_name,
        )
        docs_bytes.append((f"episode_{task.id:06d}.hdf5", raw))

    if len(docs_bytes) == 1:
        return ExportArtifact(
            content=docs_bytes[0][1],
            filename_suffix=".hdf5",
            media_type="application/x-hdf5",
        )

    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in docs_bytes:
            zf.writestr(name, data)
    return ExportArtifact(
        content=buf.getvalue(),
        filename_suffix="_hdf5.zip",
        media_type="application/zip",
    )


def _hdf5_from_doc(doc: Dict[str, Any], project_name: str) -> bytes:
    import h5py
    import numpy as np

    frames = doc.get("frames") or []
    qpos, force, tactile, actions = [], [], [], []
    for fr in frames:
        if not isinstance(fr, dict):
            continue
        joints = fr.get("joints") or []
        qpos.append([float(j.get("position_rad") or 0) for j in joints if isinstance(j, dict)])
        f = fr.get("force") if isinstance(fr.get("force"), dict) else {}
        force.append(
            [
                float(f.get("fx", 0) or 0),
                float(f.get("fy", 0) or 0),
                float(f.get("fz", 0) or 0),
                float(f.get("tx", 0) or 0),
                float(f.get("ty", 0) or 0),
                float(f.get("tz", 0) or 0),
            ]
        )
        pads = ((fr.get("tactile") or {}).get("pads") if isinstance(fr.get("tactile"), dict) else []) or []
        tactile.append([float(p.get("pressure", 0) or 0) for p in pads if isinstance(p, dict)])
        actions.append(str((fr.get("action") or {}).get("id") or "idle"))

    buf = io.BytesIO()
    with h5py.File(buf, "w") as hf:
        hf.attrs["schema"] = "dasshine.embodied_hdf5.v1"
        hf.attrs["project"] = project_name
        hf.attrs["instruction"] = str(doc.get("instruction") or "")
        hf.attrs["success"] = str(doc.get("success") or "unknown")
        hf.attrs["task_db_id"] = int(doc.get("task_db_id") or 0)
        hf.attrs["fps"] = int(doc.get("fps") or 12)
        meta = hf.create_group("meta")
        meta.create_dataset(
            "segments_json",
            data=np.bytes_(json.dumps(doc.get("segments") or [], ensure_ascii=False)),
        )
        meta.create_dataset(
            "preferences_json",
            data=np.bytes_(json.dumps(doc.get("preferences") or [], ensure_ascii=False)),
        )
        if qpos:
            max_j = max(len(r) for r in qpos)
            qpos_arr = np.zeros((len(qpos), max_j), dtype=np.float32)
            for i, r in enumerate(qpos):
                qpos_arr[i, : len(r)] = r
            hf.create_dataset("observations/qpos", data=qpos_arr)
        if force:
            hf.create_dataset("observations/force", data=np.asarray(force, dtype=np.float32))
        if tactile:
            max_p = max((len(r) for r in tactile), default=0)
            tac_arr = np.zeros((len(tactile), max(1, max_p)), dtype=np.float32)
            for i, r in enumerate(tactile):
                tac_arr[i, : len(r)] = r
            hf.create_dataset("observations/tactile", data=tac_arr)
        dt = h5py.string_dtype(encoding="utf-8")
        hf.create_dataset("actions/label", data=np.asarray(actions or [""], dtype=dt))
    return buf.getvalue()
