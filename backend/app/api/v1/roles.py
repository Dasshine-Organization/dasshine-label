"""角色与权限元数据 API"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.permissions import PLATFORM_PERMISSIONS, ROLE_LABELS
from app.models.user import User, UserRole

router = APIRouter()


@router.get("/roles")
def list_roles(current_user: User = Depends(get_current_user)):
    """返回平台角色列表及当前用户拥有的权限"""
    role_key = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    my_permissions = sorted(PLATFORM_PERMISSIONS.get(role_key, set()))

    roles = [
        {
            "value": r.value,
            "label": ROLE_LABELS[r],
            "permissions": sorted(PLATFORM_PERMISSIONS.get(r.value, set())),
        }
        for r in UserRole
    ]

    return {
        "roles": roles,
        "current_role": role_key,
        "current_permissions": my_permissions,
        "is_admin": current_user.is_admin,
    }
