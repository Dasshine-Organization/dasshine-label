"""异步导出经 FileStorageService 落盘（契约）。"""

from unittest.mock import MagicMock, patch


def test_export_task_module_uses_file_storage_api():
    """export_tasks 通过 FileStorageService.save_bytes(..., subdir='exports') 写产物。"""
    import inspect
    from app.tasks import export_tasks

    src = inspect.getsource(export_tasks.export_project_data)
    assert "FileStorageService" in src
    assert 'subdir="exports"' in src or "subdir='exports'" in src
    assert "download_url" in src
    assert "storage_backend" in src


def test_file_storage_save_bytes_contract():
    from app.services.file_storage import FileStorageService

    backend = MagicMock()
    backend.name = "s3"
    backend.save_bytes.return_value = ("key", "https://cdn/x")
    with patch("app.services.file_storage.create_storage_backend", return_value=backend):
        svc = FileStorageService()
        rel, url = svc.save_bytes(1, "a.json", b"{}", subdir="exports")
    assert rel == "key"
    assert url == "https://cdn/x"
    backend.save_bytes.assert_called_once_with(1, "a.json", b"{}", subdir="exports")
