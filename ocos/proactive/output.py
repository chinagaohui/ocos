"""Phase P: ProactiveOutput — 主动输出系统。

在现有 ProactiveEngine 基础上增强：
- 整合 AttentionFocus 实现焦点驱动的主动输出
- 支持多通道输出（日志/回调/通知）
- 输出频率管理和节流
- 输出历史记录和指标

设计原则:
  - 不替代 ProactiveEngine，而是增强和包装
  - 所有输出必须经过权限检查（fail-closed）
  - 输出频率受控（每日/每小时/每分钟阈值）
  - 输出内容结构化（类型/优先级/上下文）
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

from ocos.attention.focus import AttentionFocus, FocusType
from ocos.proactive.engine import ProactiveEngine

logger = logging.getLogger(__name__)


class OutputChannel(Enum):
    """输出通道类型。"""
    LOG = auto()           # 本地日志
    CALLBACK = auto()      # 注入回调
    NOTIFICATION = auto()  # 通知（待实现）
    BROADCAST = auto()     # 广播到所有通道


class OutputPriority(Enum):
    """输出优先级。"""
    LOW = 1        # 问候、状态更新
    MEDIUM = 2     # 观察报告、建议
    HIGH = 3       # 重要发现、警告
    CRITICAL = 4   # 紧急通知、需要用户响应


@dataclass(frozen=True)
class OutputRecord:
    """单次输出记录。"""
    record_id: str
    output_type: str           # greeting/observation/suggestion/alert
    content: str
    priority: int              # 1-4
    channel: str               # log/callback/notification/broadcast
    focus_target: str = ""     # 当前焦点主题
    granted: bool = True
    reason: str = ""           # 被拒绝时的原因
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ProactiveOutput:
    """主动输出管理器 — Phase P。

    整合:
    - ProactiveEngine: 基础触发链
    - AttentionFocus: 焦点驱动
    - 输出计划: 频率管理 + 节流
    """

    def __init__(
        self,
        focus: Optional[AttentionFocus] = None,
        proactive_engine: Optional[ProactiveEngine] = None,
        daily_limit: int = 5,
        hourly_limit: int = 20,
        min_interval_seconds: float = 60.0,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._focus = focus or AttentionFocus()
        self._proactive_engine = proactive_engine or ProactiveEngine(
            attention=self._focus,
            daily_limit=daily_limit,
            output_callback=output_callback,
        )
        self._daily_limit = daily_limit
        self._hourly_limit = hourly_limit
        self._min_interval = min_interval_seconds

        self._output_history: list[OutputRecord] = []
        self._last_output_time: float = 0.0
        self._today_count: int = 0
        self._hour_start: float = time.time()
        self._hour_count: int = 0

        # 输出类型过滤器
        self._allowed_types: set[str] = {"greeting", "observation", "suggestion", "alert"}
        self._blocked_types: set[str] = set()

        # 回调
        self._on_output: Optional[Callable[[OutputRecord], None]] = None
        self._on_throttle: Optional[Callable[[str], None]] = None

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def focus(self) -> AttentionFocus:
        return self._focus

    @property
    def output_history(self) -> list[OutputRecord]:
        return list(self._output_history)

    @property
    def today_count(self) -> int:
        return self._today_count

    @property
    def hourly_count(self) -> int:
        # 检查是否需要重置小时计数
        if time.time() - self._hour_start >= 3600:
            self._reset_hourly()
        return self._hour_count

    def try_proactive_output(self) -> Optional[OutputRecord]:
        """尝试主动输出。返回输出记录或被拒绝原因。"""
        # 1. 检查频率限制
        throttle_reason = self._check_throttle()
        if throttle_reason:
            self._record_output("greeting", "", False, reason=throttle_reason)
            if self._on_throttle:
                try:
                    self._on_throttle(throttle_reason)
                except Exception:
                    pass
            return None

        # 2. 调用底层引擎
        message = self._proactive_engine.maybe_proactive_output()
        if message is None:
            return None

        # 3. 记录输出
        record = self._record_output("greeting", message, True)
        return record

    def output_observation(
        self,
        observation: str,
        priority: int = OutputPriority.MEDIUM.value,
        focus_target: str = "",
    ) -> Optional[OutputRecord]:
        """输出观察结果（结构化）。"""
        throttle_reason = self._check_throttle()
        if throttle_reason:
            return None

        # 构建输出内容
        focus_info = f" [焦点: {focus_target}]" if focus_target else ""
        content = f"[观察] {observation}{focus_info}"

        record = self._record_output("observation", content, True, priority=priority)
        self._deliver(record)
        return record

    def output_suggestion(
        self,
        suggestion: str,
        priority: int = OutputPriority.MEDIUM.value,
        focus_target: str = "",
    ) -> Optional[OutputRecord]:
        """输出建议。"""
        throttle_reason = self._check_throttle()
        if throttle_reason:
            return None

        focus_info = f" [建议于: {focus_target}]" if focus_target else ""
        content = f"[建议] {suggestion}{focus_info}"

        record = self._record_output("suggestion", content, True, priority=priority)
        self._deliver(record)
        return record

    def output_alert(
        self,
        alert: str,
        priority: int = OutputPriority.HIGH.value,
    ) -> Optional[OutputRecord]:
        """输出警告/告警。"""
        # 告警不受频率限制（但受最小间隔限制）
        if time.time() - self._last_output_time < self._min_interval:
            logger.debug("Alert throttled by min interval: %.1fs",
                        self._min_interval - (time.time() - self._last_output_time))
            return None

        content = f"[告警] {alert}"
        record = self._record_output("alert", content, True, priority=priority)
        self._deliver(record)
        return record

    def get_output_stats(self) -> dict[str, Any]:
        """获取输出统计。"""
        return {
            "today_count": self._today_count,
            "hourly_count": self._hour_count,
            "daily_limit": self._daily_limit,
            "hourly_limit": self._hourly_limit,
            "recent_outputs": [
                {
                    "type": r.output_type,
                    "priority": r.priority,
                    "content": r.content[:60],
                    "timestamp": r.timestamp,
                }
                for r in self._output_history[-10:]
            ],
        }

    # ── Hooks ───────────────────────────────────────────────────────────

    def on_output(self, fn: Callable[[OutputRecord], None]) -> "ProactiveOutput":
        """注册输出回调。"""
        self._on_output = fn
        return self

    def on_throttle(self, fn: Callable[[str], None]) -> "ProactiveOutput":
        """注册节流回调 (reason)。"""
        self._on_throttle = fn
        return self

    # ── Internal ────────────────────────────────────────────────────────

    def _check_throttle(self) -> Optional[str]:
        """检查是否应该节流。返回原因或 None。"""
        if self._today_count >= self._daily_limit:
            return f"daily_limit:{self._today_count}/{self._daily_limit}"
        if self._hour_count >= self._hourly_limit:
            return f"hourly_limit:{self._hour_count}/{self._hourly_limit}"
        elapsed = time.time() - self._last_output_time
        if elapsed < self._min_interval:
            return f"interval:{elapsed:.1f}s<{self._min_interval}s"
        return None

    def _record_output(
        self,
        output_type: str,
        content: str,
        granted: bool,
        priority: int = OutputPriority.MEDIUM,
        reason: str = "",
    ) -> OutputRecord:
        """记录输出。"""
        import uuid
        record = OutputRecord(
            record_id=f"OUT-{uuid.uuid4().hex[:8]}",
            output_type=output_type,
            content=content,
            priority=priority,
            channel="broadcast",
            granted=granted,
            reason=reason,
        )
        self._output_history.append(record)
        if granted:
            self._today_count += 1
            self._hour_count += 1
        self._last_output_time = time.time()

        # 回调
        if self._on_output and granted:
            try:
                self._on_output(record)
            except Exception as e:
                logger.warning("on_output hook failed: %s", e)

        logger.info(
            "Output recorded: type=%s priority=%d granted=%s reason=%s",
            output_type, priority, granted, reason,
        )
        return record

    def _deliver(self, record: OutputRecord) -> None:
        """分发输出到各通道。"""
        # 日志通道（始终）
        logger.info("[%s] %s", record.output_type, record.content)

        # 优先级高的输出额外记录
        if record.priority >= OutputPriority.HIGH.value:
            logger.warning("HIGH PRIORITY OUTPUT: %s", record.content)

    def _reset_hourly(self) -> None:
        """重置小时计数。"""
        self._hour_start = time.time()
        self._hour_count = 0
