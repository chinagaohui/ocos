"""S2.9: 日志脱敏回归（白皮书 P2 / §6.4）。

- JSONFormatter: message >200 字符截断；extra 中 content/payload 等
  键 >50 字符截断追加 [REDACTED:{len}]
- OCOS_LOG_REDACT=false 关闭
- event.record_trace: 用户消息摘要不再明文进日志
"""

from __future__ import annotations

import logging

import pytest

from ocos.logging.formatter import JSONFormatter, redact_text


def _fmt_record(msg: str, extra: dict | None = None) -> str:
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="t.py", lineno=1,
        msg=msg, args=(), exc_info=None)
    for k, v in (extra or {}).items():
        setattr(record, k, v)
    return JSONFormatter().format(record)


class TestFormatterRedaction:
    def test_long_message_truncated(self):
        secret = "用户的机密内容" * 40  # 280 字符
        out = _fmt_record(f"User says: {secret}")
        assert secret not in out
        assert "REDACTED" in out

    def test_extra_content_field_redacted(self):
        secret = "x" * 120
        out = _fmt_record("ok", extra={"content": secret})
        assert secret not in out
        assert "REDACTED:120" in out

    def test_short_fields_untouched(self):
        out = _fmt_record("hello", extra={"component_note": "正常短文本"})
        assert "正常短文本" in out

    def test_redact_disabled(self, monkeypatch):
        import importlib
        monkeypatch.setenv("OCOS_LOG_REDACT", "false")
        import ocos.logging.formatter as fm
        importlib.reload(fm)
        try:
            secret = "y" * 120
            record = logging.LogRecord(
                name="t", level=logging.INFO, pathname="t.py", lineno=1,
                msg="m", args=(), exc_info=None)
            record.content = secret
            out = fm.JSONFormatter().format(record)
            assert secret in out  # 关闭后原样输出
        finally:
            monkeypatch.delenv("OCOS_LOG_REDACT", raising=False)
            importlib.reload(fm)  # 恢复默认开启（必须先删 env 再 reload）

    def test_redact_text_helper(self):
        assert redact_text("short") == "short"
        long = "z" * 80
        out = redact_text(long)
        assert out.startswith("z" * 50)
        assert out.endswith("[REDACTED:80]")


class TestRecordTraceRedaction:
    def test_push_user_message_trace_not_plaintext(self, caplog):
        """push_user_message + record_trace 后，>50 字符内容不进日志。"""
        from ocos.event import EventBus, EventSource, RawEvent
        long_msg = "这是一段超长的用户隐私内容" * 10
        bus = EventBus()
        ev = bus.push_user_message(long_msg)
        with caplog.at_level(logging.INFO, logger="ocos.event"):
            bus.record_trace(ev, 0.5, __import__(
                "ocos.event", fromlist=["AttentionDecision"]
            ).AttentionDecision.QUEUED, "test")
        assert long_msg not in caplog.text
