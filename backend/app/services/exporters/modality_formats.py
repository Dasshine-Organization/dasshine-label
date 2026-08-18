"""NLP / 语音 / 视频 / OCR / 多模态导出。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.services.exporters.common import (
    dumps_json,
    dumps_jsonl,
    modality_annotation,
    modality_content,
    primary_payload,
    rows_to_csv,
    task_file_name,
)
from app.services.exporters.types import ExportArtifact
from app.services.video_tracks import sampled_track_boxes


def _generic_csv(tasks: List[Any], suffix: str) -> ExportArtifact:
    rows: List[List[Any]] = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        rows.append(
            [
                task.id,
                getattr(task, "data_url", "") or "",
                content.get("text") or "",
                json.dumps(ann, ensure_ascii=False),
            ]
        )
    text = rows_to_csv(["task_id", "data_url", "text", "annotation"], rows)
    return ExportArtifact(content=text.encode("utf-8"), filename_suffix=suffix, media_type="text/csv")


# ── NLP ──────────────────────────────────────────────────────────────────────


def export_nlp_jsonl(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        rows.append(
            {
                "id": task.id,
                "project": project_name,
                "text": content.get("text") or "",
                "spans": ann.get("spans") or [],
                "classification_labels": ann.get("classification_labels") or [],
                "sentiment": ann.get("sentiment"),
                "qa_pairs": ann.get("qa_pairs") or [],
                "summary": ann.get("summary") or "",
                "translation": ann.get("translation") or "",
                "ann_type": ann.get("ann_type") or payload.get("ann_type"),
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_nlp.jsonl",
        media_type="application/x-ndjson",
    )


def _bio_tags(text: str, spans: List[Dict[str, Any]]) -> List[str]:
    """字符级 BIO（按空白分词近似；无空格语言退化为整句单 token）。"""
    tokens = text.split() if text.strip() else ([] if not text else [text])
    if not tokens:
        return []
    # char offsets of tokens
    offsets = []
    pos = 0
    for tok in tokens:
        idx = text.find(tok, pos)
        if idx < 0:
            idx = pos
        offsets.append((idx, idx + len(tok), tok))
        pos = idx + len(tok)
    tags = ["O"] * len(tokens)
    for sp in spans or []:
        try:
            start = int(sp.get("start", 0))
            end = int(sp.get("end", start))
        except (TypeError, ValueError):
            continue
        label = str(sp.get("label") or "ENT")
        first = True
        for i, (s, e, _) in enumerate(offsets):
            if e <= start or s >= end:
                continue
            tags[i] = f"B-{label}" if first else f"I-{label}"
            first = False
    return [f"{tok}\t{tag}" for tok, tag in zip([o[2] for o in offsets], tags)]


def export_nlp_conll(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    blocks: List[str] = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        text = content.get("text") or ""
        lines = _bio_tags(text, ann.get("spans") or [])
        if not lines and text:
            lines = [f"{text}\tO"]
        header = f"# task_id={task.id}"
        blocks.append(header + "\n" + "\n".join(lines))
    body = "\n\n".join(blocks) + ("\n" if blocks else "")
    return ExportArtifact(
        content=body.encode("utf-8"),
        filename_suffix="_conll.txt",
        media_type="text/plain",
    )


def export_nlp_csv(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = project_name, label_classes
    return _generic_csv(tasks, "_nlp.csv")


# ── Audio ────────────────────────────────────────────────────────────────────


def export_audio_jsonl(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        rows.append(
            {
                "utt_id": str(task.id),
                "project": project_name,
                "path": content.get("audio_url") or getattr(task, "data_url", None),
                "text": ann.get("transcript") or content.get("text") or "",
                "segments": ann.get("segments") or [],
                "speakers": ann.get("speakers") or [],
                "emotion": ann.get("emotion"),
                "mos": ann.get("mos"),
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_asr.jsonl",
        media_type="application/x-ndjson",
    )


def export_audio_rttm(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    lines: List[str] = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        file_id = task_file_name(task).rsplit(".", 1)[0]
        for seg in ann.get("segments") or []:
            try:
                start_ms = float(seg.get("start_ms", 0))
                end_ms = float(seg.get("end_ms", start_ms))
            except (TypeError, ValueError):
                continue
            dur = max(0.0, (end_ms - start_ms) / 1000.0)
            start_s = start_ms / 1000.0
            speaker = str(seg.get("speaker") or "SPEAKER")
            # SPEAKER file_id 1 start dur <NA> <NA> speaker <NA> <NA>
            lines.append(
                f"SPEAKER {file_id} 1 {start_s:.3f} {dur:.3f} <NA> <NA> {speaker} <NA> <NA>"
            )
    body = "\n".join(lines) + ("\n" if lines else "")
    return ExportArtifact(
        content=body.encode("utf-8"),
        filename_suffix="_diarization.rttm",
        media_type="text/plain",
    )


def export_audio_csv(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = project_name, label_classes
    return _generic_csv(tasks, "_audio.csv")


# ── Video ────────────────────────────────────────────────────────────────────


def export_video_jsonl(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        clips = ann.get("clips") or []
        tracks = [t for t in (ann.get("tracks") or []) if isinstance(t, dict)]
        rows.append(
            {
                "video_id": str(task.id),
                "project": project_name,
                "url": content.get("video_url") or getattr(task, "data_url", None),
                "caption": ann.get("caption") or "",
                "annotations": [
                    {
                        "segment": [c.get("start_sec"), c.get("end_sec")],
                        "label": c.get("label"),
                        "note": c.get("note"),
                    }
                    for c in clips
                    if isinstance(c, dict)
                ],
                "tracks": [
                    {
                        "track_id": t.get("track_id"),
                        "label": t.get("label"),
                        "color": t.get("color"),
                        "keyframes": t.get("keyframes") or [],
                        "sampled": sampled_track_boxes(t, fps=5.0),
                    }
                    for t in tracks
                ],
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_activitynet.jsonl",
        media_type="application/x-ndjson",
    )


def _sec_to_vtt(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def export_video_webvtt(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    parts: List[str] = ["WEBVTT", ""]
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        parts.append(f"NOTE task_id={task.id}")
        clips = ann.get("clips") or []
        if ann.get("caption") and not clips:
            parts.append("00:00:00.000 --> 99:00:00.000")
            parts.append(str(ann.get("caption")))
            parts.append("")
        for i, c in enumerate(clips):
            if not isinstance(c, dict):
                continue
            start = float(c.get("start_sec") or 0)
            end = float(c.get("end_sec") or start)
            parts.append(f"{_sec_to_vtt(start)} --> {_sec_to_vtt(end)}")
            text = c.get("label") or c.get("note") or f"clip_{i}"
            parts.append(str(text))
            parts.append("")
    body = "\n".join(parts)
    return ExportArtifact(
        content=body.encode("utf-8"),
        filename_suffix="_captions.vtt",
        media_type="text/vtt",
    )


def export_video_csv(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = project_name, label_classes
    return _generic_csv(tasks, "_video.csv")


# ── OCR ──────────────────────────────────────────────────────────────────────


def _ocr_items(ann: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(ann.get("spans"), list) and ann["spans"]:
        return [s for s in ann["spans"] if isinstance(s, dict)]
    if isinstance(ann.get("boxes"), list):
        return [s for s in ann["boxes"] if isinstance(s, dict)]
    if isinstance(ann.get("ocr_results"), list):
        return [s for s in ann["ocr_results"] if isinstance(s, dict)]
    return []


def export_ocr_jsonl(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        items = _ocr_items(ann)
        rows.append(
            {
                "id": task.id,
                "project": project_name,
                "image_url": content.get("image_url") or getattr(task, "data_url", None),
                "file_name": task_file_name(task),
                "texts": [
                    {
                        "text": it.get("text") or it.get("label") or "",
                        "bbox": it.get("bbox") or it.get("points"),
                        "label": it.get("label"),
                        "rows": it.get("rows"),
                        "cols": it.get("cols"),
                        "cells": it.get("cells") or [],
                    }
                    for it in items
                ],
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_ocr.jsonl",
        media_type="application/x-ndjson",
    )


def export_ocr_coco_text(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    images = []
    annotations = []
    ann_id = 1
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        file_name = task_file_name(task)
        images.append(
            {
                "id": task.id,
                "file_name": file_name,
                "coco_url": getattr(task, "data_url", None),
            }
        )
        for it in _ocr_items(ann):
            text = it.get("text") or it.get("label") or ""
            bbox = it.get("bbox")
            if not bbox and isinstance(it.get("points"), list) and len(it["points"]) >= 2:
                # approximate
                from app.services.coco_export import bbox_xywh

                xy = bbox_xywh({"type": "bbox", "points": it["points"]})
                bbox = list(xy) if xy else None
            annotations.append(
                {
                    "id": ann_id,
                    "image_id": task.id,
                    "utf8_string": text,
                    "bbox": bbox,
                    "area": (bbox[2] * bbox[3]) if isinstance(bbox, (list, tuple)) and len(bbox) >= 4 else 0,
                    "category_id": 1,
                }
            )
            ann_id += 1
    doc = {
        "info": {"description": project_name, "version": "coco_text_lite"},
        "images": images,
        "annotations": annotations,
        "categories": [{"id": 1, "name": "text"}],
    }
    return ExportArtifact(
        content=dumps_json(doc),
        filename_suffix="_coco_text.json",
        media_type="application/json",
    )


def export_ocr_paddle(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    lines: List[str] = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        file_name = task_file_name(task)
        items = []
        for it in _ocr_items(ann):
            text = it.get("text") or it.get("label") or ""
            pts = it.get("points") or it.get("bbox")
            items.append({"transcription": text, "points": pts})
        lines.append(f"{file_name}\t{json.dumps(items, ensure_ascii=False)}")
    body = "\n".join(lines) + ("\n" if lines else "")
    return ExportArtifact(
        content=body.encode("utf-8"),
        filename_suffix="_paddleocr.txt",
        media_type="text/plain",
    )


# ── Multimodal ───────────────────────────────────────────────────────────────


def export_mm_jsonl(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        vqa = ann.get("vqa") if isinstance(ann.get("vqa"), dict) else {}
        rows.append(
            {
                "id": task.id,
                "project": project_name,
                "image": content.get("image_url") or getattr(task, "data_url", None),
                "caption": ann.get("caption") or "",
                "question": vqa.get("question") or "",
                "answer": vqa.get("answer") or "",
                "preferences": ann.get("preferences") or [],
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_multimodal.jsonl",
        media_type="application/x-ndjson",
    )


def export_mm_sharegpt(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    rows = []
    for task in tasks:
        payload = primary_payload(task)
        ann = modality_annotation(payload)
        content = modality_content(task, payload)
        vqa = ann.get("vqa") if isinstance(ann.get("vqa"), dict) else {}
        conversations = []
        if ann.get("caption"):
            conversations.append({"from": "human", "value": "<image>\n请描述这张图片。"})
            conversations.append({"from": "gpt", "value": str(ann.get("caption"))})
        if vqa.get("question"):
            conversations.append({"from": "human", "value": f"<image>\n{vqa.get('question')}"})
            conversations.append({"from": "gpt", "value": str(vqa.get("answer") or "")})
        for pref in ann.get("preferences") or []:
            if not isinstance(pref, dict):
                continue
            winner = pref.get("winner") or "a"
            chosen = pref.get("response_a") if winner == "a" else pref.get("response_b")
            if winner == "tie":
                chosen = pref.get("response_a") or pref.get("response_b") or ""
            conversations.append(
                {
                    "from": "human",
                    "value": f"<image>\n{pref.get('prompt') or 'Which response is better?'}",
                }
            )
            conversations.append({"from": "gpt", "value": str(chosen or "")})
        if not conversations:
            conversations.append({"from": "human", "value": "<image>"})
            conversations.append({"from": "gpt", "value": ""})
        rows.append(
            {
                "id": f"dasshine_{task.id}",
                "image": content.get("image_url") or getattr(task, "data_url", None),
                "conversations": conversations,
                "project": project_name,
            }
        )
    return ExportArtifact(
        content=dumps_jsonl(rows),
        filename_suffix="_sharegpt.jsonl",
        media_type="application/x-ndjson",
    )


def export_mm_csv(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = project_name, label_classes
    return _generic_csv(tasks, "_multimodal.csv")
