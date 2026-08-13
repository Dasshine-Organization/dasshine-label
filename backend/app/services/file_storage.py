"""
文件存储：local 落盘 或 S3 兼容对象存储（MinIO / AWS S3 / OSS S3）。
"""

from __future__ import annotations

import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Tuple

from app.core.config import settings

logger = logging.getLogger("dasshine.storage")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]+", "_", base, flags=re.UNICODE)
    return base or "file"


def _content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"


def _object_key(project_id: int, unique: str, subdir: str = "", prefix: str = "") -> str:
    parts = []
    p = (prefix or "").strip().strip("/")
    if p:
        parts.append(p)
    parts.append("projects")
    parts.append(str(project_id))
    s = (subdir or "").strip().strip("/\\")
    if s:
        parts.append(s.replace("\\", "/"))
    parts.append(unique)
    return "/".join(parts)


class StorageBackend(Protocol):
    name: str

    def save_bytes(
        self,
        project_id: int,
        filename: str,
        content: bytes,
        *,
        subdir: str = "",
    ) -> Tuple[str, str]:
        ...

    def url_for_relative(self, relative_path: str) -> str:
        ...

    def health_check(self) -> Dict[str, Any]:
        ...


class LocalStorageBackend:
    name = "local"

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
        if rel.startswith("uploads/"):
            return f"{self.base_url}/{rel}"
        return f"{self.base_url}/uploads/{rel}"

    def health_check(self) -> Dict[str, Any]:
        ok = self.upload_root.exists() and self.upload_root.is_dir()
        writable = False
        if ok:
            try:
                writable = self.upload_root.exists() and True
                test = self.upload_root / ".write_test"
                test.write_text("ok", encoding="utf-8")
                test.unlink(missing_ok=True)
                writable = True
            except Exception as e:
                return {"ok": False, "backend": self.name, "error": str(e), "path": str(self.upload_root)}
        return {
            "ok": ok and writable,
            "backend": self.name,
            "path": str(self.upload_root),
            "public_base": self.base_url,
        }


class S3StorageBackend:
    name = "s3"

    def __init__(self, public_base_url_override: Optional[str] = None):
        if not settings.S3_BUCKET:
            raise ValueError("S3_BUCKET 未配置")
        if not settings.S3_ACCESS_KEY_ID or not settings.S3_SECRET_ACCESS_KEY:
            raise ValueError("S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY 未配置")

        try:
            import boto3
            from botocore.client import Config as BotoConfig
        except ImportError as e:
            raise RuntimeError("未安装 boto3，请执行: pip install boto3") from e

        addressing = (settings.S3_ADDRESSING_STYLE or "path").lower()
        if settings.S3_FORCE_PATH_STYLE:
            addressing = "path"

        self.bucket = settings.S3_BUCKET
        self.prefix = (settings.S3_PREFIX or "").strip().strip("/")
        self.endpoint = (settings.S3_ENDPOINT_URL or "").rstrip("/") or None
        override = (public_base_url_override or "").strip().rstrip("/")
        self.public_base = override or (settings.S3_PUBLIC_BASE_URL or "").rstrip("/") or None

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION or "us-east-1",
            verify=settings.S3_VERIFY_SSL,
            config=BotoConfig(
                s3={"addressing_style": addressing},
                signature_version="s3v4",
            ),
        )

    def _public_url(self, key: str) -> str:
        if self.public_base:
            return f"{self.public_base}/{key}"
        if self.endpoint:
            # path-style：http://minio:9000/bucket/key
            return f"{self.endpoint}/{self.bucket}/{key}"
        region = settings.S3_REGION or "us-east-1"
        return f"https://{self.bucket}.s3.{region}.amazonaws.com/{key}"

    def save_bytes(
        self,
        project_id: int,
        filename: str,
        content: bytes,
        *,
        subdir: str = "",
    ) -> Tuple[str, str]:
        safe = _safe_filename(filename)
        ext = Path(safe).suffix.lower()
        unique = f"{uuid.uuid4().hex[:12]}{ext}" if ext else uuid.uuid4().hex[:12]
        key = _object_key(project_id, unique, subdir=subdir, prefix=self.prefix)

        extra: Dict[str, Any] = {"ContentType": _content_type(safe)}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, **extra)
        logger.info("s3_put bucket=%s key=%s bytes=%s", self.bucket, key, len(content))
        return key, self._public_url(key)

    def url_for_relative(self, relative_path: str) -> str:
        key = relative_path.lstrip("/")
        return self._public_url(key)

    def health_check(self) -> Dict[str, Any]:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return {
                "ok": True,
                "backend": self.name,
                "bucket": self.bucket,
                "endpoint": self.endpoint,
                "prefix": self.prefix or None,
                "public_base": self.public_base or self._public_url(self.prefix or "").rstrip("/"),
            }
        except Exception as e:
            logger.warning("s3 health failed: %s", e)
            return {
                "ok": False,
                "backend": self.name,
                "bucket": self.bucket,
                "endpoint": self.endpoint,
                "error": str(e),
            }


def create_storage_backend(file_server_base_url: Optional[str] = None) -> StorageBackend:
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend in ("s3", "minio", "oss"):
        return S3StorageBackend(public_base_url_override=file_server_base_url)
    return LocalStorageBackend(file_server_base_url=file_server_base_url)


class FileStorageService:
    """统一入口：按 STORAGE_BACKEND 选择 local / s3。"""

    def __init__(self, file_server_base_url: Optional[str] = None):
        self.backend = create_storage_backend(file_server_base_url)

    @property
    def backend_name(self) -> str:
        return getattr(self.backend, "name", "local")

    def save_bytes(
        self,
        project_id: int,
        filename: str,
        content: bytes,
        *,
        subdir: str = "",
    ) -> Tuple[str, str]:
        """保存文件，返回 (相对路径或对象键, 公网 data_url)"""
        return self.backend.save_bytes(project_id, filename, content, subdir=subdir)

    def url_for_relative(self, relative_path: str) -> str:
        return self.backend.url_for_relative(relative_path)

    def health_check(self) -> Dict[str, Any]:
        return self.backend.health_check()


def storage_public_info() -> Dict[str, Any]:
    """供前端展示的非敏感存储配置。"""
    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    info: Dict[str, Any] = {
        "backend": backend if backend in ("s3", "minio", "oss") else "local",
        "configured": True,
    }
    if info["backend"] == "local":
        info["upload_dir"] = settings.UPLOAD_DIR
        info["public_base_url"] = settings.FILE_SERVER_BASE_URL
        info["hint"] = "本地落盘；FILE_SERVER_BASE_URL 为浏览器访问前缀"
    else:
        info["bucket"] = settings.S3_BUCKET
        info["endpoint"] = settings.S3_ENDPOINT_URL
        info["region"] = settings.S3_REGION
        info["prefix"] = settings.S3_PREFIX
        info["public_base_url"] = settings.S3_PUBLIC_BASE_URL or settings.FILE_SERVER_BASE_URL
        info["force_path_style"] = settings.S3_FORCE_PATH_STYLE
        info["hint"] = "S3 兼容存储；导入写入对象桶，data_url 使用公开前缀"
        info["configured"] = bool(
            settings.S3_BUCKET and settings.S3_ACCESS_KEY_ID and settings.S3_SECRET_ACCESS_KEY
        )
    return info
