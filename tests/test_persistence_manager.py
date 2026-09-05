"""Tests for ocos.persistence.manager - Persistence manager."""
import pytest
from unittest.mock import MagicMock


class TestPersistenceManager:
    def test_import(self):
        from ocos.persistence.manager import PersistenceManager
        assert PersistenceManager is not None

    def test_create(self):
        from ocos.persistence.manager import PersistenceManager
        mgr = PersistenceManager()
        assert mgr is not None

    def test_methods_exist(self):
        from ocos.persistence.manager import PersistenceManager
        mgr = PersistenceManager()
        assert hasattr(mgr, 'save')
        assert hasattr(mgr, 'restore')
        assert hasattr(mgr, 'save_checkpoint')
        assert hasattr(mgr, 'restore_checkpoint')
        assert hasattr(mgr, 'list_snapshots')
        assert hasattr(mgr, 'delete_snapshot')
        assert hasattr(mgr, 'get_stats')
        assert callable(mgr.save)
        assert callable(mgr.restore)
        assert callable(mgr.save_checkpoint)
        assert callable(mgr.restore_checkpoint)
        assert callable(mgr.list_snapshots)
        assert callable(mgr.get_stats)
