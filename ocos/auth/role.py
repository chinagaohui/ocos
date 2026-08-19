"""Role 枚举、Permission 枚举与 PermissionChecker。

权限模型：
- Role：OWNER / ADMIN / USER / GUEST
- Permission：细粒度操作权限
- ROLE_PERMISSIONS：Role → [Permission] 映射表
- PermissionChecker：运行时检查
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ocos.auth.user import User


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class Permission(str, Enum):
    # 系统级
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    SYSTEM_CONFIGURE = "system:configure"
    SYSTEM_UPGRADE = "system:upgrade"
    SYSTEM_AUDIT = "system:audit"
    # 能力级
    CAPABILITY_USE = "capability:use"
    CAPABILITY_CONFIGURE = "capability:configure"
    CAPABILITY_INSTALL = "capability:install"
    # 工具级
    TOOL_USE = "tool:use"
    TOOL_CONFIG = "tool:configure"
    TOOL_INSTALL = "tool:install"
    # 数据级
    DATA_READ = "data:read"
    DATA_WRITE = "data:write"
    DATA_DELETE = "data:delete"
    # 身份级
    USER_MANAGE = "user:manage"
    USER_ROLE = "user:role"


ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.OWNER: list(Permission),
    Role.ADMIN: [
        Permission.SYSTEM_READ,
        Permission.SYSTEM_WRITE,
        Permission.SYSTEM_CONFIGURE,
        Permission.SYSTEM_AUDIT,
        Permission.CAPABILITY_USE,
        Permission.CAPABILITY_CONFIGURE,
        Permission.TOOL_USE,
        Permission.TOOL_CONFIG,
        Permission.DATA_READ,
        Permission.DATA_WRITE,
        Permission.DATA_DELETE,
        Permission.USER_MANAGE,
    ],
    Role.USER: [
        Permission.SYSTEM_READ,
        Permission.CAPABILITY_USE,
        Permission.TOOL_USE,
        Permission.DATA_READ,
        Permission.DATA_WRITE,
    ],
    Role.GUEST: [
        Permission.SYSTEM_READ,
        Permission.DATA_READ,
        Permission.CAPABILITY_USE,
    ],
}


class PermissionDeniedError(PermissionError):
    """权限不足时抛出的异常。"""
    def __init__(self, user_id: str, permission: Permission):
        self.user_id = user_id
        self.permission = permission
        super().__init__(f"Permission denied: {permission.value} for user {user_id}")


class PermissionChecker:
    """权限检查器。"""

    @staticmethod
    def check(user: User, permission: Permission) -> bool:
        """检查用户是否有指定权限。"""
        perms = ROLE_PERMISSIONS.get(user.role, [])
        return permission in perms

    @staticmethod
    def check_any(user: User, permissions: list[Permission]) -> bool:
        """检查用户是否有任一权限。"""
        return any(PermissionChecker.check(user, p) for p in permissions)

    @staticmethod
    def check_all(user: User, permissions: list[Permission]) -> bool:
        """检查用户是否有所用指定权限。"""
        return all(PermissionChecker.check(user, p) for p in permissions)

    @staticmethod
    def require(user: User, permission: Permission) -> None:
        """检查权限，失败抛 PermissionDeniedError。"""
        if not PermissionChecker.check(user, permission):
            raise PermissionDeniedError(user.user_id, permission)
