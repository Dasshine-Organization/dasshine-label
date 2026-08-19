"""
文本 / 语音 / 视频等多模态标注工作区（草稿 + 提交）
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.annotation import Annotation, AnnotationStatus, AnnotationType
from app.models.annotation_draft import AnnotationDraft
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.project_service import _get_schema

TEXT_ANN_TYPES = {"ner", "re", "sentiment", "text_classify", "qa_pair", "summarization", "translation"}
AUDIO_ANN_TYPES = {"asr", "tts_label", "speaker_diarize", "emotion_audio"}
VIDEO_ANN_TYPES = {"video_tracking", "video_action", "video_caption"}


def resolve_modality(category: Optional[str], ann_type: Optional[str]) -> str:
    if ann_type in ("image_caption", "vqa", "rlhf"):
        return "multimodal"
    if category == "ocr" or (ann_type or "").startswith("ocr_"):
        return "ocr"
    if category == "nlp":
        return "text"
    if category == "audio":
        return "audio"
    if category == "video":
        return "video"
    if category == "multimodal":
        return "multimodal"
    if ann_type in TEXT_ANN_TYPES:
        return "text"
    if ann_type in AUDIO_ANN_TYPES:
        return "audio"
    if ann_type in VIDEO_ANN_TYPES:
        return "video"
    return "text"


def default_payload(modality: str, ann_type: str) -> Dict[str, Any]:
    base = {"schema": "dasshine.modality.v1", "modality": modality, "ann_type": ann_type}
    if modality == "ocr":
        payload = {**base, "spans": []}  # {id,text,bbox:[x,y,w,h],label?,rows?,cols?,cells?}
        if ann_type == "ocr_table":
            payload["spans"] = []
        return payload
    if modality == "text":
        return {
            **base,
            "spans": [],
            "classification_labels": [],
            "sentiment": None,
            "qa_pairs": [{"question": "", "answer": ""}],
            "summary": "",
            "translation": "",
        }
    if modality == "audio":
        return {
            **base,
            "segments": [],
            "transcript": "",
            "speakers": ["说话人 A", "说话人 B"],
            "emotion": None,
            "mos": None,
        }
    if modality == "video":
        return {
            **base,
            "clips": [],
            "caption": "",
            "frame_notes": {},
            "tracks": [],
        }
    if modality == "multimodal":
        return {
            **base,
            "caption": "",
            "vqa": {"question": "", "answer": ""},
            "preferences": [],
        }
    return {**base, "caption": "", "vqa": {"question": "", "answer": ""}}


def extract_task_content(task: Task) -> Dict[str, Any]:
    data = task.data or {}
    out: Dict[str, Any] = {
        "text": data.get("text") or data.get("content") or data.get("raw_text") or "",
        "title": data.get("title") or "",
        "audio_url": task.data_url if _is_audio_url(task.data_url) else data.get("audio_url"),
        "video_url": task.data_url if _is_video_url(task.data_url) else data.get("video_url"),
        "image_url": task.data_url if _is_image_url(task.data_url) else data.get("image_url"),
    }
    if not out["audio_url"] and task.data_url and "audio" in str(data.get("media_type", "")):
        out["audio_url"] = task.data_url
    if not out["video_url"] and task.data_url and "video" in str(data.get("media_type", "")):
        out["video_url"] = task.data_url
    # OCR / 无扩展名的图链：回退到 data_url
    if not out["image_url"] and task.data_url and not out["audio_url"] and not out["video_url"]:
        out["image_url"] = task.data_url
    return out


def _is_audio_url(url: Optional[str]) -> bool:
    if not url:
        return False
    return any(url.lower().endswith(ext) for ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac"))


def _is_video_url(url: Optional[str]) -> bool:
    if not url:
        return False
    return any(url.lower().endswith(ext) for ext in (".mp4", ".webm", ".mov", ".mkv"))


def _is_image_url(url: Optional[str]) -> bool:
    if not url:
        return False
    return any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"))


def _annotation_type_for(modality: str, ann_type: str) -> AnnotationType:
    if modality == "ocr":
        return AnnotationType.BOUNDING_BOX
    if modality == "audio":
        return AnnotationType.CLASSIFICATION if ann_type == "emotion_audio" else AnnotationType.TEXT
    if modality == "video":
        return AnnotationType.CLASSIFICATION
    if ann_type == "sentiment":
        return AnnotationType.SENTIMENT
    if ann_type in ("ner", "re"):
        return AnnotationType.NER
    if ann_type == "summarization":
        return AnnotationType.SUMMARY
    if ann_type == "text_classify":
        return AnnotationType.CLASSIFICATION
    return AnnotationType.TEXT


def get_workspace(
    db: Session, task: Task, user: User
) -> Dict[str, Any]:
    schema = _get_schema(task.project)
    category = schema.get("category")
    ann_type = schema.get("ann_type", "ner")
    modality = resolve_modality(category, ann_type)

    draft = (
        db.query(AnnotationDraft)
        .filter(AnnotationDraft.task_id == task.id, AnnotationDraft.user_id == user.id)
        .first()
    )
    payload = (draft.payload if draft and draft.payload else None) or default_payload(modality, ann_type)

    label_classes = schema.get("label_classes") or []
    if modality == "text" and not label_classes:
        label_classes = [
            {"id": "PER", "name": "人名", "color": "#ec4899"},
            {"id": "ORG", "name": "机构", "color": "#00d4ff"},
            {"id": "LOC", "name": "地点", "color": "#10b981"},
        ]
    if modality == "ocr" and not label_classes:
        if ann_type == "ocr_layout":
            label_classes = [
                {"id": "title", "name": "标题", "color": "#f97316"},
                {"id": "paragraph", "name": "段落", "color": "#06b6d4"},
                {"id": "figure", "name": "图像", "color": "#10b981"},
                {"id": "table", "name": "表格", "color": "#a78bfa"},
                {"id": "list", "name": "列表", "color": "#f59e0b"},
                {"id": "header", "name": "页眉", "color": "#64748b"},
                {"id": "footer", "name": "页脚", "color": "#94a3b8"},
            ]
        elif ann_type == "ocr_table":
            label_classes = [
                {"id": "table", "name": "表格", "color": "#a78bfa"},
                {"id": "cell", "name": "单元格", "color": "#06b6d4"},
            ]
        else:
            label_classes = [
                {"id": "text", "name": "文字", "color": "#06b6d4"},
                {"id": "title", "name": "标题", "color": "#f97316"},
                {"id": "table", "name": "表格", "color": "#a78bfa"},
            ]

    return {
        "task_id": task.id,
        "project_id": task.project_id,
        "project_name": task.project.name,
        "category": category,
        "ann_type": ann_type,
        "modality": modality,
        "content": extract_task_content(task),
        "payload": payload,
        "label_classes": label_classes,
        "draft_updated_at": draft.updated_at.isoformat() if draft and draft.updated_at else None,
        "last_reject_feedback": (task.task_metadata or {}).get("last_reject_feedback"),
        "last_reject_targets": (task.task_metadata or {}).get("last_reject_targets") or [],
    }


def save_workspace(db: Session, task: Task, user: User, payload: Dict[str, Any]) -> AnnotationDraft:
    row = (
        db.query(AnnotationDraft)
        .filter(AnnotationDraft.task_id == task.id, AnnotationDraft.user_id == user.id)
        .first()
    )
    if not row:
        row = AnnotationDraft(task_id=task.id, user_id=user.id, payload=payload)
        db.add(row)
    else:
        row.payload = payload
    db.commit()
    db.refresh(row)
    return row


def submit_workspace(
    db: Session, task: Task, user: User, payload: Dict[str, Any], work_time: int
) -> Annotation:
    schema = _get_schema(task.project)
    modality = resolve_modality(schema.get("category"), schema.get("ann_type"))
    ann_type = schema.get("ann_type", "ner")
    atype = _annotation_type_for(modality, ann_type)

    export_doc = {
        "schema": "dasshine.modality_export.v1",
        "task_id": task.id,
        "modality": modality,
        "ann_type": ann_type,
        "content": extract_task_content(task),
        "annotation": payload,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task.id,
            Annotation.annotator_id == user.id,
            Annotation.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        existing.data = export_doc
        existing.work_time = work_time
        existing.version += 1
        ann = existing
    else:
        ann = Annotation(
            id=str(uuid.uuid4()),
            task_id=task.id,
            data_id=str(task.id),
            annotation_type=atype,
            data=export_doc,
            status=AnnotationStatus.COMPLETED,
            annotator_id=user.id,
            work_time=work_time,
            is_latest=True,
        )
        db.add(ann)

    save_workspace(db, task, user, payload)
    from app.services.task_completion import after_annotation_submit

    after_annotation_submit(db, task, user.id, export_doc.get("annotation") or payload, work_time=work_time)
    db.commit()
    db.refresh(ann)
    return ann
