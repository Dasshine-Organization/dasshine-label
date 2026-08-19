"""大文件 Range 流与点云分片 API。"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.services.media_range import (
    DEFAULT_CHUNK_POINTS,
    iter_file_range,
    parse_range,
    pointcloud_chunk,
)

router = APIRouter(tags=["media"])


def resolve_upload_path(rel: str) -> Path:
    root = Path(settings.UPLOAD_DIR).resolve()
    cleaned = (rel or "").lstrip("/").replace("\\", "/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise HTTPException(status_code=400, detail="非法路径")
    path = (root / cleaned).resolve()
    try:
        path.relative_to(root)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="路径越界") from e
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return path


def _media_type(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(path.name)
    if ctype:
        return ctype
    if path.suffix.lower() in {".pcd", ".bin"}:
        return "application/octet-stream"
    if path.suffix.lower() in {".mp4", ".webm", ".mkv"}:
        return "video/mp4"
    return "application/octet-stream"


@router.get("/media/file/{file_path:path}")
def stream_upload_file(file_path: str, request: Request):
    """带 Accept-Ranges 的媒体流，支持大视频 Range 分片。"""
    path = resolve_upload_path(file_path)
    size = path.stat().st_size
    media_type = _media_type(path)
    parsed = parse_range(request.headers.get("range"), size)
    if parsed is None:
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(size),
        }
        return StreamingResponse(
            iter_file_range(path, 0, size - 1) if size else iter([]),
            media_type=media_type,
            headers=headers,
        )
    start, end = parsed
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(length),
    }
    return StreamingResponse(
        iter_file_range(path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


@router.head("/media/file/{file_path:path}")
def head_upload_file(file_path: str):
    path = resolve_upload_path(file_path)
    size = path.stat().st_size
    return Response(
        status_code=200,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(size),
            "Content-Type": _media_type(path),
        },
    )


@router.get("/media/pointcloud")
def get_pointcloud_chunk(
    path: str = Query(..., description="相对 UPLOAD_DIR 的路径"),
    chunk: int = Query(0, ge=0),
    points_per_chunk: int = Query(DEFAULT_CHUNK_POINTS, ge=100, le=65000),
):
    """大 PCD / KITTI bin 分片：服务端采样后按 chunk 返回 float xyz。"""
    file_path = resolve_upload_path(path)
    try:
        return pointcloud_chunk(file_path, chunk=chunk, points_per_chunk=points_per_chunk)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"点云解析失败: {e}") from e
