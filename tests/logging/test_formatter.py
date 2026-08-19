"""JSONFormatter 独立测试。"""
from __future__ import annotations

import io
import json
import logging

import pytest

from ocos.logging.formatter import JSONFormatter


@pytest.fixture
def formatter():
    return JSONFormatter()


def make_record(
    msg: str,
    level: int = logging.INFO,
    name: str = "test",
    component: str | None = None,
    process_id: str | None = None,
    exception: dict | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    if component:
        record.component = component
    if process_id:
        record.process_id = process_id
    if exception:
        record.exception = exception
    return record


class TestJSONFormatter:
    def test_basic_json_output(self, formatter):
        """基础输出为有效的 JSON 行。"""
        record = make_record("hello")
        output = formatter.format(record)
        entry = json.loads(output)
        assert entry["message"] == "hello"
        assert entry["level"] == "INFO"
        assert "timestamp" in entry

    def test_level_name(self, formatter):
        """级别名称正确。"""
        record = make_record("warn", level=logging.WARNING)
        entry = json.loads(formatter.format(record))
        assert entry["level"] == "WARNING"

    def test_component_field(self, formatter):
        """component 字段被包含。"""
        record = make_record("test", component="my_component")
        entry = json.loads(formatter.format(record))
        assert entry["component"] == "my_component"

    def test_process_id_field(self, formatter):
        """process_id 字段被包含。"""
        record = make_record("test", process_id="p-001")
        entry = json.loads(formatter.format(record))
        assert entry["process_id"] == "p-001"

    def test_exception_field(self, formatter):
        """exception 字段被包含。"""
        record = make_record("error", exception={"type": "ValueError", "message": "bad"})
        entry = json.loads(formatter.format(record))
        assert entry["exception"]["type"] == "ValueError"

    def test_logger_name(self, formatter):
        """logger 名称被包含。"""
        record = make_record("test", name="ocos.scheduler")
        entry = json.loads(formatter.format(record))
        assert entry["logger"] == "ocos.scheduler"

    def test_extra_fields(self, formatter):
        """额外字段被放在 extra 对象中。"""
        record = make_record("test")
        record.request_id = "req-abc"
        record.duration = 123
        entry = json.loads(formatter.format(record))
        assert entry["extra"]["request_id"] == "req-abc"
        assert entry["extra"]["duration"] == 123
