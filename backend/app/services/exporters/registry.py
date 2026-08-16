"""按 category 注册三种主流导出格式 + raw_json 兜底。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.services.exporters import embodied_formats as embodied
from app.services.exporters import image_formats as image
from app.services.exporters import modality_formats as modality
from app.services.exporters import pointcloud_formats as pointcloud
from app.services.exporters.common import ann_payload, latest_anns
from app.services.exporters.types import ExportArtifact, ExporterFn, FormatMeta

# re-export
__all__ = [
    "ExportArtifact",
    "FormatMeta",
    "build_export",
    "default_format_for",
    "list_formats",
]


def _raw_json(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = label_classes, project_name
    data = []
    for task in tasks:
        annotations = []
        for ann in latest_anns(task):
            annotations.append(
                {
                    "annotator_id": getattr(ann, "annotator_id", None),
                    "result": ann_payload(ann),
                    "version": getattr(ann, "version", None),
                    "work_time": getattr(ann, "work_time", None),
                }
            )
        data.append(
            {
                "task_id": task.id,
                "data": getattr(task, "data", None),
                "data_url": getattr(task, "data_url", None),
                "annotations": annotations,
                "status": task.status.value if hasattr(getattr(task, "status", None), "value") else getattr(task, "status", None),
                "is_golden": getattr(task, "is_golden", False),
            }
        )
    return ExportArtifact(
        content=json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
        filename_suffix="_raw.json",
        media_type="application/json",
    )


FORMATS_BY_CATEGORY: Dict[str, List[FormatMeta]] = {
    "image_2d": [
        FormatMeta("coco", "COCO", "json", "目标检测 COCO JSON"),
        FormatMeta("yolo", "YOLO", "zip", "YOLO labels ZIP + classes.txt"),
        FormatMeta("voc", "Pascal VOC", "zip", "VOC Annotations XML ZIP"),
    ],
    "pointcloud_3d": [
        FormatMeta("kitti", "KITTI", "zip", "KITTI label_2 ZIP"),
        FormatMeta("openpcdet", "OpenPCDet", "json", "OpenPCDet-lite infos JSON"),
        FormatMeta("csv", "CSV", "csv", "3D boxes 表格"),
    ],
    "nlp": [
        FormatMeta("jsonl", "JSONL", "jsonl", "文本 + spans/分类 JSONL"),
        FormatMeta("conll", "CoNLL/BIO", "txt", "BIO 分词标注"),
        FormatMeta("csv", "CSV", "csv", "通用表格"),
    ],
    "audio": [
        FormatMeta("jsonl", "ASR JSONL", "jsonl", "utt/path/text JSONL"),
        FormatMeta("rttm", "RTTM", "rttm", "说话人分离 RTTM"),
        FormatMeta("csv", "CSV", "csv", "通用表格"),
    ],
    "video": [
        FormatMeta("jsonl", "ActivityNet JSONL", "jsonl", "视频片段标注 JSONL"),
        FormatMeta("webvtt", "WebVTT", "vtt", "字幕/片段 WebVTT"),
        FormatMeta("csv", "CSV", "csv", "通用表格"),
    ],
    "ocr": [
        FormatMeta("jsonl", "OCR JSONL", "jsonl", "检测框 + 文本"),
        FormatMeta("coco_text", "COCO-Text", "json", "COCO 风格 OCR"),
        FormatMeta("paddleocr", "PaddleOCR", "txt", "PaddleOCR 标签文件"),
    ],
    "multimodal": [
        FormatMeta("jsonl", "Caption/VQA JSONL", "jsonl", "图文/VQA JSONL"),
        FormatMeta("sharegpt", "ShareGPT", "jsonl", "LLaVA/ShareGPT conversations"),
        FormatMeta("csv", "CSV", "csv", "通用表格"),
    ],
    "embodied": [
        FormatMeta("json", "Embodied JSON", "json", "dasshine.embodied_sequence.v6"),
        FormatMeta("lerobot_dataset", "LeRobot Dataset", "zip", "parquet + videos ZIP"),
        FormatMeta("rlds", "RLDS-lite", "zip", "episodes/*/steps.jsonl"),
    ],
}

RAW_META = FormatMeta("raw_json", "Raw JSON", "json", "原始标注兜底", primary=False)

_EXPORTERS: Dict[str, Dict[str, ExporterFn]] = {
    "image_2d": {
        "coco": image.export_coco,
        "yolo": image.export_yolo,
        "voc": image.export_voc,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "pointcloud_3d": {
        "kitti": pointcloud.export_kitti,
        "openpcdet": pointcloud.export_openpcdet,
        "csv": pointcloud.export_pointcloud_csv,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "nlp": {
        "jsonl": modality.export_nlp_jsonl,
        "conll": modality.export_nlp_conll,
        "csv": modality.export_nlp_csv,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "audio": {
        "jsonl": modality.export_audio_jsonl,
        "rttm": modality.export_audio_rttm,
        "csv": modality.export_audio_csv,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "video": {
        "jsonl": modality.export_video_jsonl,
        "webvtt": modality.export_video_webvtt,
        "csv": modality.export_video_csv,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "ocr": {
        "jsonl": modality.export_ocr_jsonl,
        "coco_text": modality.export_ocr_coco_text,
        "paddleocr": modality.export_ocr_paddle,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "multimodal": {
        "jsonl": modality.export_mm_jsonl,
        "sharegpt": modality.export_mm_sharegpt,
        "csv": modality.export_mm_csv,
        "raw_json": _raw_json,
        "json": _raw_json,
    },
    "embodied": {
        "json": embodied.export_embodied_json,
        "lerobot_dataset": embodied.export_embodied_lerobot_dataset,
        "rlds": embodied.export_embodied_rlds,
        "hdf5": embodied.export_embodied_hdf5,
        "lerobot_jsonl": embodied.export_embodied_lerobot,
        "torque_csv": embodied.export_embodied_torque_csv,
        "raw_json": _raw_json,
    },
}


def normalize_category(category: Optional[str]) -> str:
    c = (category or "").strip().lower()
    if c in FORMATS_BY_CATEGORY:
        return c
    # legacy aliases
    aliases = {
        "image": "image_2d",
        "2d": "image_2d",
        "pointcloud": "pointcloud_3d",
        "3d": "pointcloud_3d",
        "text": "nlp",
        "corpus": "nlp",
        "speech": "audio",
        "robot": "embodied",
    }
    return aliases.get(c, "image_2d")


def list_formats(category: Optional[str], include_raw: bool = True) -> List[FormatMeta]:
    cat = normalize_category(category)
    primary = list(FORMATS_BY_CATEGORY.get(cat, FORMATS_BY_CATEGORY["image_2d"]))
    if include_raw:
        return primary + [RAW_META]
    return primary


def default_format_for(category: Optional[str]) -> str:
    formats = list_formats(category, include_raw=False)
    return formats[0].id if formats else "raw_json"


def build_export(
    category: Optional[str],
    format_id: str,
    tasks: List[Any],
    project_name: str,
    label_classes: Optional[List[Dict]] = None,
) -> ExportArtifact:
    cat = normalize_category(category)
    fmt = (format_id or "").strip().lower()
    if fmt in ("json",) and cat != "embodied":
        # legacy json → raw
        fmt = "raw_json"
    exporters = _EXPORTERS.get(cat) or _EXPORTERS["image_2d"]
    fn = exporters.get(fmt)
    if not fn:
        allowed = ", ".join(e.id for e in list_formats(cat))
        raise ValueError(f"类别 {cat} 不支持格式 {format_id}；可选: {allowed}")
    return fn(tasks, project_name, label_classes if isinstance(label_classes, list) else None)
