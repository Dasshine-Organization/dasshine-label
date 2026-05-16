"""预标注模型类型定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelProvider(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    HTTP = "http"
    DEMO = "demo"


class ModelAvailability(str, Enum):
    AVAILABLE = "available"
    CONFIG_REQUIRED = "config_required"
    UNAVAILABLE = "unavailable"
    LOADED = "loaded"


@dataclass
class ModelDescriptor:
    id: str
    label: str
    provider: ModelProvider
    kind: str  # supervised | unsupervised
    description: str = ""
    config_keys: List[str] = field(default_factory=list)

    def to_dict(self, status: ModelAvailability, message: str = "", loaded: bool = False) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "provider": self.provider.value,
            "kind": self.kind,
            "description": self.description,
            "config_keys": self.config_keys,
            "status": ModelAvailability.LOADED.value if loaded else status.value,
            "status_message": message,
            "loaded": loaded,
        }


@dataclass
class PrelabelBBox:
    label: str
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    color: str = "#00d4ff"


@dataclass
class PrelabelRunResult:
    model_id: str
    provider: str
    annotations2d: List[Dict[str, Any]]
    confidence: float
    image_width: int
    image_height: int
    inference_source: str  # local | cloud | http | demo
    message: str = ""
