"""Role、Permission 与 PermissionChecker 测试。"""
from __future__ import annotations

import pytest

from ocos.auth.user import User
from ocos.auth.role import (
    Role,
    Permission,
    PermissionChecker,
    PermissionDeniedError,
    ROLE_PERMISSIONS,
)


class TestRole:
    def test_role_values(self):
        """Role 枚举值正确。"""
        assert Role.OWNER.value == "owner"
        assert Role.ADMIN.value == "admin"
        assert Role.USER.value == "user"
        assert Role.GUEST.value == "guest"


class TestPermission:
    def test_permission_values(self):
        """Permission 枚举值正确。"""
        assert Permission.SYSTEM_READ.value == "system:read"
        assert Permission.DATA_WRITE.value == "data:write"
        assert Permission.USER_MANAGE.value == "user:manage"


class TestROLE_PERMISSIONS:
    def test_owner_has_all(self):
        """OWNER 拥有所有权限。"""
        owner_perms = ROLE_PERMISSIONS[Role.OWNER]
        assert len(owner_perms) == len(list(Permission))

    def test_guest_has_limited(self):
        """GUEST 只有读权限。"""
        guest_perms = ROLE_PERMISSIONS[Role.GUEST]
        assert Permission.SYSTEM_READ in guest_perms
        assert Permission.SYSTEM_WRITE not in guest_perms
        assert Permission.DATA_DELETE not in guest_perms


class TestPermissionChecker:
    def test_check_valid(self):
        """check 返回 True 当用户有权限。"""
        user = User(user_id="u-001", name="admin", role=Role.ADMIN)
        assert PermissionChecker.check(user, Permission.SYSTEM_READ) is True

    def test_check_invalid(self):
        """check 返回 False 当用户无权限。"""
        user = User(user_id="u-002", name="guest", role=Role.GUEST)
        assert PermissionChecker.check(user, Permission.SYSTEM_WRITE) is False

    def test_check_any(self):
        """check_any 任一权限满足即返回 True。"""
        user = User(user_id="u-003", name="user", role=Role.USER)
        assert PermissionChecker.check_any(user, [
            Permission.SYSTEM_READ,
            Permission.SYSTEM_UPGRADE,
        ]) is True
        assert PermissionChecker.check_any(user, [
            Permission.SYSTEM_UPGRADE,
            Permission.USER_ROLE,
        ]) is False

    def test_check_all(self):
        """check_all 全部满足才返回 True。"""
        user = User(user_id="u-004", name="admin", role=Role.ADMIN)
        assert PermissionChecker.check_all(user, [
            Permission.SYSTEM_READ,
            Permission.SYSTEM_AUDIT,
        ]) is True
        assert PermissionChecker.check_all(user, [
            Permission.SYSTEM_READ,
            Permission.SYSTEM_UPGRADE,
        ]) is False

    def test_require_valid(self):
        """require 不抛异常。"""
        user = User(user_id="u-005", name="owner", role=Role.OWNER)
        PermissionChecker.require(user, Permission.DATA_DELETE)  # no exception

    def test_require_invalid_raises(self):
        """require 失败抛 PermissionDeniedError。"""
        user = User(user_id="u-006", name="guest", role=Role.GUEST)
        with pytest.raises(PermissionDeniedError) as exc:
            PermissionChecker.require(user, Permission.DATA_DELETE)
        assert exc.value.user_id == "u-006"
        assert exc.value.permission == Permission.DATA_DELETE
