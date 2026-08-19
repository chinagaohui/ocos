"""User 模型与 UserStore 测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocos.auth.user import User, UserStore
from ocos.auth.role import Role


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def store(db_path):
    return UserStore(db_path)


class TestUserModel:
    def test_user_creation(self):
        """创建 User 实例。"""
        user = User(user_id="u-001", name="laogao", role=Role.OWNER)
        assert user.user_id == "u-001"
        assert user.name == "laogao"
        assert user.role == Role.OWNER

    def test_user_with_preferences(self):
        """User 包含偏好设置。"""
        user = User(
            user_id="u-002",
            name="admin",
            role=Role.ADMIN,
            preferences={"theme": "dark", "lang": "zh"},
        )
        assert user.preferences["theme"] == "dark"

    def test_user_frozen(self):
        """User 是不可变的。"""
        user = User(user_id="u-004", name="frozen", role=Role.GUEST)
        with pytest.raises(Exception):
            user.name = "changed"  # type: ignore


class TestUserStore:
    def test_save_and_load(self, store):
        """保存后可以加载。"""
        user = User(user_id="u-010", name="alice", role=Role.USER, preferences={"a": 1})
        store.save(user)

        loaded = store.load("u-010")
        assert loaded is not None
        assert loaded.user_id == "u-010"
        assert loaded.name == "alice"
        assert loaded.role == Role.USER
        assert loaded.preferences["a"] == 1

    def test_load_missing(self, store):
        """加载不存在的 user_id 返回 None。"""
        assert store.load("u-nonexistent") is None

    def test_load_by_name(self, store):
        """按名称加载用户。"""
        store.save(User(user_id="u-020", name="bob", role=Role.ADMIN))
        loaded = store.load_by_name("bob")
        assert loaded is not None
        assert loaded.user_id == "u-020"

    def test_list(self, store):
        """list 返回所有用户。"""
        store.save(User(user_id="u-031", name="user1", role=Role.USER))
        store.save(User(user_id="u-032", name="user2", role=Role.USER))
        users = store.list()
        assert len(users) == 2

    def test_update_last_active(self, store):
        """update_last_active 更新最后活跃时间。"""
        store.save(User(user_id="u-040", name="active_user", role=Role.USER))
        store.update_last_active("u-040")

        loaded = store.load("u-040")
        assert loaded is not None
        assert loaded.last_active is not None

    def test_count(self, store):
        """count 返回用户数量。"""
        assert store.count() == 0
        store.save(User(user_id="u-050", name="count_test", role=Role.USER))
        assert store.count() == 1

    def test_update_existing(self, store):
        """保存相同 user_id 覆盖已有记录。"""
        store.save(User(user_id="u-060", name="original", role=Role.USER))
        store.save(User(user_id="u-060", name="updated", role=Role.ADMIN))

        loaded = store.load("u-060")
        assert loaded is not None
        assert loaded.name == "updated"
        assert loaded.role == Role.ADMIN
