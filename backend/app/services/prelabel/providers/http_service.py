"""自定义 HTTP 推理端点

约定 POST JSON:
  { "image_url": "...", "frame_index": 0 }
响应:
  { "annotations2d": [...], "confidence": 0.9, "image_width": 1280, "image_height": 720 }
"""

from __future__ import annotations

from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.services.prelabel.providers.base import BasePrelabelProvider
from app.services.prelabel.types import PrelabelRunResult


class HttpPrelabelProvider(BasePrelabelProvider):
    model_id = "prelabel_http"
    _loaded = False

    def load(self) -> None:
        if not settings.PRELABEL_HTTP_ENDPOINT:
            raise ValueError("PRELABEL_HTTP_ENDPOINT 未配置")
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if settings.PRELABEL_HTTP_API_KEY:
            headers["Authorization"] = f"Bearer {settings.PRELABEL_HTTP_API_KEY}"

        payload = {"image_url": image_url, "frame_index": frame_index}
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(settings.PRELABEL_HTTP_ENDPOINT, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        anns: List[Dict[str, Any]] = data.get("annotations2d") or data.get("annotations") or []
        conf = float(data.get("confidence", 0.0))
        if not conf and anns:
            scores = [float(a.get("score", 0)) for a in anns if a.get("score") is not None]
            conf = sum(scores) / max(len(scores), 1)

        return PrelabelRunResult(
            model_id=self.model_id,
            provider="http",
            annotations2d=anns,
            confidence=conf,
            image_width=int(data.get("image_width", 1280)),
            image_height=int(data.get("image_height", 720)),
            inference_source="http",
            message=data.get("message", "HTTP 推理服务"),
        )
