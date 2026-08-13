"""存储配置与健康状态 API。"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.services.file_storage import FileStorageService, storage_public_info

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/config")
def get_storage_config(current_user: User = Depends(get_current_user)):
    """返回非敏感存储配置，供导入 UI 展示。"""
    return storage_public_info()


@router.get("/health")
def get_storage_health(current_user: User = Depends(get_current_user)):
    """探测当前存储后端是否可用。"""
    try:
        svc = FileStorageService()
        return svc.health_check()
    except Exception as e:
        return {"ok": False, "backend": storage_public_info().get("backend"), "error": str(e)}
