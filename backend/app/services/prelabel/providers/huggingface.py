"""Hugging Face Inference API"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.services.prelabel.providers.base import BasePrelabelProvider
from app.services.prelabel.types import PrelabelRunResult

_LABEL_COLORS = {"person": "#7c3aed", "car": "#00d4ff"}


def _ann_from_box(label: str, x1: float, y1: float, x2: float, y2: float, score: float) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": "bbox",
        "label": label,
        "color": _LABEL_COLORS.get(label, "#00d4ff"),
        "points": [{"x": x1, "y": y1}, {"x": x2, "y": y2}],
        "visible": True,
        "locked": False,
        "score": score,
        "isAI": True,
    }


class HuggingFaceYoloProvider(BasePrelabelProvider):
    model_id = "yolov8_hf"
    _loaded = False

    def load(self) -> None:
        if not settings.PRELABEL_HF_API_TOKEN:
            raise ValueError("PRELABEL_HF_API_TOKEN 未配置")
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        return await _hf_object_detection(
            image_url, settings.PRELABEL_HF_MODEL_ID, self.model_id
        )


async def _hf_object_detection(image_url: str, hf_model_id: str, result_model_id: str) -> PrelabelRunResult:
    api_url = f"https://api-inference.huggingface.co/models/{hf_model_id}"
    headers = {"Authorization": f"Bearer {settings.PRELABEL_HF_API_TOKEN}"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        img_resp = await client.get(image_url, follow_redirects=True)
        img_resp.raise_for_status()
        r = await client.post(api_url, headers=headers, content=img_resp.content)
        r.raise_for_status()
        data = r.json()

    anns: List[Dict[str, Any]] = []
    items = data if isinstance(data, list) else data.get("predictions") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("class") or "object"
        score = float(item.get("score", item.get("confidence", 0.5)))
        box = item.get("box") or item
        if "xmin" in box:
            x1, y1, x2, y2 = box["xmin"], box["ymin"], box["xmax"], box["ymax"]
        elif "x" in box:
            x1, y1 = box["x"], box["y"]
            x2, y2 = x1 + box.get("width", 0), y1 + box.get("height", 0)
        else:
            continue
        anns.append(_ann_from_box(str(label), float(x1), float(y1), float(x2), float(y2), score))

    conf = sum(a["score"] for a in anns) / max(len(anns), 1) if anns else 0.0
    return PrelabelRunResult(
        model_id=result_model_id,
        provider="cloud",
        annotations2d=anns,
        confidence=conf,
        image_width=1280,
        image_height=720,
        inference_source="cloud",
        message=f"Hugging Face ({hf_model_id}) 返回 {len(anns)} 个框",
    )


class HuggingFaceDetrProvider(BasePrelabelProvider):
    model_id = "detr_hf"
    _loaded = False

    def load(self) -> None:
        if not settings.PRELABEL_HF_API_TOKEN:
            raise ValueError("PRELABEL_HF_API_TOKEN 未配置")
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        return await _hf_object_detection(
            image_url, settings.PRELABEL_HF_DETR_MODEL_ID, self.model_id
        )
