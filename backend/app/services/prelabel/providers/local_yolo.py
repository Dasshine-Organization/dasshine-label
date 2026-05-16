"""本地 Ultralytics YOLO"""

from __future__ import annotations

import uuid
from io import BytesIO
from typing import Any, Dict, List, Optional

import httpx
from PIL import Image

from app.core.config import settings
from app.services.prelabel.providers.base import BasePrelabelProvider
from app.services.prelabel.types import PrelabelBBox, PrelabelRunResult

# COCO 部分类别着色
_LABEL_COLORS = {
    "person": "#7c3aed",
    "car": "#00d4ff",
    "truck": "#00d4ff",
    "bus": "#00d4ff",
    "bicycle": "#10b981",
    "motorcycle": "#10b981",
}


async def _fetch_image_size(url: str) -> tuple[int, int, Image.Image]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        return img.width, img.height, img


def _boxes_to_annotations(boxes: List[PrelabelBBox]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for b in boxes:
        out.append(
            {
                "id": str(uuid.uuid4()),
                "type": "bbox",
                "label": b.label,
                "color": b.color,
                "points": [{"x": b.x1, "y": b.y1}, {"x": b.x2, "y": b.y2}],
                "visible": True,
                "locked": False,
                "score": b.score,
                "isAI": True,
            }
        )
    return out


class LocalYoloProvider(BasePrelabelProvider):
    model_id = "yolov8_local"

    def __init__(self) -> None:
        self._model: Any = None

    def load(self) -> None:
        from ultralytics import YOLO

        path = str(settings.resolved_yolo_weights_path())
        self._model = YOLO(path)

    def unload(self) -> None:
        self._model = None

    def is_loaded(self) -> bool:
        return self._model is not None

    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        if not self._model:
            raise RuntimeError("模型未加载，请先调用 load")

        w, h, pil = await _fetch_image_size(image_url)
        # ultralytics 支持 PIL / path / url
        results = self._model.predict(pil, verbose=False)
        boxes: List[PrelabelBBox] = []
        for r in results:
            names = r.names or {}
            if r.boxes is None:
                continue
            for box in r.boxes:
                xyxy = box.xyxy[0].tolist()
                cls_id = int(box.cls[0].item()) if box.cls is not None else 0
                conf = float(box.conf[0].item()) if box.conf is not None else 0.0
                label = names.get(cls_id, str(cls_id))
                color = _LABEL_COLORS.get(label, "#00d4ff")
                boxes.append(
                    PrelabelBBox(
                        label=label,
                        x1=xyxy[0],
                        y1=xyxy[1],
                        x2=xyxy[2],
                        y2=xyxy[3],
                        score=conf,
                        color=color,
                    )
                )

        anns = _boxes_to_annotations(boxes)
        overall = sum(b.score for b in boxes) / max(len(boxes), 1) if boxes else 0.0
        return PrelabelRunResult(
            model_id=self.model_id,
            provider="local",
            annotations2d=anns,
            confidence=overall,
            image_width=w,
            image_height=h,
            inference_source="local",
            message=f"本地 YOLO 检测到 {len(boxes)} 个目标",
        )
