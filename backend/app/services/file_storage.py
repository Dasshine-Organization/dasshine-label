"""项目数据文件存储：写入本地 UPLOAD_DIR，通过 FILE_SERVER_BASE_URL 对外提供 URL"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE)
    return base or "file"


class FileStorageService:
    def __init__(self, file_server_base_url: Optional[str] = None):
        self.base_url = (file_server_base_url or settings.FILE_SERVER_BASE_URL).rstrip("/")
        self.upload_root = Path(settings.UPLOAD_DIR).resolve()

    def project_dir(self, project_id: int) -> Path:
        d = self.upload_root / "projects" / str(project_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_bytes(
        self,
        project_id: int,
        filename: str,
        content: bytes,
        *,
        subdir: str = "",
    ) -> Tuple[str, str]:
        """保存文件，返回 (相对路径, 公网 data_url)"""
        safe = _safe_filename(filename)
        ext = Path(safe).suffix.lower()
        unique = f"{uuid.uuid4().hex[:12]}{ext}" if ext else uuid.uuid4().hex[:12]

        dest_dir = self.project_dir(project_id)
        if subdir:
            dest_dir = dest_dir / subdir.strip("/\\")
            dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / unique
        dest.write_bytes(content)

        rel = dest.relative_to(self.upload_root).as_posix()
        public_url = f"{self.base_url}/uploads/{rel}"
        return rel, public_url

    def url_for_relative(self, relative_path: str) -> str:
        rel = relative_path.lstrip("/").replace("\\", "/")
        return f"{self.base_url}/uploads/{rel}"
