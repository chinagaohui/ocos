"""Phase 46: ContextSynchronizer — 上下文同步器。

将 Self Model + Personal Memory + World Model 的快照聚合为
Decision Intelligence 所需的统一上下文。

同步来源:
    - Phase 40: Self Model → 当前自我状态
    - Phase 41: Personal Memory → 相关智慧提示
    - Phase 42: World Model → 世界当前状态
    - Phase 39: Goal → 活跃目标

不创建新数据，只做聚合快照。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_loop.loop_types import LoopContext


@dataclass
class ContextSynchronizer:
    """上下文同步器——聚合各层快照为统一上下文。"""

    # 外部注入的回调 (可接入 Phase 40/41/42/39 的实际存储)
    _self_snapshot_fn: object = None     # () -> str
    _wisdom_fn: object = None            # () -> list[str]
    _world_state_fn: object = None       # () -> str
    _active_goals_fn: object = None      # () -> list[str]

    def set_self_provider(self, fn: object) -> None:
        """注入 Self Model 快照提供者。"""
        self._self_snapshot_fn = fn

    def set_wisdom_provider(self, fn: object) -> None:
        """注入 Personal Memory 智慧提供者。"""
        self._wisdom_fn = fn

    def set_world_provider(self, fn: object) -> None:
        """注入 World Model 状态提供者。"""
        self._world_state_fn = fn

    def set_goals_provider(self, fn: object) -> None:
        """注入 Goal 提供者。"""
        self._active_goals_fn = fn

    def sync(self, ctx: LoopContext) -> LoopContext:
        """同步所有层的上下文到 LoopContext。"""
        if self._self_snapshot_fn:
            ctx.self_snapshot = self._self_snapshot_fn()  # type: ignore
        if self._wisdom_fn:
            ctx.active_wisdom = self._wisdom_fn()  # type: ignore
        if self._world_state_fn:
            ctx.world_state = self._world_state_fn()  # type: ignore
        if self._active_goals_fn:
            ctx.active_goals = self._active_goals_fn()  # type: ignore
        return ctx

    def build_decision_context(self, ctx: LoopContext) -> str:
        """构建 Decision Intelligence 所需的聚合上下文字符串。"""
        parts = []
        if ctx.perception_input:
            parts.append(f"[Perception] {ctx.perception_input}")
        if ctx.attention_focus:
            parts.append(f"[Attention] {ctx.attention_focus} (weight={ctx.attention_weight})")
        if ctx.self_snapshot:
            parts.append(f"[Self] {ctx.self_snapshot}")
        if ctx.active_wisdom:
            parts.append(f"[Wisdom] {'; '.join(ctx.active_wisdom[:5])}")
        if ctx.world_state:
            parts.append(f"[World] {ctx.world_state}")
        if ctx.active_goals:
            parts.append(f"[Goals] {'; '.join(ctx.active_goals[:3])}")
        return "\n".join(parts)


__all__ = ["ContextSynchronizer"]
