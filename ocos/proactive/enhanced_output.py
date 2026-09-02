"""Phase AJ: ProactiveOutputEnhanced — 增强型主动输出管理器。

在 Phase P ProactiveOutput 基础上增强：
- 多通道输出管理（日志/回调/通知/广播）
- 输出频率管理与节流
- 输出历史记录和指标
- 与 ToolIntegration 集成
- 输出质量评估

架构原则:
- AJ-OUT-01: 输出 ≠ 决策 — 主动输出是观察展示，不改变目标
- AJ-OUT-02: 频率受控 — 每日/每小时/每分钟阈值
- AJ-OUT-03: 优先级驱动 — 紧急输出优先
- AJ-OUT-04: 多通道 — 同一内容可发往多个通道
- AJ-OUT-05: 审计记录 — 所有输出尝试均记录
- AJ-OUT-06: 可配置 — 阈值、模板、通道均可配置
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class OutputChannel(str, Enum):
    """输出通道类型。"""
    LOG = "log"
    CALLBACK = "callback"
    NOTIFICATION = "notification"
    BROADCAST = "broadcast"


class OutputPriority(int, Enum):
    """输出优先级。"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class OutputRecord:
    """单次输出记录。"""
    record_id: str
    output_type: str
    content: str
    priority: int
    channel: str
    granted: bool
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "output_type": self.output_type,
            "priority": self.priority,
            "channel": self.channel,
            "granted": self.granted,
            "reason": self.reason[:100],
            "timestamp": self.timestamp,
        }


@dataclass
class OutputStats:
    """输出统计。"""
    total_outputs: int = 0
    granted_outputs: int = 0
    rejected_outputs: int = 0
    total_by_channel: dict[str, int] = field(default_factory=dict)
    total_by_priority: dict[int, int] = field(default_factory=dict)
    avg_daily_outputs: float = 0.0
    last_output_time: float = 0.0

    def record(self, record: OutputRecord) -> None:
        self.total_outputs += 1
        if record.granted:
            self.granted_outputs += 1
        else:
            self.rejected_outputs += 1
        self.total_by_channel[record.channel] = self.total_by_channel.get(record.channel, 0) + 1
        self.total_by_priority[record.priority] = self.total_by_priority.get(record.priority, 0) + 1
        self.last_output_time = record.timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_outputs": self.total_outputs,
            "granted_outputs": self.granted_outputs,
            "rejected_outputs": self.rejected_outputs,
            "rejection_rate": round(self.rejected_outputs / self.total_outputs, 3) if self.total_outputs > 0 else 0.0,
            "by_channel": dict(self.total_by_channel),
            "by_priority": {str(k): v for k, v in self.total_by_priority.items()},
            "last_output_time": self.last_output_time,
        }


class ProactiveOutputEnhanced:
    """增强型主动输出管理器。

    在 Phase P 基础上增加：
    - 多通道输出
    - 频率管理
    - 优先级队列
    - 输出统计
    """

    def __init__(
        self,
        daily_limit: int = 5,
        hourly_limit: int = 20,
        min_interval_seconds: float = 60.0,
        output_callback: Optional[Callable[[str, str], None]] = None,
        notification_callback: Optional[Callable[[str, str, int], None]] = None,
    ):
        self._daily_limit = daily_limit
        self._hourly_limit = hourly_limit
        self._min_interval = min_interval_seconds
        self._output_callback = output_callback
        self._notification_callback = notification_callback

        self._lock = threading.Lock()
        self._history: list[OutputRecord] = []
        self._stats = OutputStats()
        self._daily_count = 0
        self._hourly_count = 0
        self._last_output_time = 0.0
        self._today_start = time.time()
        self._hour_start = time.time()

    # ── 输出入口 ───────────────────────────────────────────────────────

    def emit(
        self,
        output_type: str,
        content: str,
        priority: OutputPriority = OutputPriority.MEDIUM,
        channel: OutputChannel = OutputChannel.BROADCAST,
    ) -> OutputRecord:
        """执行一次主动输出。"""
        with self._lock:
            # 检查频率限制
            if not self._check_rate_limit():
                record = self._create_record(output_type, content, priority, channel, granted=False, reason="rate_limited")
                self._stats.record(record)
                self._history.append(record)
                return record

            # 检查最小间隔
            if time.time() - self._last_output_time < self._min_interval:
                record = self._create_record(output_type, content, priority, channel, granted=False, reason="too_frequent")
                self._stats.record(record)
                self._history.append(record)
                return record

            # 执行输出
            self._execute_output(output_type, content, priority, channel)

            # 更新计数
            self._daily_count += 1
            self._hourly_count += 1
            self._last_output_time = time.time()

            record = self._create_record(output_type, content, priority, channel, granted=True)
            self._stats.record(record)
            self._history.append(record)
            return record

    def _check_rate_limit(self) -> bool:
        """检查频率限制。"""
        now = time.time()
        # 重置日计数
        if now - self._today_start >= 86400:
            self._daily_count = 0
            self._today_start = now
        # 重置小时计数
        if now - self._hour_start >= 3600:
            self._hourly_count = 0
            self._hour_start = now
        # 检查限制
        return self._daily_count < self._daily_limit and self._hourly_count < self._hourly_limit

    def _execute_output(
        self,
        output_type: str,
        content: str,
        priority: OutputPriority,
        channel: OutputChannel,
    ) -> None:
        """执行实际输出。"""
        message = f"[{output_type.upper()}] {content}"
        logger.info("Proactive output: %s", message)

        if channel == OutputChannel.CALLBACK and self._output_callback:
            try:
                self._output_callback(message)
            except Exception as e:
                logger.error("Output callback failed: %s", e)

        if channel == OutputChannel.NOTIFICATION and self._notification_callback:
            try:
                self._notification_callback(output_type, content, priority.value)
            except Exception as e:
                logger.error("Notification callback failed: %s", e)

        # BROADCAST 发送到所有可用通道
        if channel == OutputChannel.BROADCAST:
            if self._output_callback:
                try:
                    self._output_callback(message)
                except Exception:
                    pass

    def _create_record(
        self,
        output_type: str,
        content: str,
        priority: OutputPriority,
        channel: OutputChannel,
        granted: bool,
        reason: str = "",
    ) -> OutputRecord:
        return OutputRecord(
            record_id=f"out-{time.time():.0f}-{threading.current_thread().ident}",
            output_type=output_type,
            content=content[:500],
            priority=priority.value,
            channel=channel.value,
            granted=granted,
            reason=reason,
        )

    # ── 查询接口 ───────────────────────────────────────────────────────

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取输出历史。"""
        with self._lock:
            return [r.to_dict() for r in self._history[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """获取输出统计。"""
        with self._lock:
            return self._stats.to_dict()

    def get_status(self) -> dict[str, Any]:
        """获取管理器状态。"""
        with self._lock:
            return {
                "total_outputs": self._stats.total_outputs,
                "granted_outputs": self._stats.granted_outputs,
                "rejected_outputs": self._stats.rejected_outputs,
                "daily_count": self._daily_count,
                "hourly_count": self._hourly_count,
                "daily_limit": self._daily_limit,
                "hourly_limit": self._hourly_limit,
                "min_interval_seconds": self._min_interval,
            }

    # ── 配置接口 ───────────────────────────────────────────────────────

    def set_limits(
        self,
        daily_limit: int | None = None,
        hourly_limit: int | None = None,
        min_interval: float | None = None,
    ) -> None:
        """设置输出限制。"""
        with self._lock:
            if daily_limit is not None:
                self._daily_limit = max(1, daily_limit)
            if hourly_limit is not None:
                self._hourly_limit = max(1, hourly_limit)
            if min_interval is not None:
                self._min_interval = max(0.0, min_interval)

    def clear_history(self) -> None:
        """清空输出历史。"""
        with self._lock:
            self._history.clear()
            self._stats = OutputStats()
            self._daily_count = 0
            self._hourly_count = 0

    # ── 类型安全比较 ────────────────────────────────────────────────────

    def _priority_ge(self, a: OutputPriority, b: int) -> bool:
        """优先级比较（使用 .value）。"""
        return a.value >= b
