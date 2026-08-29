"""Stage ③: Memory Sync — 工作记忆同步。

39.2: 从 MemoryHub 恢复/刷新工作记忆。
不执行 Experience→Pattern→Knowledge 固化。

GAP-P2-2 决策（记录于 docs/OCOS_AUDIT_KERNEL.md）:
MemoryHub 是各 store 的聚合门面（episode/belief/semantic/pattern），
无"差异同步"API 可接。stage 收敛为转发语义：注入 hub 后取 get_stats()
快照作为 memory_changes 注入 context——只反映记忆状态，不写入长期记忆，
符合阶段约束。无 hub 注入 → 空快照（降级）。
"""

from __future__ import annotations

from typing import Any, Optional

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class MemorySyncStage:
    """记忆同步阶段。

    39.2: 刷新短期工作记忆。不写入长期记忆。
    """

    name = "MEMORY_SYNC"

    def __init__(self, memory_hub: Any = None) -> None:
        """注入 MemoryHub（ocos/memory/hub.MemoryHub）。"""
        self._memory_hub = memory_hub

    def execute(self, context: TickContext) -> TickContext:
        """取 MemoryHub 状态快照注入 context（GAP-P2-2 转发语义）。"""
        if self._memory_hub is not None and self._memory_hub.is_initialized():
            changes = (self._memory_hub.get_stats(),)
        else:
            changes = ()
        return context.with_updates(
            memory_changes=changes
        ).with_stage_trace(self.name)
