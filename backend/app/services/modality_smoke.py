"""按类别构造最小可导出 payload，供冒烟与 Playwright 对照。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from app.services.exporters import build_export, default_format_for
from app.services.exporters.registry import FORMATS_BY_CATEGORY

CATEGORIES = list(FORMATS_BY_CATEGORY.keys())


def _ann(data: Dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id="a1",
        annotator_id=1,
        version=1,
        work_time=10,
        is_latest=True,
        data=data,
    )


def _task(task_id: int, data: Dict[str, Any], anns: list, data_url: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=task_id,
        data=data,
        data_url=data_url or f"http://localhost/{task_id}",
        annotations=anns,
        status=SimpleNamespace(value="approved"),
        is_golden=False,
        task_metadata={},
        canonical_annotation_id="ann_1",
    )


def smoke_payload(category: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """返回 (task.data, annotation.data, data_url)。"""
    if category == "image_2d":
        return (
            {"file_name": "1.jpg", "width": 100, "height": 80},
            {
                "schema": "dasshine.image_export.v1",
                "session": {
                    "frames": {
                        "0": [
                            {
                                "type": "bbox",
                                "label": "person",
                                "points": [{"x": 0, "y": 0}, {"x": 10, "y": 20}],
                            }
                        ]
                    }
                },
            },
            "http://localhost/1.jpg",
        )
    if category == "pointcloud_3d":
        return (
            {"file_name": "000001.bin"},
            {
                "schema": "dasshine.pointcloud_export.v1",
                "session": {
                    "boxes3d": [
                        {
                            "label": "Car",
                            "center": {"x": 1, "y": 2, "z": 3},
                            "size": {"x": 4, "y": 1.5, "z": 2},
                            "rotation": {"z": 0.1},
                        }
                    ]
                },
            },
            "http://localhost/000001.bin",
        )
    if category == "nlp":
        return (
            {"text": "Alice lives in Paris"},
            {
                "schema": "dasshine.modality_export.v1",
                "content": {"text": "Alice lives in Paris"},
                "annotation": {
                    "schema": "dasshine.modality.v1",
                    "spans": [{"start": 0, "end": 5, "label": "PER", "text": "Alice"}],
                },
            },
            "",
        )
    if category == "audio":
        return (
            {},
            {
                "annotation": {
                    "segments": [{"start_ms": 0, "end_ms": 1500, "speaker": "A", "text": "hi"}],
                    "transcript": "hi",
                }
            },
            "http://localhost/a.wav",
        )
    if category == "video":
        return (
            {},
            {
                "annotation": {
                    "clips": [{"start_sec": 1.0, "end_sec": 2.5, "label": "run"}],
                    "tracks": [
                        {
                            "track_id": 1,
                            "label": "person",
                            "keyframes": [{"t": 0, "bbox": [0.1, 0.1, 0.2, 0.2]}],
                        }
                    ],
                    "caption": "demo",
                }
            },
            "http://localhost/v.mp4",
        )
    if category == "ocr":
        return (
            {"file_name": "r.jpg"},
            {"annotation": {"spans": [{"text": "发票", "bbox": [1, 2, 30, 10]}]}},
            "http://localhost/r.jpg",
        )
    if category == "multimodal":
        return (
            {},
            {
                "annotation": {
                    "caption": "a cat",
                    "vqa": {"question": "what?", "answer": "cat"},
                }
            },
            "http://localhost/img.jpg",
        )
    if category == "embodied":
        return (
            {},
            {
                "schema": "dasshine.embodied_sequence.v3",
                "task_db_id": 9,
                "frames": [
                    {
                        "index": 0,
                        "timestamp_ms": 0,
                        "action": {"id": "pick", "label": "抓取"},
                        "joints": [{"name": "j1", "position_rad": 0.1, "torque_nm": 1.2}],
                    }
                ],
            },
            "",
        )
    raise ValueError(f"unknown category {category}")


def export_smoke(category: str, fmt: str | None = None) -> bytes:
    data, ann, url = smoke_payload(category)
    fmt = (fmt or default_format_for(category)).strip().lower()
    artifact = build_export(
        category,
        fmt,
        [_task(1, data, [_ann(ann)], url)],
        f"smoke-{category}",
        [{"name": "person"}, {"name": "Car"}],
    )
    if not artifact.content:
        raise ValueError(f"{category}/{fmt} empty export")
    return artifact.content


def all_category_export_smokes() -> List[Tuple[str, str, int]]:
    out = []
    for cat in CATEGORIES:
        fmt = default_format_for(cat)
        content = export_smoke(cat, fmt)
        out.append((cat, fmt, len(content)))
    return out
