"""
LLM/OCR 自动标注服务。

真实推理尚未接入：process / batch 一律 NotImplementedError → API 501。
2D 图像预标注请使用 /tasks/{id}/prelabel/*。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

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


_UNAVAILABLE = (
    "LLM/OCR 自动标注尚未接入真实模型。"
    "2D 图像请使用 /tasks/{id}/prelabel/run。"
)


class AutoLabelService:
    CONFIDENCE_THRESHOLD = 0.8

    def __init__(self, db: Session):
        self.db = db

    async def process_task(self, task_id: int) -> Optional[AutoLabelOutput]:
        raise NotImplementedError(_UNAVAILABLE)

    async def batch_process(
        self, project_id: int, batch_size: int = 100
    ) -> Dict[str, Any]:
        raise NotImplementedError(_UNAVAILABLE)


def get_auto_label_service(db: Session) -> AutoLabelService:
    return AutoLabelService(db)
