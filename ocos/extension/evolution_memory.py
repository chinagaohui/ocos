"""Phase 44: EvolutionMemory — 扩展演化记忆。

记录每个扩展的完整生命周期:
    - 状态变迁 (DISCOVERED → ... → FROZEN)
    - 集成记录
    - 健康历史
    - 修复事件
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import (
    EvolutionEntry, ExtensionState, ExtensionCandidate,
    IntegrationRecord, HealthReport,
)


@dataclass
class EvolutionMemory:
    """演化记忆 — 记录扩展的完整生命周期。"""

    _entries: dict[str, EvolutionEntry] = field(default_factory=dict)

    def record_candidate(self, candidate: ExtensionCandidate) -> EvolutionEntry:
        entry = EvolutionEntry(
            candidate_id=candidate.candidate_id,
            name=candidate.name,
            state_history=[(ExtensionState.DISCOVERED, candidate.discovered_tick)],
        )
        self._entries[candidate.candidate_id] = entry
        return entry

    def record_state_change(
        self, candidate_id: str, new_state: ExtensionState, tick_id: int,
    ) -> None:
        """记录状态变更。"""
        entry = self._entries.get(candidate_id)
        if entry:
            new_history = list(entry.state_history)
            new_history.append((new_state, tick_id))
            self._entries[candidate_id] = EvolutionEntry(
                candidate_id=entry.candidate_id,
                name=entry.name,
                state_history=new_history,
                integration_record=entry.integration_record,
                health_history=list(entry.health_history),
                repair_events=list(entry.repair_events),
                frozen_tick=entry.frozen_tick,
                frozen_reason=entry.frozen_reason,
            )

    def record_integration(self, candidate_id: str, record: IntegrationRecord) -> None:
        entry = self._entries.get(candidate_id)
        if entry:
            self._entries[candidate_id] = EvolutionEntry(
                candidate_id=entry.candidate_id,
                name=entry.name,
                state_history=list(entry.state_history),
                integration_record=record,
                health_history=list(entry.health_history),
                repair_events=list(entry.repair_events),
                frozen_tick=entry.frozen_tick,
                frozen_reason=entry.frozen_reason,
            )

    def record_health(self, candidate_id: str, report: HealthReport) -> None:
        entry = self._entries.get(candidate_id)
        if entry:
            self._entries[candidate_id] = EvolutionEntry(
                candidate_id=entry.candidate_id,
                name=entry.name,
                state_history=list(entry.state_history),
                integration_record=entry.integration_record,
                health_history=list(entry.health_history) + [report],
                repair_events=list(entry.repair_events),
                frozen_tick=entry.frozen_tick,
                frozen_reason=entry.frozen_reason,
            )

    def record_repair(self, candidate_id: str, event: str) -> None:
        entry = self._entries.get(candidate_id)
        if entry:
            self._entries[candidate_id] = EvolutionEntry(
                candidate_id=entry.candidate_id,
                name=entry.name,
                state_history=list(entry.state_history),
                integration_record=entry.integration_record,
                health_history=list(entry.health_history),
                repair_events=list(entry.repair_events) + [event],
                frozen_tick=entry.frozen_tick,
                frozen_reason=entry.frozen_reason,
            )

    def freeze(self, candidate_id: str, tick_id: int, reason: str = "") -> None:
        entry = self._entries.get(candidate_id)
        if entry:
            self._entries[candidate_id] = EvolutionEntry(
                candidate_id=entry.candidate_id,
                name=entry.name,
                state_history=list(entry.state_history),
                integration_record=entry.integration_record,
                health_history=list(entry.health_history),
                repair_events=list(entry.repair_events),
                frozen_tick=tick_id,
                frozen_reason=reason,
            )

    def get(self, candidate_id: str) -> EvolutionEntry | None:
        return self._entries.get(candidate_id)

    @property
    def all_entries(self) -> dict[str, EvolutionEntry]:
        return dict(self._entries)


__all__ = ["EvolutionMemory"]
