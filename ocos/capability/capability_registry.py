"""Phase 45: CapabilityRegistry — 能力注册中心。

维护所有已知能力的档案，支持注册、查询、状态管理。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    Capability, CapabilityType, CapabilityState,
)


@dataclass
class CapabilityRegistry:
    """能力注册中心。

    提供:
        - register: 注册新能力（通常来自 Phase 44 批准后）
        - query:    按类型/标签查询
        - get:      按 ID 获取
        - update:   状态更新
    """

    _capabilities: dict[str, Capability] = field(default_factory=dict)

    # ── 注册 ──

    def register(self, cap: Capability) -> None:
        """注册一个能力。如果 ID 已存在，更新之。"""
        self._capabilities[cap.capability_id] = cap

    def register_from_extension(
        self, name: str, cap_type: CapabilityType,
        provider: str = "", endpoint: str = "",
        description: str = "", tags: list[str] | None = None,
    ) -> Capability:
        """从 Phase 44 Extension 注册能力。"""
        cap = Capability(
            capability_id=f"cap:{name}",
            name=name,
            cap_type=cap_type,
            provider=provider,
            endpoint=endpoint or name,
            description=description,
            tags=tags or [],
            state=CapabilityState.AVAILABLE,
        )
        self._capabilities[cap.capability_id] = cap
        return cap

    # ── 查询 ──

    def get(self, capability_id: str) -> Capability | None:
        return self._capabilities.get(capability_id)

    def query_by_type(self, cap_type: CapabilityType) -> list[Capability]:
        return [c for c in self._capabilities.values() if c.cap_type == cap_type]

    def query_by_tag(self, tag: str) -> list[Capability]:
        return [c for c in self._capabilities.values() if tag in c.tags]

    def query_callable(self) -> list[Capability]:
        return [c for c in self._capabilities.values() if c.is_callable]

    @property
    def all(self) -> list[Capability]:
        return list(self._capabilities.values())

    @property
    def count(self) -> int:
        return len(self._capabilities)

    # ── 状态管理 ──

    def update_state(self, capability_id: str, state: CapabilityState) -> None:
        cap = self._capabilities.get(capability_id)
        if cap:
            self._capabilities[capability_id] = Capability(
                capability_id=cap.capability_id,
                name=cap.name,
                cap_type=cap.cap_type,
                executor_kind=cap.executor_kind,
                provider=cap.provider,
                endpoint=cap.endpoint,
                description=cap.description,
                input_schema=cap.input_schema,
                output_schema=cap.output_schema,
                tags=list(cap.tags),
                state=state,
                trust_level=cap.trust_level,
                performance_score=cap.performance_score,
                cost_estimate=cap.cost_estimate,
                max_concurrency=cap.max_concurrency,
            )

    def update_performance(self, capability_id: str, score: float) -> None:
        cap = self._capabilities.get(capability_id)
        if cap:
            new_score = (cap.performance_score + score) / 2  # moving avg
            self._capabilities[capability_id] = Capability(
                capability_id=cap.capability_id,
                name=cap.name,
                cap_type=cap.cap_type,
                executor_kind=cap.executor_kind,
                provider=cap.provider,
                endpoint=cap.endpoint,
                description=cap.description,
                input_schema=cap.input_schema,
                output_schema=cap.output_schema,
                tags=list(cap.tags),
                state=cap.state,
                trust_level=cap.trust_level,
                performance_score=round(new_score, 4),
                cost_estimate=cap.cost_estimate,
                max_concurrency=cap.max_concurrency,
            )


__all__ = ["CapabilityRegistry"]
