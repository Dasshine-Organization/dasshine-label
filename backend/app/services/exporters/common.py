"""导出公共抽取逻辑。"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.coco_export import bbox_xywh, iter_frame_boxes


def latest_anns(task: Any) -> List[Any]:
    return [a for a in (task.annotations or []) if getattr(a, "is_latest", True)]


def ann_payload(ann: Any) -> Dict[str, Any]:
    data = getattr(ann, "data", None)
    return data if isinstance(data, dict) else {}


def task_file_name(task: Any) -> str:
    data = task.data if isinstance(getattr(task, "data", None), dict) else {}
    return str(
        data.get("file_name")
        or data.get("filename")
        or (task.data_url.split("/")[-1] if getattr(task, "data_url", None) else f"{task.id}")
    )


def task_image_size(task: Any, payload: Optional[Dict[str, Any]] = None) -> Tuple[int, int]:
    data = task.data if isinstance(getattr(task, "data", None), dict) else {}
    w = int(data.get("width") or 0)
    h = int(data.get("height") or 0)
    if w and h:
        return w, h
    session = None
    if payload:
        session = payload.get("session") if isinstance(payload.get("session"), dict) else payload
    if isinstance(session, dict):
        w = int(session.get("width") or session.get("imageWidth") or w or 0)
        h = int(session.get("height") or session.get("imageHeight") or h or 0)
    meta = getattr(task, "task_metadata", None) or {}
    if isinstance(meta, dict):
        w = int(meta.get("width") or w or 0)
        h = int(meta.get("height") or h or 0)
    return max(0, w), max(0, h)


def primary_payload(task: Any) -> Dict[str, Any]:
    """导出真源：优先 canonical_annotation_id，否则首个非空 is_latest。"""
    cid = getattr(task, "canonical_annotation_id", None)
    if cid:
        for ann in task.annotations or []:
            if getattr(ann, "id", None) == cid:
                payload = ann_payload(ann)
                if payload:
                    return payload
    for ann in latest_anns(task):
        payload = ann_payload(ann)
        if payload:
            return payload
    return {}


def modality_annotation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """dasshine.modality_export.v1 → annotation 字段；或直接 modality.v1。"""
    if not payload:
        return {}
    if isinstance(payload.get("annotation"), dict):
        return payload["annotation"]
    if payload.get("schema") in ("dasshine.modality.v1", "dasshine.modality_export.v1"):
        return payload
    return payload


def modality_content(task: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
    data = task.data if isinstance(getattr(task, "data", None), dict) else {}
    return {
        "text": content.get("text") or data.get("text") or data.get("content") or "",
        "audio_url": content.get("audio_url") or getattr(task, "data_url", None) or data.get("audio_url"),
        "video_url": content.get("video_url") or getattr(task, "data_url", None) or data.get("video_url"),
        "image_url": content.get("image_url") or getattr(task, "data_url", None) or data.get("image_url"),
        "title": content.get("title") or data.get("title") or "",
    }


def build_class_map(label_classes: Optional[List[Dict]], discovered: Iterable[str]) -> Dict[str, int]:
    ordered: List[str] = []
    seen = set()
    if label_classes:
        for lc in label_classes:
            name = str(lc.get("name") or lc.get("id") or "")
            if name and name not in seen:
                ordered.append(name)
                seen.add(name)
    for name in discovered:
        if name and name not in seen:
            ordered.append(str(name))
            seen.add(str(name))
    return {n: i for i, n in enumerate(ordered)}


def class_names_ordered(cat_map: Dict[str, int]) -> List[str]:
    inv: Dict[int, str] = {}
    for name, idx in cat_map.items():
        if idx not in inv:
            inv[idx] = name
    return [inv[i] for i in sorted(inv)]


def zip_files(files: Dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def rows_to_csv(headers: List[str], rows: List[List[Any]]) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    for row in rows:
        w.writerow(row)
    return out.getvalue()


def dumps_json(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def dumps_jsonl(rows: Iterable[Dict[str, Any]]) -> bytes:
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def extract_boxes2d(task: Any) -> List[Dict[str, Any]]:
    boxes: List[Dict[str, Any]] = []
    cid = getattr(task, "canonical_annotation_id", None)
    anns = latest_anns(task)
    if cid:
        anns = [a for a in (task.annotations or []) if getattr(a, "id", None) == cid] or anns
    for ann in anns:
        boxes.extend(iter_frame_boxes(ann_payload(ann)))
    return boxes


def extract_boxes3d(task: Any) -> List[Dict[str, Any]]:
    """统一 boxes3d session 与 CRUD cuboid。"""
    out: List[Dict[str, Any]] = []
    cid = getattr(task, "canonical_annotation_id", None)
    anns = latest_anns(task)
    if cid:
        anns = [a for a in (task.annotations or []) if getattr(a, "id", None) == cid] or anns
    for ann in anns:
        payload = ann_payload(ann)
        session = payload.get("session") if isinstance(payload.get("session"), dict) else payload
        boxes = []
        if isinstance(session, dict):
            boxes = session.get("boxes3d") or []
        if isinstance(boxes, list) and boxes:
            for b in boxes:
                if not isinstance(b, dict):
                    continue
                center = b.get("center") or {}
                size = b.get("size") or {}
                rot = b.get("rotation") or {}
                out.append(
                    {
                        "label": str(b.get("label") or "Unknown"),
                        "x": float(center.get("x", 0)),
                        "y": float(center.get("y", 0)),
                        "z": float(center.get("z", 0)),
                        "dx": float(size.get("x") or size.get("width") or size.get("l") or 0),
                        "dy": float(size.get("y") or size.get("height") or size.get("h") or 0),
                        "dz": float(size.get("z") or size.get("depth") or size.get("w") or 0),
                        "yaw": float(rot.get("z") or rot.get("yaw") or 0),
                        "score": b.get("score"),
                    }
                )
            continue
        if payload.get("type") == "cuboid":
            pos = payload.get("position") or {}
            size = payload.get("size") or {}
            rot = payload.get("rotation") or {}
            out.append(
                {
                    "label": str(payload.get("label") or "Unknown"),
                    "x": float(pos.get("x", 0)),
                    "y": float(pos.get("y", 0)),
                    "z": float(pos.get("z", 0)),
                    "dx": float(size.get("depth") or size.get("x") or 0),
                    "dy": float(size.get("height") or size.get("y") or 0),
                    "dz": float(size.get("width") or size.get("z") or 0),
                    "yaw": float(rot.get("yaw") or rot.get("z") or 0),
                    "score": payload.get("score"),
                }
            )
    return out


# re-export for exporters
__all__ = [
    "ann_payload",
    "bbox_xywh",
    "build_class_map",
    "class_names_ordered",
    "dumps_json",
    "dumps_jsonl",
    "extract_boxes2d",
    "extract_boxes3d",
    "iter_frame_boxes",
    "latest_anns",
    "modality_annotation",
    "modality_content",
    "primary_payload",
    "rows_to_csv",
    "task_file_name",
    "task_image_size",
    "zip_files",
]
