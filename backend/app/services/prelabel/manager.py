"""预标注模型加载与会话管理"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from app.services.prelabel.providers.base import BasePrelabelProvider
from app.services.prelabel.registry import get_descriptor, list_catalog, probe_availability
from app.services.prelabel.types import ModelAvailability, PrelabelRunResult

# 进程内已加载实例：key = f"{user_id}:{model_id}"
_loaded: Dict[str, BasePrelabelProvider] = {}
_load_meta: Dict[str, Dict[str, Any]] = {}


def _session_key(user_id: int, model_id: str) -> str:
    return f"{user_id}:{model_id}"


def _create_provider(model_id: str) -> BasePrelabelProvider:
    if model_id == "yolov8_local":
        from app.services.prelabel.providers.local_yolo import LocalYoloProvider

        return LocalYoloProvider()
    if model_id == "yolov8_hf":
        from app.services.prelabel.providers.huggingface import HuggingFaceYoloProvider

        return HuggingFaceYoloProvider()
    if model_id == "detr_hf":
        from app.services.prelabel.providers.huggingface import HuggingFaceDetrProvider

        return HuggingFaceDetrProvider()
    if model_id == "prelabel_http":
        from app.services.prelabel.providers.http_service import HttpPrelabelProvider

        return HttpPrelabelProvider()
    if model_id == "demo_template":
        from app.core.config import settings
        from app.services.prelabel.providers.demo import DemoTemplateProvider

        if not settings.DEBUG:
            raise ValueError("演示模板仅 DEBUG 可用")
        return DemoTemplateProvider()
    raise ValueError(f"未知模型: {model_id}")


def list_models_with_status(user_id: int, loaded_model_id: Optional[str] = None) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for desc in list_catalog():
        avail, msg = probe_availability(desc.id)
        loaded = False
        key = _session_key(user_id, desc.id)
        if key in _loaded and _loaded[key].is_loaded():
            loaded = True
            avail = ModelAvailability.LOADED
            msg = _load_meta.get(key, {}).get("message", "已加载到内存")
        elif loaded_model_id == desc.id and key not in _loaded:
            loaded = False
        out.append(desc.to_dict(avail, msg, loaded=loaded))
    return out


def load_model(user_id: int, model_id: str) -> Dict[str, Any]:
    desc = get_descriptor(model_id)
    if not desc:
        raise ValueError("未知模型 ID")

    avail, probe_msg = probe_availability(model_id)
    if avail == ModelAvailability.UNAVAILABLE:
        raise RuntimeError(probe_msg)
    if avail == ModelAvailability.CONFIG_REQUIRED:
        raise RuntimeError(probe_msg)

    key = _session_key(user_id, model_id)
    # 卸载同用户其它模型以节省内存
    for k in list(_loaded.keys()):
        if k.startswith(f"{user_id}:") and k != key:
            try:
                _loaded[k].unload()
            except Exception:
                pass
            _loaded.pop(k, None)
            _load_meta.pop(k, None)

    t0 = time.perf_counter()
    provider = _loaded.get(key)
    if provider is None or not provider.is_loaded():
        provider = _create_provider(model_id)
        provider.load()
        _loaded[key] = provider

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    message = probe_msg
    if desc.provider.value == "local":
        message = f"本地模型已加载 ({elapsed_ms} ms)"
    elif desc.provider.value == "cloud":
        message = f"云服务已就绪 ({elapsed_ms} ms)"
    elif desc.provider.value == "http":
        message = f"HTTP 端点已验证 ({elapsed_ms} ms)"
    elif desc.provider.value == "demo":
        message = "演示模板已就绪"

    _load_meta[key] = {"loaded_at": time.time(), "message": message, "elapsed_ms": elapsed_ms}
    return {
        "success": True,
        "model_id": model_id,
        "status": ModelAvailability.LOADED.value,
        "status_message": message,
        "load_time_ms": elapsed_ms,
        "provider": desc.provider.value,
    }


def unload_model(user_id: int, model_id: str) -> None:
    key = _session_key(user_id, model_id)
    if key in _loaded:
        _loaded[key].unload()
        del _loaded[key]
    _load_meta.pop(key, None)


def get_loaded_model_id(user_id: int) -> Optional[str]:
    for k, p in _loaded.items():
        if k.startswith(f"{user_id}:") and p.is_loaded():
            return k.split(":", 1)[1]
    return None


async def run_prelabel(
    user_id: int,
    model_id: str,
    image_url: str,
    frame_index: int = 0,
) -> PrelabelRunResult:
    key = _session_key(user_id, model_id)
    provider = _loaded.get(key)
    if not provider or not provider.is_loaded():
        load_model(user_id, model_id)
        provider = _loaded[key]
    return await provider.predict(image_url, frame_index)
