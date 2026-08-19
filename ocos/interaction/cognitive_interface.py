"""Phase 22-F — CognitiveInterface: 统一入口 + InputAdapter 基类。

职责:
  - CognitiveInterface: 对外暴露的统一认知入口
  - InputAdapter 基类: 输入适配器，将外部输入转为 Stimulus
  - 提供 stimulate(stimulus) → AgentRuntime 唤起
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.logging import get_logger
from ocos.interaction.stimulus import Stimulus, StimulusType, StimulusResult

logger = get_logger(__name__)


# ── InputAdapter 基类 ────────────────────────────────────────────────────────


class InputAdapter(ABC):
    """输入适配器基类 — 将各平台输入转为 Stimulus。

    子类实现:
      - parse(raw_input) → Stimulus
      - can_handle(source: str) → bool
    """

    @abstractmethod
    def parse(self, raw_input: Any) -> Stimulus:
        """解析原始输入为 Stimulus。"""
        ...

    @abstractmethod
    def can_handle(self, source: str) -> bool:
        """判断是否能处理该来源的输入。"""
        ...

    def validate(self, stimulus: Stimulus) -> bool:
        """验证 Stimulus 合法性（可重写）。"""
        return bool(stimulus.content)


class CLIAdapter(InputAdapter):
    """CLI 输入适配器 — stdin/终端。"""

    def parse(self, raw_input: Any) -> Stimulus:
        if isinstance(raw_input, str):
            return Stimulus(
                source="cli",
                type=StimulusType.TEXT,
                content=raw_input.strip(),
                timestamp=datetime.now(timezone.utc),
            )
        return Stimulus(source="cli", type=StimulusType.UNKNOWN, content=str(raw_input))

    def can_handle(self, source: str) -> bool:
        return source in ("cli", "stdin", "terminal")


class APIAdapter(InputAdapter):
    """API 输入适配器 — HTTP/REST。"""

    def parse(self, raw_input: Any) -> Stimulus:
        if isinstance(raw_input, dict):
            return Stimulus(
                source="api",
                type=StimulusType.from_str(raw_input.get("type", "text")),
                content=raw_input.get("content", raw_input.get("message", "")),
                metadata=raw_input.get("metadata", {}),
                timestamp=datetime.now(timezone.utc),
            )
        return Stimulus(source="api", type=StimulusType.TEXT, content=str(raw_input))

    def can_handle(self, source: str) -> bool:
        return source in ("api", "http", "rest")


# ── CognitiveInterface ───────────────────────────────────────────────────────


@dataclass
class CognitiveInterface:
    """统一认知入口 — 接收外部刺激，路由到 AgentRuntime。

    职责:
      - 管理 InputAdapter 注册表
      - 接收外部输入 → Stimulus → Agent.tick() 唤起
      - 记录交互历史

    用法:
        iface = CognitiveInterface(runtime, adapters=[CLIAdapter(), APIAdapter()])
        result = iface.stimulate("你好")
    """

    runtime: Any  # AgentRuntime
    adapters: list[InputAdapter] = field(default_factory=list)
    history: list[StimulusResult] = field(default_factory=list)
    max_history: int = 1000

    def __post_init__(self):
        if not self.adapters:
            self.adapters = [CLIAdapter(), APIAdapter()]

    def stimulate(self, raw_input: Any, source: str = "cli") -> StimulusResult:
        """接收外部刺激，解析并路由到 Runtime。

        Args:
            raw_input: 原始输入
            source: 输入来源标识

        Returns:
            StimulusResult
        """
        # 1. 选择适配器
        adapter = self._find_adapter(source)
        if adapter is None:
            return StimulusResult(
                stimulus=Stimulus(source=source, type=StimulusType.UNKNOWN, content=str(raw_input)),
                accepted=False,
                error=f"No adapter for source: {source}",
            )

        # 2. 解析 Stimulus
        stimulus = adapter.parse(raw_input)

        # 3. 验证
        if not adapter.validate(stimulus):
            return StimulusResult(stimulus=stimulus, accepted=False, error="Validation failed")

        # 4. 注入到 Runtime（publish event + wake）
        self._inject_to_runtime(stimulus)

        # 5. 唤起 Agent（如果休眠中）
        self._wake_if_needed()

        result = StimulusResult(stimulus=stimulus, accepted=True)
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        return result

    def _find_adapter(self, source: str) -> InputAdapter | None:
        for adapter in self.adapters:
            if adapter.can_handle(source):
                return adapter
        return None

    def _inject_to_runtime(self, stimulus: Stimulus) -> None:
        """将 Stimulus 注入 Runtime 的事件管道。"""
        try:
            if hasattr(self.runtime, "_event_ingestion"):
                if self.runtime._event_ingestion is not None:
                    # 通过 event_bus 发布
                    bus = self.runtime._event_ingestion.event_bus
                    if hasattr(bus, "pending_events"):
                        bus.pending_events.append({
                            "type": "user_input",
                            "event_type": "user_input",
                            "payload": {
                                "content": stimulus.content,
                                "stimulus_type": stimulus.type.value,
                                "source": stimulus.source,
                            },
                            "source": stimulus.source,
                            "timestamp": stimulus.timestamp,
                        })
        except Exception as e:
            logger.debug("CognitiveInterface: inject failed: %s", e)

    def _wake_if_needed(self) -> None:
        """如果 Agent 在休眠中，尝试唤醒。"""
        try:
            if hasattr(self.runtime, "cortex"):
                cortex = self.runtime.cortex
                # 字符串比较避免跨包导入 CortexMode 枚举
                if hasattr(cortex, "mode") and str(cortex.mode) == "SLEEPING":
                    cortex.wake()
                    logger.info("CognitiveInterface: woke AgentRuntime from sleep")
        except Exception:
            pass

    def get_recent_history(self, limit: int = 20) -> list[StimulusResult]:
        return self.history[-limit:]

    def clear_history(self) -> None:
        self.history.clear()
