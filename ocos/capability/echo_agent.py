"""echo_agent — 参考实现，展示 Capability ABI 最小接口。

Freeze Phase 27a7: 参考 agent 实现，供 Provider 开发者参考。
实现 `execute(inputs)` 接口，返回 echo 输出。
不 import 任何 OCOS 内部模块（遵守单向依赖原则）。
"""

from __future__ import annotations

from typing import Any


class EchoAgent:
    """最小 Capability ABI 参考实现。

    遵守 ABI 契约：
      - 单方法: execute(inputs) → dict
      - 无状态: 不持有 OCOS 内部引用
      - 无 OCOS import: 单向依赖

    用法：
        agent = EchoAgent()
        result = agent.execute(prompt="hello")
        assert result["output"] == "Echo: hello"
    """

    def __init__(self, prefix: str = "Echo") -> None:
        self._prefix = prefix

    def execute(self, **inputs: Any) -> dict[str, Any]:
        """Echo 回显输入。

        Args:
            inputs: 任意 keyword arguments

        Returns:
            {"output": f"{prefix}: {input_value}"}
        """
        # 找到第一个非空值作为 echo 内容
        content = ""
        for key in ("prompt", "text", "input", "content"):
            if key in inputs and inputs[key]:
                content = str(inputs[key])
                break

        # 如果没匹配到，输出所有 input keys
        if not content:
            content = f"received keys: {', '.join(inputs.keys())}"

        return {
            "output": f"{self._prefix}: {content}",
            "echoed_keys": list(inputs.keys()),
        }
