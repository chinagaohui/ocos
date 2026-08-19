"""
M0.5 Knowledge Promotion Rules — 触发条件 + 权限 + 提升前条件。

定义了知识在层级间提升的规则引擎，包括:
- PromotionTrigger: 触发条件（何时启动提升流程）
- PromotionPolicy: 提升策略（权限 + 前条件）
- PromotionRuleEngine: 规则评估引擎
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    can_elevate,
    validate_elevation,
)

logger = logging.getLogger(__name__)


class PromotionTriggerType(str, Enum):
    """提升触发条件类型。"""
    REPETITION = "repetition"        # 相同观察出现 N 次
    CONFIDENCE = "confidence"        # 置信度超过阈值
    GOVERNANCE = "governance"        # Governance 审批通过
    MANUAL = "manual"                # 手动触发
    TIME_BASED = "time_based"        # 基于时间（观察持续有效超过 T 时长）


@dataclasses.dataclass(frozen=True)
class PromotionTrigger:
    """提升触发条件定义。"""
    trigger_type: PromotionTriggerType = PromotionTriggerType.REPETITION
    threshold: int | float = 3       # 触发阈值（次数/置信度/时长等）
    description: str = ""


# ── 默认触发条件模板 ──────────────────────────────────────────────────────

DEFAULT_TRIGGERS: dict[KnowledgeLevel, list[PromotionTrigger]] = {
    KnowledgeLevel.OBSERVATION: [
        PromotionTrigger(
            trigger_type=PromotionTriggerType.REPETITION,
            threshold=3,
            description="同一观察出现 >= 3 次可提升为 Evidence",
        ),
    ],
    KnowledgeLevel.EVIDENCE: [
        PromotionTrigger(
            trigger_type=PromotionTriggerType.REPETITION,
            threshold=5,
            description="同一 Evidence 出现 >= 5 次可提升为 Pattern",
        ),
        PromotionTrigger(
            trigger_type=PromotionTriggerType.CONFIDENCE,
            threshold=0.7,
            description="Evidence 置信度 >= 0.7 可提升为 Pattern",
        ),
    ],
    KnowledgeLevel.PATTERN: [
        PromotionTrigger(
            trigger_type=PromotionTriggerType.CONFIDENCE,
            threshold=0.85,
            description="Pattern 置信度 >= 0.85 可提升为 Principle",
        ),
        PromotionTrigger(
            trigger_type=PromotionTriggerType.GOVERNANCE,
            threshold=1,
            description="Pattern 提升需 Governance 审批",
        ),
    ],
    KnowledgeLevel.PRINCIPLE: [
        PromotionTrigger(
            trigger_type=PromotionTriggerType.GOVERNANCE,
            threshold=1,
            description="Principle 提升需 Governance 审批",
        ),
    ],
    KnowledgeLevel.POLICY: [],  # 顶层不可再提升
}


# ── 权限和前条件 ──────────────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class PreCondition:
    """提升前条件检查。"""
    name: str
    check_fn: Callable[[KnowledgeUnit, dict[str, Any]], bool]
    description: str = ""


class PromotionPolicy:
    """提升策略：定义给定提升路径的权限和前条件。"""

    def __init__(
        self,
        allowed_sources: list[str] | None = None,
        pre_conditions: list[PreCondition] | None = None,
        requires_governance: bool = False,
    ):
        self.allowed_sources = allowed_sources or []
        self.pre_conditions = pre_conditions or []
        self.requires_governance = requires_governance

    def evaluate(
        self,
        unit: KnowledgeUnit,
        source: str = "",
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, list[str]]:
        """评估提升策略是否通过。

        Returns:
            (permitted, error_messages)
        """
        errors: list[str] = []
        context = context or {}

        # 1. 权限检查
        if self.allowed_sources and source not in self.allowed_sources:
            errors.append(
                f"来源 '{source}' 未被授权发起提升；"
                f"允许的来源: {self.allowed_sources}"
            )

        # 2. Governance 检查
        if self.requires_governance:
            governance_approved = context.get("governance_approved", False)
            if not governance_approved:
                errors.append("此提升路径需要 Governance 审批")

        # 3. 前条件检查
        for pc in self.pre_conditions:
            if not pc.check_fn(unit, context):
                errors.append(f"前条件不满足: {pc.description}")

        ok = len(errors) == 0
        if not ok:
            logger.warning("PromotionPolicy.evaluate failed: unit=%s source=%s errors=%s",
                           unit.unit_id, source, errors)
        else:
            logger.debug("PromotionPolicy.evaluate ok: unit=%s source=%s", unit.unit_id, source)
        return (ok, errors)

    @classmethod
    def default_for_level(
        cls, source_level: KnowledgeLevel, target_level: KnowledgeLevel
    ) -> PromotionPolicy:
        """返回层级间的默认提升策略。"""
        requires_gov = False
        pre_conditions: list[PreCondition] = [
            PreCondition(
                name="valid_elevation",
                check_fn=lambda u, c: can_elevate(u.level, target_level),
                description=f"必须可从 {source_level.value} 提升到 {target_level.value}",
            ),
            PreCondition(
                name="active_or_verified",
                check_fn=lambda u, c: u.status in (
                    KnowledgeStatus.ACTIVE, KnowledgeStatus.VERIFIED
                ),
                description="知识必须是 ACTIVE 或 VERIFIED 状态",
            ),
        ]

        # Pattern→Principle 和 Principle→Policy 需要 Governance
        if source_level in (
            KnowledgeLevel.PATTERN, KnowledgeLevel.PRINCIPLE
        ):
            requires_gov = True

        return cls(
            allowed_sources=["governance", "pattern_detector", "manual"],
            pre_conditions=pre_conditions,
            requires_governance=requires_gov,
        )


# ── 规则引擎 ──────────────────────────────────────────────────────────────


class PromotionRuleEngine:
    """提升规则引擎：评估触发条件 + 执行策略检查。"""

    def __init__(self):
        self._policies: dict[tuple[KnowledgeLevel, KnowledgeLevel], PromotionPolicy] = {}

    def register_policy(
        self,
        source_level: KnowledgeLevel,
        target_level: KnowledgeLevel,
        policy: PromotionPolicy,
    ) -> None:
        """注册提升路径的审批策略。"""
        self._policies[(source_level, target_level)] = policy
        logger.debug("register_policy: %s -> %s", source_level.value, target_level.value)

    def get_policy(
        self,
        source_level: KnowledgeLevel,
        target_level: KnowledgeLevel,
    ) -> PromotionPolicy | None:
        """获取提升路径的策略。"""
        policy = self._policies.get((source_level, target_level))
        logger.debug("get_policy: %s -> %s = %s", source_level.value, target_level.value,
                     "found" if policy else "None")
        return policy

    def can_promote(
        self,
        unit: KnowledgeUnit,
        target_level: KnowledgeLevel,
        source: str = "",
        context: dict[str, Any] | None = None,
    ) -> tuple[bool, list[str]]:
        """完整评估一个 KnowledgeUnit 是否可以提升。

        同时检查：
        1. 层级提升合法性（can_elevate）
        2. 状态合法性（validate_elevation）
        3. 策略检查（权限 + 前条件）

        Returns:
            (can_promote, errors)
        """
        errors: list[str] = []

        # 1. 基础层级验证
        ok, ve_errors = validate_elevation(unit, target_level)
        if not ok:
            errors.extend(ve_errors)

        # 2. 策略检查
        policy = self._policies.get((unit.level, target_level))
        if policy:
            p_ok, p_errors = policy.evaluate(unit, source, context)
            if not p_ok:
                errors.extend(p_errors)
        elif can_elevate(unit.level, target_level):
            # 未注册策略时使用默认策略
            default = PromotionPolicy.default_for_level(unit.level, target_level)
            p_ok, p_errors = default.evaluate(unit, source, context)
            if not p_ok:
                errors.extend(p_errors)

        ok = len(errors) == 0
        logger.debug("can_promote: unit=%s %s -> %s source=%s result=%s",
                     unit.unit_id, unit.level.value, target_level.value, source, ok)
        return (ok, errors)

    def check_trigger(
        self,
        unit: KnowledgeUnit,
        repetition_count: int = 0,
        confidence: float = 0.0,
        governance_approved: bool = False,
    ) -> tuple[bool, str]:
        """检查触发条件是否满足。

        Returns:
            (triggered, reason)
        """
        triggers = DEFAULT_TRIGGERS.get(unit.level, [])
        if not triggers:
            logger.debug("check_trigger: %s no triggers (top level)", unit.level.value)
            return (False, f"{unit.level.value} 层级无向上提升路径")

        for t in triggers:
            if t.trigger_type == PromotionTriggerType.REPETITION:
                if repetition_count >= t.threshold:
                    logger.info("check_trigger triggered: unit=%s type=repetition count=%d threshold=%d",
                                unit.unit_id, repetition_count, t.threshold)
                    return (
                        True,
                        f"重复次数 {repetition_count} >= {t.threshold}，满足触发条件"
                    )

            elif t.trigger_type == PromotionTriggerType.CONFIDENCE:
                if confidence >= t.threshold:
                    logger.info("check_trigger triggered: unit=%s type=confidence score=%f threshold=%f",
                                unit.unit_id, confidence, t.threshold)
                    return (
                        True,
                        f"置信度 {confidence} >= {t.threshold}，满足触发条件"
                    )

            elif t.trigger_type == PromotionTriggerType.GOVERNANCE:
                if governance_approved:
                    logger.info("check_trigger triggered: unit=%s type=governance", unit.unit_id)
                    return (True, "Governance 已审批")

        logger.debug("check_trigger not triggered: unit=%s level=%s", unit.unit_id, unit.level.value)
        return (False, "未满足任何触发条件")

    def load_default_policies(self) -> None:
        """加载所有默认提升策略。"""
        from ocos.knowledge.store.ontology import ELEVATION_MATRIX
        for source, targets in ELEVATION_MATRIX.items():
            for target in targets:
                policy = PromotionPolicy.default_for_level(source, target)
                self._policies[(source, target)] = policy
        logger.info("load_default_policies: loaded %d policies", len(self._policies))
