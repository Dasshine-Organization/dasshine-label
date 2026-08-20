"""HTTP Range 与点云分片读取（大视频 / 大 PCD）。"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
DEFAULT_CHUNK_POINTS = 20_000
MAX_SAMPLE_POINTS = 65_000


def _np():
    import numpy as np

    return np

STREAM_CHUNK_BYTES = 1024 * 1024


def parse_range(header: Optional[str], size: int) -> Optional[Tuple[int, int]]:
    """解析 Range 头，返回闭区间 (start, end)。

    无 Range / 无法解析 / 越界时返回 None。调用方：无头则整文件；有头但 None 应 416。
    """
    if not header or size <= 0:
        return None
    first = header.split(",")[0].strip().replace(" ", "")
    m = RANGE_RE.fullmatch(first)
    if not m:
        return None
    start_s, end_s = m.group(1), m.group(2)
    if start_s == "" and end_s == "":
        return None
    if start_s == "":
        suffix = int(end_s)
        if suffix <= 0:
            return None
        start = max(0, size - suffix)
        return start, size - 1
    start = int(start_s)
    if start >= size:
        return None
    end = int(end_s) if end_s else size - 1
    end = min(end, size - 1)
    if end < start:
        return None
    return start, end


def iter_file_range(path: Path, start: int, end: int, chunk_size: int = STREAM_CHUNK_BYTES) -> Iterator[bytes]:
    remaining = end - start + 1
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            buf = f.read(min(chunk_size, remaining))
            if not buf:
                break
            remaining -= len(buf)
            yield buf


def kitti_to_scene(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """KITTI: x 前 y 左 z 上 → Three.js y 上。"""
    return (x, z, -y)


def _pcd_header_fields(text: str) -> Tuple[List[str], int, str, int]:
    """返回 fields, points, data_kind, header_bytes（utf-8）。"""
    fields = ["x", "y", "z"]
    points = 0
    data_kind = "ascii"
    header_chars = 0
    for line in text.splitlines(keepends=True):
        header_chars += len(line)
        s = line.strip()
        if s.startswith("FIELDS"):
            fields = s[6:].split()
        elif s.startswith("POINTS"):
            try:
                points = int(s[6:].strip())
            except ValueError:
                points = 0
        elif s.startswith("DATA"):
            data_kind = s[4:].strip().lower() or "ascii"
            break
    return fields, points, data_kind, header_chars


def sample_kitti_bin(path: Path, max_points: int = MAX_SAMPLE_POINTS) -> Any:
    np = _np()
    size = path.stat().st_size
    total = size // 16
    if total <= 0:
        return np.zeros((0, 3), dtype=np.float32)
    stride = max(1, math.ceil(total / max_points))
    out: List[Tuple[float, float, float]] = []
    with path.open("rb") as f:
        i = 0
        while i < total and len(out) < max_points:
            f.seek(i * 16)
            buf = f.read(12)
            if len(buf) < 12:
                break
            x, y, z = struct.unpack("<fff", buf)
            out.append(kitti_to_scene(x, y, z))
            i += stride
    return np.asarray(out, dtype=np.float32)


def sample_pcd_ascii(path: Path, max_points: int = MAX_SAMPLE_POINTS) -> Any:
    np = _np()
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    fields, points, kind, _ = _pcd_header_fields(text)
    if kind != "ascii":
        raise ValueError("仅支持 ASCII PCD 分片（binary PCD 请转 ascii 或用 .bin）")
    xi, yi, zi = fields.index("x"), fields.index("y"), fields.index("z")
    body = False
    read = 0
    stride = max(1, math.ceil((points or 1) / max_points)) if points else 1
    out: List[Tuple[float, float, float]] = []
    for line in text.splitlines():
        s = line.strip()
        if not body:
            if s.startswith("DATA"):
                body = True
            continue
        if not s or s.startswith("#"):
            continue
        if points and read % stride == 0:
            parts = s.split()
            try:
                x, y, z = float(parts[xi]), float(parts[yi]), float(parts[zi])
            except (IndexError, ValueError):
                read += 1
                continue
            out.append(kitti_to_scene(x, y, z))
            if len(out) >= max_points:
                break
        read += 1
    return np.asarray(out, dtype=np.float32)


def sample_pointcloud(path: Path, max_points: int = MAX_SAMPLE_POINTS) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".bin":
        return sample_kitti_bin(path, max_points)
    return sample_pcd_ascii(path, max_points)


def pointcloud_chunk(
    path: Path,
    chunk: int = 0,
    points_per_chunk: int = DEFAULT_CHUNK_POINTS,
    max_points: int = MAX_SAMPLE_POINTS,
) -> Dict:
    pts = sample_pointcloud(path, max_points=max_points)
    total = int(pts.shape[0])
    ppc = max(1, int(points_per_chunk))
    total_chunks = max(1, math.ceil(total / ppc)) if total else 1
    chunk = max(0, int(chunk))
    start = chunk * ppc
    sl = pts[start : start + ppc]
    bounds = None
    if total:
        mn = pts.min(axis=0)
        mx = pts.max(axis=0)
        bounds = {
            "min": {"x": float(mn[0]), "y": float(mn[1]), "z": float(mn[2])},
            "max": {"x": float(mx[0]), "y": float(mx[1]), "z": float(mx[2])},
        }
    return {
        "chunk": chunk,
        "total_chunks": total_chunks,
        "total_points": total,
        "count": int(sl.shape[0]),
        "positions": sl.reshape(-1).astype(np.float32).tolist(),
        "bounds": bounds,
        "source": path.name,
    }
