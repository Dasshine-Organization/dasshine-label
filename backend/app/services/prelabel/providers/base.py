"""预标注推理提供方基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from app.services.prelabel.types import PrelabelRunResult


class BasePrelabelProvider(ABC):
    model_id: str

    @abstractmethod
    def load(self) -> None:
        """加载 / 预热模型"""

    @abstractmethod
    def unload(self) -> None:
        pass

    @abstractmethod
    async def predict(self, image_url: str, frame_index: int = 0) -> PrelabelRunResult:
        pass

    def is_loaded(self) -> bool:
        return False
