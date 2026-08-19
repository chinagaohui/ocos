"""JSONFormatter — 输出 JSON 行的结构化日志格式化器。

每行一个 JSON 对象，方便 LogSearcher 和外部工具解析。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from collections import OrderedDict


class JSONFormatter(logging.Formatter):
    """将 LogRecord 格式化为单行 JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = OrderedDict()
        log_entry["timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        log_entry["level"] = record.levelname
        log_entry["logger"] = record.name
        log_entry["message"] = record.getMessage()

        # 提取结构化字段（component, process_id）
        component = getattr(record, "component", None)
        if component:
            log_entry["component"] = component

        process_id = getattr(record, "process_id", None)
        if process_id:
            log_entry["process_id"] = process_id

        # exception
        exception = getattr(record, "exception", None)
        if exception:
            log_entry["exception"] = exception

        # 额外字段（extra keys）
        extra = {}
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "levelname", "levelno", "lineno",
                "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
                "component", "process_id", "exception",
            ):
                continue
            extra[key] = value
        if extra:
            log_entry["extra"] = extra

        return json.dumps(log_entry, ensure_ascii=False, default=str)

    def formatMessage(self, record: logging.LogRecord) -> str:
        return self.format(record)
