"""Tests for ocos.engines.retrieval_engine - 检索引擎。"""
import pytest
from unittest.mock import MagicMock


class TestRetrievalEngine:
    def test_import(self):
        from ocos.engines.retrieval_engine import RetrievalEngine
        assert RetrievalEngine is not None

    def test_create(self):
        from ocos.engines.retrieval_engine import RetrievalEngine
        resolver = MagicMock()
        engine = RetrievalEngine(resolver)
        assert engine is not None
