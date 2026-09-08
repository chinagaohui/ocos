# ARCHIVED（收敛裁决 P1，2026-09-08）— 本模块已冻结归档，非生产代码。
# 依据: docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md（FROZEN DECISION）
# 禁止从生产路径 import 本模块（违冻条款见来源文档第七节）。

"""AgentWorkingMemory — Agent 的工作记忆。

与 WorkingMemory（系统持久化工作区）不同——这是"我在想什么"而非"系统上下文"。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class WorkItem:
    """工作记忆项。"""
    item_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    content: Any = None
    item_type: str = "observation"
    priority: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AgentWorkingMemory:
    """Agent 的工作记忆——意识的"当前内容"。

    与持久化 WorkingMemory 不同，这是 Agent 当前正在思考的内容。
    SLEEP 时清空。
    """

    def __init__(self, max_capacity: int = 7):
        self._items: dict[str, WorkItem] = {}
        self._max_capacity = max_capacity

    def add(self, item: WorkItem | Any) -> str:
        """添加工作记忆项。"""
        if not isinstance(item, WorkItem):
            item = WorkItem(content=item)
        if len(self._items) >= self._max_capacity:
            # 移除最低优先级项
            lowest = min(self._items.values(), key=lambda x: x.priority)
            del self._items[lowest.item_id]
        self._items[item.item_id] = item
        return item.item_id

    def remove(self, item_id: str) -> None:
        """移除工作记忆项。"""
        self._items.pop(item_id, None)

    def clear(self) -> None:
        """清空所有。"""
        self._items.clear()

    def list_items(self) -> list[WorkItem]:
        """列出所有项（按优先级降序）。"""
        return sorted(self._items.values(), key=lambda x: x.priority, reverse=True)

    def current_focus(self) -> Optional[WorkItem]:
        """获取当前最高优先级项。"""
        if not self._items:
            return None
        return max(self._items.values(), key=lambda x: x.priority)

    def capacity(self) -> tuple[int, int]:
        """返回 (used, max)。"""
        return (len(self._items), self._max_capacity)

    def __len__(self) -> int:
        return len(self._items)
