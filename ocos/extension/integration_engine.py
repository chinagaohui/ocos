"""Phase 44: IntegrationEngine — 扩展集成引擎。

正式接入扩展——不是修改核心，而是增加认知连接。

约束:
    - 不能修改 Identity
    - 不能绕过 Permission
    - 不能自动创建 Goal
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import (
    ExtensionCandidate, IntegrationRecord, TrustLevel,
)


@dataclass
class IntegrationEngine:
    """集成引擎 — 将批准后的扩展接入 OCOS。

    集成后返回 IntegrationRecord 记录接入点。
    """

    _records: dict[str, IntegrationRecord] = field(default_factory=dict)
    _counter: int = field(default=0, init=False)

    def integrate(self, candidate: ExtensionCandidate, tick_id: int = 0) -> IntegrationRecord:
        self._counter += 1
        # 确定连接点
        connection_points = self._determine_connection_points(candidate)

        record = IntegrationRecord(
            candidate_id=candidate.candidate_id,
            integration_id=f"integration:{self._counter}",
            connection_points=connection_points,
            adapters_applied=[],
            integrated_tick=tick_id,
            trust_level=TrustLevel.UNKNOWN,
        )
        self._records[candidate.candidate_id] = record
        return record

    def _determine_connection_points(self, c: ExtensionCandidate) -> list[str]:
        """根据扩展类型确定接入点。"""
        from ocos.extension.extension_types import ExtensionType
        mapping = {
            ExtensionType.PERCEPTION: ["input_bus"],
            ExtensionType.MEMORY: ["memory_hub"],
            ExtensionType.REASONING: ["reasoning_pipeline"],
            ExtensionType.CAPABILITY: ["capability_registry", "permission_gateway"],
            ExtensionType.COMMUNICATION: ["output_bus"],
            ExtensionType.KNOWLEDGE: ["knowledge_registry"],
            ExtensionType.META: ["monitoring_hub"],
        }
        return mapping.get(c.extension_type, ["generic_adapter"])

    def get_record(self, candidate_id: str) -> IntegrationRecord | None:
        return self._records.get(candidate_id)

    def update_trust(self, candidate_id: str, level: TrustLevel) -> None:
        if candidate_id in self._records:
            # IntegrationRecord is frozen, replace
            old = self._records[candidate_id]
            new_record = IntegrationRecord(
                candidate_id=old.candidate_id,
                integration_id=old.integration_id,
                connection_points=list(old.connection_points),
                adapters_applied=list(old.adapters_applied),
                integrated_tick=old.integrated_tick,
                trust_level=level,
            )
            self._records[candidate_id] = new_record


__all__ = ["IntegrationEngine"]
