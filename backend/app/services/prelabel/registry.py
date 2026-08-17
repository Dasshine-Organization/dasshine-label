"""预标注模型目录（静态定义 + 运行时探测）"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.core.config import settings
from app.services.prelabel.types import ModelAvailability, ModelDescriptor, ModelProvider

MODEL_CATALOG: List[ModelDescriptor] = [
    ModelDescriptor(
        id="yolov8_local",
        label="YOLOv8n · 本地权重",
        provider=ModelProvider.LOCAL,
        kind="supervised",
        description="通过 Ultralytics 在本地加载 yolov8n.pt，需安装 ultralytics",
        config_keys=["PRELABEL_LOCAL_WEIGHTS_DIR", "PRELABEL_YOLO_WEIGHTS"],
    ),
    ModelDescriptor(
        id="yolov8_hf",
        label="YOLOv8 · Hugging Face 推理",
        provider=ModelProvider.CLOUD,
        kind="supervised",
        description="调用 Hugging Face Inference API（需 PRELABEL_HF_API_TOKEN）",
        config_keys=["PRELABEL_HF_API_TOKEN", "PRELABEL_HF_MODEL_ID"],
    ),
    ModelDescriptor(
        id="detr_hf",
        label="DETR · Hugging Face 检测",
        provider=ModelProvider.CLOUD,
        kind="supervised",
        description="facebook/detr-resnet-50 等检测模型",
        config_keys=["PRELABEL_HF_API_TOKEN", "PRELABEL_HF_DETR_MODEL_ID"],
    ),
    ModelDescriptor(
        id="prelabel_http",
        label="自定义 HTTP 推理服务",
        provider=ModelProvider.HTTP,
        kind="supervised",
        description="POST 图片 URL 到自建推理端点，返回 JSON 检测框",
        config_keys=["PRELABEL_HTTP_ENDPOINT", "PRELABEL_HTTP_API_KEY"],
    ),
    ModelDescriptor(
        id="demo_template",
        label="演示模板（无真实模型）",
        provider=ModelProvider.DEMO,
        kind="supervised",
        description="固定候选框，用于联调 UI；无 GPU / 无密钥时可用",
    ),
]

_CATALOG_BY_ID: Dict[str, ModelDescriptor] = {m.id: m for m in MODEL_CATALOG}


def get_descriptor(model_id: str) -> Optional[ModelDescriptor]:
    return _CATALOG_BY_ID.get(model_id)


def list_catalog() -> List[ModelDescriptor]:
    if settings.DEBUG:
        return list(MODEL_CATALOG)
    return [m for m in MODEL_CATALOG if m.provider != ModelProvider.DEMO]


def probe_availability(model_id: str) -> tuple[ModelAvailability, str]:
    """探测模型是否可加载（不实际加载权重）"""
    d = get_descriptor(model_id)
    if not d:
        return ModelAvailability.UNAVAILABLE, "未知模型 ID"

    if d.provider == ModelProvider.DEMO:
        if not settings.DEBUG:
            return ModelAvailability.UNAVAILABLE, "演示模板仅 DEBUG 可用"
        return ModelAvailability.AVAILABLE, "演示模式，无需额外配置"

    if d.provider == ModelProvider.LOCAL:
        if not settings.PRELABEL_ENABLE_LOCAL:
            return ModelAvailability.CONFIG_REQUIRED, "本地模型未启用（设置 PRELABEL_ENABLE_LOCAL=true）"
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            return (
                ModelAvailability.UNAVAILABLE,
                "未安装 ultralytics，请执行: pip install ultralytics",
            )
        weights = settings.resolved_yolo_weights_path()
        if weights.exists():
            return ModelAvailability.AVAILABLE, f"权重文件: {weights.name}"
        return ModelAvailability.AVAILABLE, "将使用 Ultralytics 自动下载 yolov8n.pt"

    if d.provider == ModelProvider.CLOUD:
        if not settings.PRELABEL_HF_API_TOKEN:
            return ModelAvailability.CONFIG_REQUIRED, "请配置 PRELABEL_HF_API_TOKEN"
        if model_id == "detr_hf" and not settings.PRELABEL_HF_DETR_MODEL_ID:
            return ModelAvailability.CONFIG_REQUIRED, "请配置 PRELABEL_HF_DETR_MODEL_ID"
        return ModelAvailability.AVAILABLE, "Hugging Face Inference API 已配置"

    if d.provider == ModelProvider.HTTP:
        if not settings.PRELABEL_HTTP_ENDPOINT:
            return ModelAvailability.CONFIG_REQUIRED, "请配置 PRELABEL_HTTP_ENDPOINT"
        return ModelAvailability.AVAILABLE, settings.PRELABEL_HTTP_ENDPOINT

    return ModelAvailability.UNAVAILABLE, "不支持的提供方"
