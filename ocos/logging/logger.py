"""OCOSLogger — OCOS 结构化日志实现。

每个日志条目包含结构化字段：
{
    "timestamp": "ISO-8601",
    "level": "INFO",
    "component": "scheduler",
    "process_id": "p-1234",
    "message": "...",
    "exception": {...},   # 仅 error / critical 级别
    "extra": {...}        # 自定义扩展字段
}
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ocos.logging.formatter import JSONFormatter


_LOGGER_CACHE: dict[str, "OCOSLogger"] = {}
_DEFAULT_CONFIG_APPLIED = False


class OCOSLogger(logging.Logger):
    """OCOS 结构化日志器。

    每个日志方法都接受可选的 component、process_id 和 extra 关键字参数。
    """

    def _fmt(self, msg: str, args: tuple[Any, ...]) -> str:
        return msg % args if args else msg

    def debug(
        self,
        msg: str,
        *args: Any,
        component: Optional[str] = None,
        process_id: Optional[str] = None,
        exc_info: Any = None,
        **extra: Any,
    ) -> None:
        if not self.isEnabledFor(logging.DEBUG):
            return
        self._log(logging.DEBUG, self._fmt(msg, args), (), exc_info=exc_info, extra={
            "component": component,
            "process_id": process_id,
            **extra,
        })

    def info(
        self,
        msg: str,
        *args: Any,
        component: Optional[str] = None,
        process_id: Optional[str] = None,
        exc_info: Any = None,
        **extra: Any,
    ) -> None:
        if not self.isEnabledFor(logging.INFO):
            return
        self._log(logging.INFO, self._fmt(msg, args), (), exc_info=exc_info, extra={
            "component": component,
            "process_id": process_id,
            **extra,
        })

    def warning(
        self,
        msg: str,
        *args: Any,
        component: Optional[str] = None,
        process_id: Optional[str] = None,
        exc_info: Any = None,
        **extra: Any,
    ) -> None:
        if not self.isEnabledFor(logging.WARNING):
            return
        self._log(logging.WARNING, self._fmt(msg, args), (), exc_info=exc_info, extra={
            "component": component,
            "process_id": process_id,
            **extra,
        })

    def error(
        self,
        msg: str,
        *args: Any,
        component: Optional[str] = None,
        process_id: Optional[str] = None,
        exception: Optional[BaseException] = None,
        **extra: Any,
    ) -> None:
        if not self.isEnabledFor(logging.ERROR):
            return
        extra_fields: dict[str, Any] = {
            "component": component,
            "process_id": process_id,
            **extra,
        }
        if exception:
            extra_fields["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": "".join(traceback.format_tb(exception.__traceback__))
                if exception.__traceback__
                else None,
            }
        self._log(logging.ERROR, self._fmt(msg, args), (), extra=extra_fields)

    def critical(
        self,
        msg: str,
        *args: Any,
        component: Optional[str] = None,
        process_id: Optional[str] = None,
        exception: Optional[BaseException] = None,
        **extra: Any,
    ) -> None:
        if not self.isEnabledFor(logging.CRITICAL):
            return
        extra_fields: dict[str, Any] = {
            "component": component,
            "process_id": process_id,
            **extra,
        }
        if exception:
            extra_fields["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": "".join(traceback.format_tb(exception.__traceback__))
                if exception.__traceback__
                else None,
            }
        self._log(logging.CRITICAL, self._fmt(msg, args), (), extra=extra_fields)


def get_logger(name: str) -> OCOSLogger:
    """获取或创建一个 OCOSLogger 实例。

    第一次调用时自动应用默认配置（如果尚未配置）。
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    _apply_default_config()
    logger = logging.getLogger(name)
    if not isinstance(logger, OCOSLogger):
        # 替换为 OCOSLogger 子类
        logger.__class__ = OCOSLogger
    _LOGGER_CACHE[name] = logger
    return logger


def _apply_default_config() -> None:
    """应用日志默认配置（如果尚未配置）。"""
    global _DEFAULT_CONFIG_APPLIED
    if _DEFAULT_CONFIG_APPLIED:
        return
    _DEFAULT_CONFIG_APPLIED = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 控制台 Handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter())
    root.addHandler(console)
