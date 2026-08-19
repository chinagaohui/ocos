"""OCOSLogger 和 get_logger 测试。"""
from __future__ import annotations

import json
import io
import logging
import re

import pytest

from ocos.logging.logger import OCOSLogger, get_logger


class TestOCOSLogger:
    def test_get_logger_default(self):
        """get_logger 返回 OCOSLogger 实例。"""
        logger = get_logger("test.default")
        assert isinstance(logger, OCOSLogger)

    def test_get_logger_cached(self):
        """同一 name 返回同一个 logger 实例。"""
        a = get_logger("test.cache")
        b = get_logger("test.cache")
        assert a is b

    def test_info_logs_correctly(self):
        """info 日志包含正确字段。"""
        logger = get_logger("test.info")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        logger.info("hello world", component="test", process_id="p-1", custom="val")
        logger.removeHandler(handler)

        output = stream.getvalue()
        assert "hello world" in output

    def test_json_format_includes_fields(self):
        """JSON 格式包含 timestamp/level/message 等字段。"""
        logger = get_logger("test.json")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        logger.info("json test", component="scheduler", process_id="p-42")
        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["level"] == "INFO"
        assert entry["message"] == "json test"
        assert entry["component"] == "scheduler"
        assert entry["process_id"] == "p-42"
        assert "timestamp" in entry

    def test_error_with_exception_includes_traceback(self):
        """error 时传入 exception 生成 exception 字段。"""
        logger = get_logger("test.exc")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        try:
            raise ValueError("boom")
        except ValueError as e:
            logger.error("something failed", exception=e)

        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["level"] == "ERROR"
        assert "exception" in entry
        assert entry["exception"]["type"] == "ValueError"
        assert entry["exception"]["message"] == "boom"
        assert "traceback" in entry["exception"]

    def test_warning_level(self):
        """warning 级别日志有效。"""
        logger = get_logger("test.warn")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        logger.warning("watch out")
        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["level"] == "WARNING"

    def test_critical_level(self):
        """critical 级别日志有效。"""
        logger = get_logger("test.crit")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        logger.critical("fatal error")
        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["level"] == "CRITICAL"

    def test_logger_name_in_entry(self):
        """JSON 记录中包含 logger 名称。"""
        logger = get_logger("test.namecheck")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        logger.info("name test")
        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["logger"] == "test.namecheck"

    def test_extra_fields(self):
        """关键字参数额外字段被包含。"""
        logger = get_logger("test.extra")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        from ocos.logging.formatter import JSONFormatter
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

        logger.info("extra fields", component="test", request_id="req-001", duration_ms=42)
        logger.removeHandler(handler)

        line = stream.getvalue().strip()
        entry = json.loads(line)
        assert entry["component"] == "test"
        assert "request_id" in entry["extra"]
        assert entry["extra"]["request_id"] == "req-001"
        assert entry["extra"]["duration_ms"] == 42
