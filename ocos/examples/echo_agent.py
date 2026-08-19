"""echo_agent — Capability ABI v1.0 参考实现。

Phase 27: Architecture Freeze — 最小的 IAgentAdapter 实现，
用于展示 Capability ABI 完整接口契约。

特性:
  - 实现 ICapabilityProvider 协议
  - 实现 IAgentAdapter 协议
  - 支持同步/异步适配器包装
  - 可通过 AgentLifecycleManager 管理生命周期
  - 内置 CapabilityDescriptor 自动声明
  - 零外部依赖

用法:
  from ocos.examples.echo_agent import EchoAgent, echo_agent_descriptor
  EngineBridge.register_engine(EchoAgent())
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ── Capability Descriptor ───────────────────────────────────────────────────


@dataclass(frozen=True)
class _EchoDescriptor:
    """Echo Agent 的能力声明 (ABI v1.0 CapabilityDescriptor)。"""
    capability_id: str = "echo"
    domain: str = "utility"
    actions: tuple[str, ...] = ("echo", "ping", "identity", "reverse")
    input_types: tuple[str, ...] = ("text",)
    output_types: tuple[str, ...] = ("text",)
    params: dict[str, Any] = None  # type: ignore[assignment]
    tags: tuple[str, ...] = ("fast", "reliable")

    def __post_init__(self):
        object.__setattr__(self, "params", {
            "action": {"type": "string", "default": "echo", "description": "操作名称"},
            "input": {"type": "string", "default": "", "description": "输入文本"},
        })


echo_agent_descriptor = _EchoDescriptor()


# ── EchoAgent 主体 ──────────────────────────────────────────────────────────


class EchoAgent:
    """Capability ABI v1.0 参考 Agent。

    实现 ICapabilityProvider 和 IAgentAdapter 协议：
      - provider_id / capabilities / protocol 属性
      - engine_name / engine_type 属性
      - execute(**kwargs) 方法
    """

    # ── ICapabilityProvider 属性 ──
    provider_id: str = "echo_agent"
    capabilities: tuple[str, ...] = ("echo", "ping", "identity", "reverse")
    protocol: str = "inproc"

    # ── IAgentAdapter 属性 ──
    engine_name: str = "echo"
    engine_type: str = "tool"

    # ── 可选属性 ──
    version: str = "1.0.0"

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """执行 echo 操作。

        Args:
            action (str): 操作名 — echo|ping|identity|reverse
            input (str): 输入文本

        Returns:
            dict: {"output": str, "action": str, "quality_score": float, "duration_ms": float}
        """
        import time
        start = time.monotonic()

        action = kwargs.get("action", "echo")
        text = str(kwargs.get("input", kwargs.get("text", "")))

        output = self._dispatch(action, text)
        duration_ms = (time.monotonic() - start) * 1000

        return {
            "output": output,
            "action": action,
            "engine": self.engine_name,
            "provider": self.provider_id,
            "quality_score": 1.0,
            "duration_ms": duration_ms,
        }

    def _dispatch(self, action: str, text: str) -> str:
        """路由到具体操作。"""
        handlers = {
            "echo": self._echo,
            "ping": self._ping,
            "identity": self._identity,
            "reverse": self._reverse,
        }
        handler = handlers.get(action, self._echo)
        return handler(text)

    # ── 操作实现 ───────────────────────────────────────────────────────

    @staticmethod
    def _echo(text: str) -> str:
        """Echo back the input."""
        return text if text else "echo: (empty input)"

    @staticmethod
    def _ping(text: str) -> str:
        """Health check — always returns pong."""
        return "pong"

    @staticmethod
    def _identity(text: str) -> str:
        """Return agent identity info."""
        return (
            f"EchoAgent v{EchoAgent.version} | "
            f"provider={EchoAgent.provider_id} | "
            f"engine={EchoAgent.engine_name} | "
            f"capabilities={list(EchoAgent.capabilities)}"
        )

    @staticmethod
    def _reverse(text: str) -> str:
        """Reverse the input text."""
        return text[::-1] if text else "(empty)"

    def __repr__(self) -> str:
        return f"<EchoAgent v{self.version} caps={list(self.capabilities)}>"


# ── 便捷工厂 ─────────────────────────────────────────────────────────────────


def make_echo_agent() -> EchoAgent:
    """创建 EchoAgent 实例 (工厂函数)。"""
    return EchoAgent()
