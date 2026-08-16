"""具身策略权重托管桩（上传 / 列表 / 激活；推理仍走 HTTP）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings


def _weights_root() -> Path:
    root = Path(getattr(settings, "EMBODIED_POLICY_WEIGHTS_DIR", None) or Path(settings.UPLOAD_DIR) / "embodied_policies")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _registry_path() -> Path:
    return _weights_root() / "registry.json"


def _load_registry() -> Dict[str, Any]:
    path = _registry_path()
    if not path.is_file():
        return {"active_id": None, "items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"active_id": None, "items": []}
        data.setdefault("active_id", None)
        data.setdefault("items", [])
        return data
    except Exception:
        return {"active_id": None, "items": []}


def _save_registry(reg: Dict[str, Any]) -> None:
    path = _registry_path()
    path.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")


def list_policy_weights() -> Dict[str, Any]:
    reg = _load_registry()
    return {
        "active_id": reg.get("active_id"),
        "items": list(reg.get("items") or []),
        "weights_dir": str(_weights_root()),
    }


def get_active_weight() -> Optional[Dict[str, Any]]:
    reg = _load_registry()
    active = reg.get("active_id")
    if not active:
        return None
    for item in reg.get("items") or []:
        if isinstance(item, dict) and item.get("id") == active:
            return item
    return None


def save_policy_weight(
    *,
    filename: str,
    content: bytes,
    name: Optional[str] = None,
    note: str = "",
) -> Dict[str, Any]:
    wid = uuid.uuid4().hex[:12]
    safe = Path(filename).name or "model.bin"
    dest_dir = _weights_root() / wid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe
    dest.write_bytes(content)
    item = {
        "id": wid,
        "name": (name or Path(safe).stem or wid).strip(),
        "filename": safe,
        "path": str(dest),
        "size_bytes": len(content),
        "note": note or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reg = _load_registry()
    items: List[Dict[str, Any]] = list(reg.get("items") or [])
    items.append(item)
    reg["items"] = items
    if not reg.get("active_id"):
        reg["active_id"] = wid
    _save_registry(reg)
    return item


def activate_policy_weight(weight_id: str) -> Dict[str, Any]:
    reg = _load_registry()
    found = None
    for item in reg.get("items") or []:
        if isinstance(item, dict) and item.get("id") == weight_id:
            found = item
            break
    if not found:
        raise ValueError("权重不存在")
    reg["active_id"] = weight_id
    _save_registry(reg)
    return found


def delete_policy_weight(weight_id: str) -> None:
    reg = _load_registry()
    items = [x for x in (reg.get("items") or []) if isinstance(x, dict) and x.get("id") != weight_id]
    if len(items) == len(reg.get("items") or []):
        raise ValueError("权重不存在")
    # best-effort remove files
    d = _weights_root() / weight_id
    if d.is_dir():
        for f in d.iterdir():
            try:
                f.unlink()
            except OSError:
                pass
        try:
            d.rmdir()
        except OSError:
            pass
    reg["items"] = items
    if reg.get("active_id") == weight_id:
        reg["active_id"] = items[0]["id"] if items else None
    _save_registry(reg)
