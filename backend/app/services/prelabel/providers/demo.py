"""演示模板：固定候选框"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from app.services.prelabel.providers.base import BasePrelabelProvider
from app.services.prelabel.types import PrelabelRunResult


class DemoTemplateProvider(BasePrelabelProvider):
    model_id = "demo_template"
    _loaded = False

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def is_loaded(self) -> bool:
        return self._loaded

    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        templates: List[List[Dict[str, Any]]] = [
            [
                {"label": "car", "color": "#00d4ff", "points": [{"x": 120, "y": 200}, {"x": 360, "y": 380}], "score": 0.94},
                {"label": "person", "color": "#7c3aed", "points": [{"x": 440, "y": 120}, {"x": 510, "y": 310}], "score": 0.88},
            ],
            [
                {"label": "person", "color": "#7c3aed", "points": [{"x": 80, "y": 150}, {"x": 160, "y": 350}], "score": 0.82},
                {"label": "car", "color": "#00d4ff", "points": [{"x": 300, "y": 240}, {"x": 550, "y": 400}], "score": 0.95},
            ],
        ]
        tpl = templates[frame_index % len(templates)]
        anns = [
            {
                "id": str(uuid.uuid4()),
                "type": "bbox",
                "label": b["label"],
                "color": b["color"],
                "points": b["points"],
                "visible": True,
                "locked": False,
                "score": b["score"],
                "isAI": True,
            }
            for b in tpl
        ]
        conf = sum(float(b["score"]) for b in tpl) / max(len(tpl), 1)
        return PrelabelRunResult(
            model_id=self.model_id,
            provider="demo",
            annotations2d=anns,
            confidence=conf,
            image_width=1280,
            image_height=720,
            inference_source="demo",
            message="演示模板结果（非真实模型推理）",
        )
