"""Tests for ocos.agent.memory_consolidator."""

import pytest


class TestMemoryConsolidator:

    def test_import_memoryconsolidator(self):
        from ocos.agent.memory_consolidator import MemoryConsolidator
        assert MemoryConsolidator is not None

