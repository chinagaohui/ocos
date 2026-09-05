"""Phase 42: WorldValidator — 世界更新输入治理。

核心约束 WM42-04:
    外部 Agent 可以提供 Observation/Data/Analysis，
    但不能直接写入 World Model。
    必须经过: Observation → Validation → World Update。

验证规则:
    1. 来源可信度检查
    2. 与已有模型的一致性检查
    3. 多来源交叉验证
    4. 置信度阈值
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ocos.world_model.world_types import (Observation, Entity, Relation,
                                          EntityType)


class ValidationDecision(Enum):
    ACCEPT = "accept"          # 接受，可以更新
    NEED_MORE = "need_more"    # 需要更多证据
    REJECT = "reject"          # 拒接
    CONFLICT = "conflict"      # 与已有模型冲突
    QUARANTINE = "quarantine"  # 隔离观察，不更新也不丢弃


class ValidationIssue(Enum):
    UNKNOWN_SOURCE = "unknown_source"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICT_WITH_EXISTING = "conflict_with_existing"
    SINGLE_SOURCE = "single_source"      # 只有单一来源
    MISSING_EVIDENCE = "missing_evidence"
    INCONSISTENT = "inconsistent"        # 内部不一致


@dataclass(frozen=True)
class ValidationResult:
    """验证结果。"""
    decision: ValidationDecision
    issues: tuple[ValidationIssue, ...] = ()
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.decision == ValidationDecision.ACCEPT


# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WorldValidator:
    """世界模型输入治理。

    任何外部输入在写入 World Store 前必须通过此验证。
    """

    min_confidence: float = 0.5
    max_confidence: float = 1.0
    min_sources: int = 1  # 最少需要多少个来源
    trusted_sources: set[str] = field(default_factory=set)

    # ── 观察 → 验证 ──

    def validate_observation(self, observation: Observation) -> ValidationResult:
        """验证外部观察是否可以接受。

        检查:
            1. 来源是否已知
            2. 是否有冲突信息
        """
        issues: list[ValidationIssue] = []

        # Rule 1: 来源检查
        if self.trusted_sources and observation.source not in self.trusted_sources:
            issues.append(ValidationIssue.UNKNOWN_SOURCE)

        # Rule 2: 内容非空
        has_content = bool(
            observation.entity_id or
            observation.claimed_relation or
            observation.claimed_state
        )
        if not has_content:
            issues.append(ValidationIssue.MISSING_EVIDENCE)

        if issues:
            return ValidationResult(
                decision=ValidationDecision.NEED_MORE,
                issues=tuple(issues),
                reason=f"Observation from {observation.source} needs validation: {[i.value for i in issues]}",
            )

        return ValidationResult(decision=ValidationDecision.ACCEPT)

    def validate_against_model(
        self,
        observation: Observation,
        existing_entities: dict[str, Entity],
        existing_relations: dict[str, Relation],
    ) -> ValidationResult:
        """额外验证：与已有世界模型的一致性检查。"""
        issues: list[ValidationIssue] = []

        # 先做基本验证
        base = self.validate_observation(observation)
        if not base.accepted:
            return base

        # 实体冲突检查
        if observation.entity_id and observation.claimed_state:
            existing = existing_entities.get(observation.entity_id)
            if existing:
                # S2.1 (白皮书 P1-4): 原为 `existing.entity_type !=
                # existing.entity_type` 自比较恒 False — 冲突检查从未触发。
                # 观察侧类型取 claimed_state.attributes["entity_type"]，
                # 与 world_store._extract_entity_type 同语义。
                observed_type = self._observed_entity_type(observation)
                if (observed_type is not None
                        and existing.entity_type != observed_type):
                    # 同一个 ID 但不同类型 → 冲突
                    issues.append(ValidationIssue.CONFLICT_WITH_EXISTING)

        if issues:
            return ValidationResult(
                decision=ValidationDecision.CONFLICT,
                issues=tuple(issues),
                reason=f"Observation conflicts with existing model: {[i.value for i in issues]}",
            )

        return ValidationResult(decision=ValidationDecision.ACCEPT)

    # ── 置信度阈值 ──

    @staticmethod
    def _observed_entity_type(observation):
        """从观察的 claimed_state 提取声称的实体类型（无声称返回 None）。

        S2.1: 与 world_store._extract_entity_type 同语义，但此处对
        非法值返回 None（无法判定 → 不产生冲突），并避免
        validator → store 反向依赖。
        """
        if observation.claimed_state is None:
            return None
        raw = observation.claimed_state.attributes.get("entity_type")
        if isinstance(raw, str):
            try:
                return EntityType(raw)
            except ValueError:
                return None
        return None

    def clamp_confidence(self, value: float) -> float:
        """将置信度限制在 [min_confidence, max_confidence] 范围内。"""
        return max(self.min_confidence, min(self.max_confidence, value))


__all__ = [
    "ValidationDecision",
    "ValidationIssue",
    "ValidationResult",
    "WorldValidator",
]
