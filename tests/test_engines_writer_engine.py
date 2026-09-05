"""Tests for ocos.engines.writer_engine - 写作引擎。"""
import pytest
from unittest.mock import MagicMock


class TestWriterEngine:
    def test_import(self):
        from ocos.engines.writer_engine import WriterEngine
        assert WriterEngine is not None

    def test_create(self):
        from ocos.engines.writer_engine import WriterEngine
        event_bus = MagicMock()
        working_memory = MagicMock()
        engine = WriterEngine(event_bus, working_memory)
        assert engine is not None
