"""日志 Handler — OCOS 日志轮转处理器。

支持：
- 按文件大小轮转（10MB 默认）
- 按时间轮转（每天）
- 双轮转策略
"""

from __future__ import annotations

import os
import logging
from logging.handlers import RotatingFileHandler as StdRotatingHandler
from logging.handlers import TimedRotatingFileHandler as StdTimedHandler


class RotatingFileHandler(StdRotatingHandler):
    """按大小轮转的日志 Handler。

    默认：maxBytes=10MB, backupCount=5, encoding=utf-8。
    """

    def __init__(
        self,
        filename: str,
        maxBytes: int = 10 * 1024 * 1024,
        backupCount: int = 5,
        encoding: str = "utf-8",
    ):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)


class DailyRotatingHandler(StdTimedHandler):
    """按天轮转的日志 Handler。

    默认：每天凌晨轮转，保留 7 天。
    """

    def __init__(
        self,
        filename: str,
        when: str = "midnight",
        backupCount: int = 7,
        encoding: str = "utf-8",
    ):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        super().__init__(filename, when=when, backupCount=backupCount, encoding=encoding)
