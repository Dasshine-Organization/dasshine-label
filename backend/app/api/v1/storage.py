"""存储配置、健康与目录浏览 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get("/browse")
def browse_storage(
    prefix: str = Query("", max_length=512),
    limit: int = Query(200, ge=1, le=1000),
    delimiter: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    """列出存储前缀下对象（白名单 + 可选单层目录）。"""
    try:
        items = FileStorageService().list_prefix(
            prefix, max_keys=limit, delimiter=delimiter
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"浏览失败: {e}") from e
    info = storage_public_info()
    return {
        "backend": info.get("backend"),
        "prefix": prefix,
        "delimiter": delimiter,
        "count": len(items),
        "items": items,
    }
