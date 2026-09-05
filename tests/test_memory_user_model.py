"""Tests for ocos.memory.user.model - 用户模型。"""
import pytest


class TestUserModel:
    def test_import_user_profile(self):
        from ocos.memory.user.model import UserProfile
        assert UserProfile is not None

    def test_import_user_memory(self):
        from ocos.memory.user.model import UserMemory
        assert UserMemory is not None

    def test_import_user_memory_store(self):
        from ocos.memory.user.model import UserMemoryStore
        assert UserMemoryStore is not None

    def test_create_user_profile(self):
        from ocos.memory.user.model import UserProfile
        profile = UserProfile(user_id="test_user")
        assert profile is not None
        assert profile.user_id == "test_user"

    def test_user_profile_defaults(self):
        from ocos.memory.user.model import UserProfile
        profile = UserProfile(user_id="test", name="Test User")
        assert profile.name == "Test User"
        assert profile.description == ""
        assert isinstance(profile.preferences, dict)
        assert isinstance(profile.interests, list)
