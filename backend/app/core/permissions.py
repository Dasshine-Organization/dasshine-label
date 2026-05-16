"""平台角色与权限定义"""

from app.models.user import User, UserRole

# 角色显示名（API / 文档参考）
ROLE_LABELS: dict[UserRole, str] = {
    UserRole.SUPER_ADMIN: "超级管理员",
    UserRole.ADMIN: "管理员",
    UserRole.MANAGER: "项目经理",
    UserRole.ANNOTATOR: "标注员",
    UserRole.REVIEWER: "审核员",
}

# 各角色可访问的平台能力
PLATFORM_PERMISSIONS: dict[str, set[str]] = {
    UserRole.SUPER_ADMIN.value: {
        "users.manage",
        "users.assign_role",
        "users.reset_password",
        "projects.manage",
        "tasks.manage",
        "export.run",
        "quality.run",
    },
    UserRole.ADMIN.value: {
        "users.manage",
        "users.assign_role",
        "users.reset_password",
        "projects.manage",
        "tasks.manage",
        "export.run",
        "quality.run",
    },
    UserRole.MANAGER.value: {
        "projects.manage",
        "tasks.manage",
        "export.run",
    },
    UserRole.REVIEWER.value: {
        "tasks.review",
    },
    UserRole.ANNOTATOR.value: set(),
}

# 管理员可分配的角色（不含 super_admin）
ADMIN_ASSIGNABLE_ROLES = {
    UserRole.MANAGER,
    UserRole.ANNOTATOR,
    UserRole.REVIEWER,
    UserRole.ADMIN,
}

SUPER_ADMIN_ONLY_ROLES = {UserRole.SUPER_ADMIN}


def role_value(role: UserRole | str) -> str:
    return role.value if isinstance(role, UserRole) else role


def has_platform_permission(user: User, permission: str) -> bool:
    perms = PLATFORM_PERMISSIONS.get(role_value(user.role), set())
    return permission in perms


def can_assign_role(actor: User, target_role: UserRole) -> bool:
    """判断操作者是否可将用户设为 target_role。"""
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    if actor.role == UserRole.ADMIN:
        return target_role in ADMIN_ASSIGNABLE_ROLES
    return False
