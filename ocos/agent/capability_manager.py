"""CapabilityManager — Agent 知道自己的能力。

从 Engine Loader 获取能力列表，供 Agent 决策时使用。
"""

from __future__ import annotations

from typing import Any, Optional


class CapabilityManager:
    """能力管理器。

    Agent 知道自己有哪些能力（从 Engine Loader 获取）。
    """

    def __init__(self, engines: Optional[dict[str, Any]] = None):
        self._engines: dict[str, Any] = engines or {}

    def register_engine(self, engine_id: str, engine: Any) -> None:
        """注册一个引擎。"""
        self._engines[engine_id] = engine

    def unregister_engine(self, engine_id: str) -> None:
        """注销一个引擎。"""
        self._engines.pop(engine_id, None)

    def has_capability(self, capability_id: str) -> bool:
        """检查是否有某个能力。"""
        return capability_id in self._engines

    def list_capabilities(self) -> list[str]:
        """列出所有能力。"""
        return list(self._engines.keys())

    def get_engine(self, engine_id: str) -> Optional[Any]:
        """获取引擎实例。"""
        return self._engines.get(engine_id)

    def count(self) -> int:
        return len(self._engines)
