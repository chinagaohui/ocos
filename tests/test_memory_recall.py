"""Tests for ocos.memory.recall."""

import pytest


class TestMemoryRecall:

    def test_import_memoryrecall(self):
        from ocos.memory.recall import MemoryRecall
        assert MemoryRecall is not None

