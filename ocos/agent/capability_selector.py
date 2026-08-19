"""CapabilitySelector — 意图→能力编排映射。

从 Intent 提取的意图类型映射到 Engine 编排序列。
Phase 22 已建立 Intent + CapabilityManager，Phase 23 将它们连接起来。
"""

from __future__ import annotations

from typing import Any, Optional


class CapabilitySelector:
    """能力选择器。

    将意图（intent type）映射到引擎编排序列（ordered list of engine_ids）。
    """

    # 默认意图→引擎映射表
    DEFAULT_MAP: dict[str, list[str]] = {
        "create": ["planner", "writer", "validator"],
        "analyze": ["reader", "analyzer", "reporter"],
        "search": ["searcher", "reader"],
        "modify": ["reader", "editor", "validator"],
        "delete": ["searcher", "remover"],
        "learn": ["reader", "analyzer", "memorizer"],
        "plan": ["planner"],
        "reflect": ["reader", "analyzer"],
    }

    def __init__(self, engine_list: Optional[list[str]] = None):
        self._engine_list = engine_list or []
        self._custom_map: dict[str, list[str]] = {}

    def map(self, intent_type: str) -> list[str]:
        """将意图类型映射到引擎编排序列。

        Args:
            intent_type: 来自 Intent.extract() 的 type

        Returns:
            引擎 ID 的有序列表
        """
        if intent_type in self._custom_map:
            return list(self._custom_map[intent_type])
        if intent_type in self.DEFAULT_MAP:
            # 只返回 Engine List 中存在的引擎
            return [e for e in self.DEFAULT_MAP[intent_type] if e in self._engine_list]
        return []

    def register_mapping(self, intent_type: str, engine_sequence: list[str]) -> None:
        """注册自定义意图→引擎映射。"""
        self._custom_map[intent_type] = list(engine_sequence)

    def unregister_mapping(self, intent_type: str) -> None:
        """注销自定义映射（恢复默认）。"""
        self._custom_map.pop(intent_type, None)

    def get_available_intents(self) -> list[str]:
        """获取当前引擎可支持的所有意图类型。"""
        available = []
        for intent_type, engines in self.DEFAULT_MAP.items():
            if any(e in self._engine_list for e in engines):
                available.append(intent_type)
        for intent_type in self._custom_map:
            if intent_type not in available:
                available.append(intent_type)
        return available

    def get_required_engines(self, intent_type: str) -> list[str]:
        """获取某个意图所需的所有引擎。"""
        if intent_type in self._custom_map:
            return list(self._custom_map[intent_type])
        return list(self.DEFAULT_MAP.get(intent_type, []))
