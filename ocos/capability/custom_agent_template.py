"""custom_agent_template — 用户自定义 Agent 接入规范 (Phase 28a5).

外部 Agent 实现此协议即可接入 OCOS 能力系统。
与 echo_agent 配合构成最小可运行示例。

Freeze §4.4: 所有 Provider 必须遵守此 ABI。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AgentProvider(ABC):
    """外部 Agent 接入 OCOS 的抽象基类。

    实现要求:
      1. 实现 execute() — 同步，返回 dict
      2. 可选实现 manifest() — 返回能力元数据
      3. 不 import OCOS 内部模块（单向依赖）
      4. 无状态 — Provider 不持有 OCOS 内部状态

    注册方式:
      1. 创建 AgentProvider 子类实例
      2. 放入 CapabilityRegistry
      3. 启动 OCOS AgentRuntime
    """

    @abstractmethod
    def execute(self, **inputs: Any) -> dict[str, Any]:
        """执行能力。

        Args:
            inputs: 由 caller 传入的参数，取决于具体能力类型

        Returns:
            {
                "output": ...,
                "status": "success" | "error",
                "metadata": {...},
            }
        """
        ...

    def manifest(self) -> dict[str, Any]:
        """返回 Agent 的元数据声明。

        Returns:
            {
                "name": str,
                "version": str,
                "capabilities": [str, ...],
                "protocol": "subprocess" | "http" | "mcp",
            }
        """
        return {
            "name": self.__class__.__name__,
            "version": "0.1.0",
            "capabilities": [],
            "protocol": "subprocess",
        }

    def health_check(self) -> bool:
        """返回 Provider 是否可用。默认总是 True。"""
        return True

    def shutdown(self) -> None:
        """清理资源。默认空实现。"""
        pass
