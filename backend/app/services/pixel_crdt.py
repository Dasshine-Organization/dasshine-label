"""稀疏像素 / 点标签 CRDT 辅助（与前端 lib/pixelCrdt.ts 对齐）。"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

PIXEL_CAP = 200_000


def pixel_key(x: int, y: int) -> str:
    return f"{int(x)},{int(y)}"


def parse_pixel_key(key: str) -> Tuple[int, int]:
    a, b = str(key).split(",", 1)
    return int(a), int(b)


def paint_disk(
    pixels: Dict[str, str],
    cx: int,
    cy: int,
    radius: int,
    label: str,
    *,
    erase: bool = False,
    cap: int = PIXEL_CAP,
) -> Dict[str, str]:
    r = max(1, int(radius))
    r2 = r * r
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r2:
                continue
            k = pixel_key(cx + dx, cy + dy)
            if erase:
                pixels.pop(k, None)
            elif k in pixels or len(pixels) < cap:
                pixels[k] = label
    return pixels


def merge_point_labels(
    current: Dict[str, str],
    patch: Dict[str, Optional[str]],
) -> Dict[str, str]:
    out = dict(current)
    for k, v in patch.items():
        if v is None or v == "":
            out.pop(str(k), None)
        else:
            out[str(k)] = str(v)
    return out


def object_keys(kind: str, ids: Iterable[str]) -> list[str]:
    prefix = "a:" if kind == "ann" else "b:"
    return [f"{prefix}{i}" for i in ids]
