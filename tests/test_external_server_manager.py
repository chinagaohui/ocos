"""Tests for ocos.external.server_manager."""

import pytest


class TestServerManager:

    def test_import_servermanager(self):
        from ocos.external.server_manager import ServerManager
        assert ServerManager is not None

