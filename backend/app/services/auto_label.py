"""
LLM / Whisper / OCR 自动标注：HTTP 适配器写入草稿与 pre_label_*，不再 501。
2D 图像仍走 /tasks/{id}/prelabel/*。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.auto_label_adapters import (
    AdapterResult,
    AutoLabelAdapterError,
    AutoLabelConfigError,
    AutoLabelUnsupportedError,
    LabelHit,
    adapter_status,
    infer,
)
from app.services.modality_workspace import (
    default_payload,
    extract_task_content,
    resolve_modality,
    save_workspace,
    submit_workspace,
)
from app.services.project_service import _get_schema

logger = logging.getLogger(__name__)


class AutoLabelType(str, Enum):
    NER = "ner"
    CLASSIFICATION = "classification"
    SENTIMENT = "sentiment"
    SUMMARIZATION = "summarization"
    OCR = "ocr"


@dataclass
class LabelResult:
    label: str
    text: str
    start: Optional[int] = None
    end: Optional[int] = None
    confidence: float = 0.0


@dataclass
class AutoLabelOutput:
    results: List[LabelResult]
    overall_confidence: float
    model: str
    processing_time: float
    raw_response: Optional[str] = None
    adapter: str = "demo"
    recommended: bool = False
    needs_review: bool = True
    draft_written: bool = False
    task_id: Optional[int] = None


def _hit_to_result(h: LabelHit) -> LabelResult:
    return LabelResult(
        label=h.label,
        text=h.text,
        start=h.start,
        end=h.end,
        confidence=h.confidence,
    )


def _field_empty(payload: Dict[str, Any], key: str) -> bool:
    val = payload.get(key)
    if val is None:
        return True
    if isinstance(val, str):
        return not val.strip()
    if isinstance(val, list):
        return len(val) == 0
    if isinstance(val, dict):
        if key == "vqa":
            return not str(val.get("answer") or "").strip()
        return len(val) == 0
    return False


def merge_ai_into_payload(
    payload: Dict[str, Any],
    patch: Dict[str, Any],
    *,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill empty fields; for spans, append non-overlapping AI spans."""
    out = dict(payload or {})
    for key, value in (patch or {}).items():
        if key == "spans":
            existing = list(out.get("spans") or [])
            incoming = list(value or [])
            if not existing:
                out["spans"] = incoming
                continue
            occupied = []
            for s in existing:
                if isinstance(s, dict) and s.get("start") is not None and s.get("end") is not None:
                    occupied.append((int(s["start"]), int(s["end"])))
            merged = list(existing)
            for s in incoming:
                if not isinstance(s, dict):
                    continue
                if s.get("start") is None or s.get("end") is None:
                    merged.append(s)
                    continue
                a, b = int(s["start"]), int(s["end"])
                overlap = any(not (b <= x0 or a >= x1) for x0, x1 in occupied)
                if not overlap:
                    merged.append(s)
                    occupied.append((a, b))
            out["spans"] = merged
            continue
        if _field_empty(out, key):
            out[key] = value
    if meta:
        out["_auto_label"] = meta
    return out


class AutoLabelService:
    CONFIDENCE_THRESHOLD = 0.8

    def __init__(self, db: Session):
        self.db = db

    def _threshold(self, project) -> float:
        t = getattr(project, "auto_label_threshold", None)
        if t is None:
            t = settings.AUTO_LABEL_CONFIDENCE_THRESHOLD
        try:
            return float(t)
        except (TypeError, ValueError):
            return 0.8

    def process_task(self, task_id: int, user_id: Optional[int] = None) -> AutoLabelOutput:
        t0 = time.perf_counter()
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task or not task.project:
            raise AutoLabelUnsupportedError("任务不存在")

        project = task.project
        schema = _get_schema(project)
        ann_type = schema.get("ann_type") or getattr(project, "ann_type", None) or "ner"
        category = schema.get("category") or getattr(project, "category", None)
        modality = resolve_modality(category, ann_type)
        content = extract_task_content(task)
        label_classes = schema.get("label_classes") or []
        model = getattr(project, "auto_label_model", None) or settings.AUTO_LABEL_LLM_MODEL

        result: AdapterResult = infer(
            modality=modality,
            ann_type=ann_type,
            content=content,
            label_classes=label_classes,
            model=model if model and model != "default" else None,
        )

        uid = user_id or task.assignee_id
        user = self.db.query(User).filter(User.id == uid).first() if uid else None
        if not user:
            raise AutoLabelUnsupportedError("无法写入草稿：任务未分配且未指定用户")

        from app.models.annotation_draft import AnnotationDraft

        draft = (
            self.db.query(AnnotationDraft)
            .filter(AnnotationDraft.task_id == task.id, AnnotationDraft.user_id == user.id)
            .first()
        )
        payload = (draft.payload if draft and draft.payload else None) or default_payload(
            modality, ann_type
        )
        threshold = self._threshold(project)
        recommended = result.overall_confidence >= threshold
        meta = {
            "model": result.model,
            "adapter": result.adapter,
            "confidence": result.overall_confidence,
            "recommended": recommended,
            "needs_review": not recommended,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        merged = merge_ai_into_payload(payload, result.payload_patch, meta=meta)
        save_workspace(self.db, task, user, merged)

        task.pre_label_result = {
            "schema": "dasshine.auto_label.v1",
            "model": result.model,
            "adapter": result.adapter,
            "ann_type": ann_type,
            "modality": modality,
            "results": [
                {
                    "label": h.label,
                    "text": h.text,
                    "start": h.start,
                    "end": h.end,
                    "confidence": h.confidence,
                }
                for h in result.hits
            ],
            "payload_patch": result.payload_patch,
            "recommended": recommended,
            "needs_review": not recommended,
            "generated_at": meta["at"],
            "raw": (result.raw_response or "")[:2000] or None,
        }
        task.pre_label_confidence = float(result.overall_confidence)
        self.db.commit()

        if settings.AUTO_LABEL_AUTO_SUBMIT and recommended:
            try:
                submit_workspace(self.db, task, user, merged, work_time=0)
            except Exception:
                logger.exception("auto-submit failed task_id=%s", task_id)

        elapsed = time.perf_counter() - t0
        return AutoLabelOutput(
            results=[_hit_to_result(h) for h in result.hits],
            overall_confidence=result.overall_confidence,
            model=result.model,
            processing_time=round(elapsed, 4),
            raw_response=result.raw_response,
            adapter=result.adapter,
            recommended=recommended,
            needs_review=not recommended,
            draft_written=True,
            task_id=task_id,
        )

    def batch_process(
        self,
        project_id: int,
        batch_size: int = 100,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        from app.models.project import Project

        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise AutoLabelUnsupportedError("项目不存在")

        limit = max(1, min(int(batch_size or 100), 500))
        tasks = (
            self.db.query(Task)
            .filter(
                Task.project_id == project_id,
                Task.pre_label_confidence.is_(None),
                Task.status.notin_(
                    [TaskStatus.APPROVED, TaskStatus.SUBMITTED, TaskStatus.REVIEWING]
                ),
            )
            .order_by(Task.id.asc())
            .limit(limit)
            .all()
        )

        processed = 0
        high = 0
        low = 0
        failed = 0
        errors: List[Dict[str, Any]] = []
        for task in tasks:
            try:
                out = self.process_task(task.id, user_id=user_id or task.assignee_id)
                processed += 1
                if out.recommended:
                    high += 1
                else:
                    low += 1
            except (AutoLabelConfigError, AutoLabelUnsupportedError, AutoLabelAdapterError) as e:
                failed += 1
                errors.append({"task_id": task.id, "error": str(e)})
                logger.warning("auto-label task %s failed: %s", task.id, e)
            except Exception as e:
                failed += 1
                errors.append({"task_id": task.id, "error": str(e)})
                logger.exception("auto-label task %s crashed", task.id)

        return {
            "processed": processed,
            "success": processed,
            "high_confidence": high,
            "low_confidence": low,
            "failed": failed,
            "errors": errors[:20],
            "adapters": adapter_status(),
        }


def get_auto_label_service(db: Session) -> AutoLabelService:
    return AutoLabelService(db)
