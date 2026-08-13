"""S3 / local 存储冒烟测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.file_storage import (
    LocalStorageBackend,
    S3StorageBackend,
    _object_key,
    create_storage_backend,
    storage_public_info,
)


def test_object_key_with_prefix():
    assert _object_key(7, "abc.jpg", subdir="raw", prefix="dasshine") == "dasshine/projects/7/raw/abc.jpg"


def test_local_save_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.services.file_storage.settings.FILE_SERVER_BASE_URL",
        "http://files.example",
    )
    backend = LocalStorageBackend()
    rel, url = backend.save_bytes(3, "demo.png", b"\x89PNG", subdir="")
    assert rel.startswith("projects/3/")
    assert url.startswith("http://files.example/uploads/projects/3/")
    assert (tmp_path / rel).is_file()


def test_create_backend_local(monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.STORAGE_BACKEND", "local")
    b = create_storage_backend()
    assert b.name == "local"


def test_s3_save_bytes_mocked(monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("app.services.file_storage.settings.S3_BUCKET", "label-data")
    monkeypatch.setattr("app.services.file_storage.settings.S3_ACCESS_KEY_ID", "ak")
    monkeypatch.setattr("app.services.file_storage.settings.S3_SECRET_ACCESS_KEY", "sk")
    monkeypatch.setattr("app.services.file_storage.settings.S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr("app.services.file_storage.settings.S3_PREFIX", "dasshine")
    monkeypatch.setattr(
        "app.services.file_storage.settings.S3_PUBLIC_BASE_URL",
        "http://cdn.example/label-data",
    )
    monkeypatch.setattr("app.services.file_storage.settings.S3_FORCE_PATH_STYLE", True)
    monkeypatch.setattr("app.services.file_storage.settings.S3_REGION", "us-east-1")
    monkeypatch.setattr("app.services.file_storage.settings.S3_VERIFY_SSL", False)

    fake_client = MagicMock()
    with patch("boto3.client", return_value=fake_client):
        backend = S3StorageBackend()
        key, url = backend.save_bytes(9, "a.jpg", b"jpegdata")

    fake_client.put_object.assert_called_once()
    call_kw = fake_client.put_object.call_args.kwargs
    assert call_kw["Bucket"] == "label-data"
    assert call_kw["Key"].startswith("dasshine/projects/9/")
    assert call_kw["Body"] == b"jpegdata"
    assert key == call_kw["Key"]
    assert url == f"http://cdn.example/label-data/{key}"


def test_storage_public_info_s3(monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.STORAGE_BACKEND", "s3")
    monkeypatch.setattr("app.services.file_storage.settings.S3_BUCKET", "b")
    monkeypatch.setattr("app.services.file_storage.settings.S3_ACCESS_KEY_ID", "ak")
    monkeypatch.setattr("app.services.file_storage.settings.S3_SECRET_ACCESS_KEY", "sk")
    info = storage_public_info()
    assert info["backend"] == "s3"
    assert info["configured"] is True
    assert "ak" not in str(info)
    assert "sk" not in str(info)
