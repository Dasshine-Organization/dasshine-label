"""COCO 导出纯逻辑（与 FastAPI 路由解耦，便于单测）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def bbox_xywh(ann: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    if ann.get("type") and ann["type"] not in ("bbox", "rectangle", "box"):
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


def iter_frame_boxes(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
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


def build_coco_from_tasks(
    tasks: List[Any],
    project_name: str,
    label_classes: Optional[List[Dict]] = None,
) -> dict:
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

        anns = [a for a in (task.annotations or []) if getattr(a, "is_latest", True)]
        for ann in anns:
            payload = ann.data if isinstance(ann.data, dict) else {}
            for box in iter_frame_boxes(payload):
                xywh = bbox_xywh(box)
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
