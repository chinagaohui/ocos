"""Phase 42: StateTracker — 实体状态版本追踪。

每个实体的状态随时间变化，StateTracker 记录:
    - 每个版本的状态快照 (EntityState)
    - 版本的变更链 (StateChange)
    - 回访历史状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

from ocos.world_model.world_types import EntityState, StateChange


@dataclass
class StateTracker:
    """实体状态版本追踪器。

    每个 entity 维护一个状态历史链。
    """

    _states: dict[str, list[EntityState]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _changes: list[StateChange] = field(default_factory=list)

    # ── 写入 ──

    def record_state(self, state: EntityState) -> None:
        """记录新状态，自动建立与上一个状态的变更链。"""
        entity_states = self._states[state.entity_id]

        if entity_states:
            prev = entity_states[-1]
            changed = state.attributes != prev.attributes
            if changed:
                changed_keys = frozenset(
                    {k for k in state.keys | prev.keys
                     if state.get(k) != prev.get(k)}
                )
                self._changes.append(StateChange(
                    from_state_id=prev.state_id,
                    to_state_id=state.state_id,
                    entity_id=state.entity_id,
                    changed_keys=changed_keys,
                    tick_id=state.tick_id,
                ))

        self._states[state.entity_id].append(state)

    # ── 查询 ──

    def current(self, entity_id: str) -> Optional[EntityState]:
        """获取实体当前（最新）状态。"""
        states = self._states.get(entity_id, [])
        return states[-1] if states else None

    def history(self, entity_id: str) -> list[EntityState]:
        """获取实体完整状态历史。"""
        return list(self._states.get(entity_id, []))

    def at_tick(self, entity_id: str, tick_id: int) -> Optional[EntityState]:
        """获取实体在特定 tick 时的状态（最近的 <= tick_id 的版本）。"""
        states = self._states.get(entity_id, [])
        best = None
        for s in states:
            if s.tick_id <= tick_id:
                best = s
            else:
                break
        return best

    def changes_since(
        self, entity_id: str, since_tick: int
    ) -> list[StateChange]:
        """获取自某 tick 以来的所有变更。"""
        return [
            c for c in self._changes
            if c.entity_id == entity_id and c.tick_id >= since_tick
        ]

    def changed_keys(self, entity_id: str) -> set[str]:
        """获取该实体历史上所有变更过的属性键。"""
        keys: set[str] = set()
        for c in self._changes:
            if c.entity_id == entity_id:
                keys |= c.changed_keys
        return keys

    @property
    def tracked_entities(self) -> list[str]:
        return list(self._states.keys())

    @property
    def change_count(self) -> int:
        return len(self._changes)


__all__ = ["StateTracker"]
