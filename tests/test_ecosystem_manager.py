"""Tests for ocos.ecosystem.manager - 生态管理器。"""
import pytest
from unittest.mock import MagicMock


class TestEcosystemManager:
    def test_import(self):
        from ocos.ecosystem.manager import EcosystemManager
        assert EcosystemManager is not None

    def test_create(self):
        from ocos.ecosystem.manager import EcosystemManager
        mgr = EcosystemManager()
        assert mgr is not None

    def test_get_stats(self):
        from ocos.ecosystem.manager import EcosystemManager
        mgr = EcosystemManager()
        stats = mgr.get_stats()
        assert isinstance(stats, dict)
