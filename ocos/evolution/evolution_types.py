"""Phase 47: Evolution Types — 认知进化类型系统。

Cognitive Evolution Governance 回答最后一个核心问题:
    如何在保持自身稳定的情况下，持续变得更好？

不是"Self Evolution"的自发进化——而是受治理的、信号驱动的改进。

进化流程:
    Observation → Detection → Proposal → Analysis → Sandbox → Approval → Migration → Rollback Safety

核心边界:
    CE47-01: Evolution ≠ Autonomy  — 进化由系统信号触发 (Health/Experience/Performance)
    CE47-02: Proposal ≠ Execution  — 提案需多层审批
    CE47-03: Migration ≠ Destruction — 迁移可回滚
    CE47-04: Evolution ≠ Identity Change — 禁止修改 identity/constitution/permission model
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 进化状态
# ═══════════════════════════════════════════════════════════════════════════════


class EvolutionState(Enum):
    """进化提案的状态变迁。"""
    DETECTED = "detected"            # Health/Experience 信号检测到改进机会
    DRAFTING = "drafting"            # 正在生成提案
    ANALYZING = "analyzing"          # 影响分析中
    SANDBOXING = "sandboxing"        # 沙箱测试中
    APPROVED = "approved"            # 治理审批通过
    MIGRATING = "migrating"          # 迁移执行中
    ACTIVE = "active"                # 进化已生效
    ROLLED_BACK = "rolled_back"      # 回滚 (CE47-03)
    REJECTED = "rejected"            # 拒绝
    OBSOLETE = "obsolete"            # 已被后续进化替代


class EvolutionTrigger(Enum):
    """进化触发器来源。"""
    HEALTH_ALERT = "health_alert"         # Health Monitor 发现异常
    EXPERIENCE_PATTERN = "experience"    # 持续类似经验形成模式
    PERFORMANCE_DEGRADATION = "perf"     # 性能退化
    CAPABILITY_GAP = "cap_gap"           # 能力缺失
    DECISION_CONSISTENCY_DRIFT = "drift" # 决策漂移
    WORLD_MODEL_CONFLICT = "conflict"    # 世界模型冲突
    MANUAL_PROPOSAL = "manual"           # 用户/治理层手动提议


# ═══════════════════════════════════════════════════════════════════════════════
# 进化领域 (允许修改)
# ═══════════════════════════════════════════════════════════════════════════════


class EvolutionDomain(Enum):
    """进化可以修改的领域。"""
    CAPABILITY = "capability"           # 新增/优化能力
    CONNECTION = "connection"           # 模块间连接优化
    PARAMETER = "parameter"             # 参数调优
    ADAPTER = "adapter"                 # 适配器升级
    KNOWLEDGE_STRUCTURE = "knowledge"   # 知识结构优化
    ATTENTION_POLICY = "attention"      # 注意力策略
    LEARNING_STRATEGY = "learning"      # 学习策略
    EXTENSION_INTEGRATION = "extension" # 扩展集成优化


# 永远禁止修改
FORBIDDEN_DOMAINS = (
    "identity",
    "constitution",
    "permission_model",
    "core_values",
    "anchor",
)


# ═══════════════════════════════════════════════════════════════════════════════
# 影响评估
# ═══════════════════════════════════════════════════════════════════════════════


class ImpactLevel(Enum):
    """进化影响等级。"""
    NEGLIGIBLE = "negligible"    # 几乎无影响
    LOW = "low"                  # 低影响，局部变化
    MODERATE = "moderate"        # 中等影响，多模块
    HIGH = "high"                # 高影响，需额外验证
    CRITICAL = "critical"        # 可能影响系统稳定，需最高审批


@dataclass
class ImpactAssessment:
    """进化影响评估报告。"""
    domain: EvolutionDomain = EvolutionDomain.PARAMETER
    level: ImpactLevel = ImpactLevel.LOW
    affected_modules: list[str] = field(default_factory=list)
    abi_breaking: bool = False              # 是否破坏 ABI
    identity_safe: bool = True              # CE47-04: 是否触碰 identity
    constitution_safe: bool = True          # CE47-04: 是否触碰 constitution
    permission_safe: bool = True            # CE47-04: 是否触碰 permission model
    rollback_viable: bool = True            # CE47-03: 是否可回滚
    estimated_downtime_ticks: int = 0       # 预计停机 tick 数

    @property
    def is_safe(self) -> bool:
        """进化是否边界安全。"""
        return (
            self.identity_safe
            and self.constitution_safe
            and self.permission_safe
            and self.rollback_viable
        )

    @property
    def boundary_violations(self) -> list[str]:
        """CE47-04 越界列表。"""
        viol = []
        if not self.identity_safe:
            viol.append("identity")
        if not self.constitution_safe:
            viol.append("constitution")
        if not self.permission_safe:
            viol.append("permission_model")
        return viol


# ═══════════════════════════════════════════════════════════════════════════════
# Evolution Proposal
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EvolutionProposal:
    """进化提案。"""
    proposal_id: str = ""
    trigger: EvolutionTrigger = EvolutionTrigger.HEALTH_ALERT
    source_tick: int = 0

    # What
    domain: EvolutionDomain = EvolutionDomain.PARAMETER
    description: str = ""
    rationale: str = ""               # 为什么需要这个进化
    evidence: list[str] = field(default_factory=list)  # 证据列表

    # How
    target_module: str = ""           # 目标模块路径
    change_type: str = ""             # add / modify / optimize / replace
    change_spec: str = ""             # 变更规范

    # Status
    state: EvolutionState = EvolutionState.DETECTED
    impact: ImpactAssessment = field(default_factory=ImpactAssessment)

    # Approval
    sandbox_passed: bool = False
    governance_approved: bool = False
    approved_by: str = ""             # 审批链

    # Results
    migration_tick: int = 0
    rollback_snapshot: str = ""       # 回滚快照标识
    active_since_tick: int = 0

    @property
    def is_boundary_safe(self) -> bool:
        return self.impact.is_safe

    @property
    def ready_for_migration(self) -> bool:
        return (
            self.state == EvolutionState.APPROVED
            and self.sandbox_passed
            and self.governance_approved
            and self.is_boundary_safe
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Rollback
# ═══════════════════════════════════════════════════════════════════════════════


class RollbackReason(Enum):
    """回滚原因。"""
    TEST_FAILURE = "test_failure"
    ABI_BREAK = "abi_break"
    PERFORMANCE_REGRESSION = "perf_regression"
    UNEXPECTED_SIDE_EFFECT = "side_effect"
    MANUAL = "manual"


@dataclass
class RollbackRecord:
    """回滚记录 (CE47-03)。"""
    proposal_id: str = ""
    reason: RollbackReason = RollbackReason.TEST_FAILURE
    restored_at_tick: int = 0
    snapshot_before: str = ""
    snapshot_after: str = ""
    verified: bool = False           # 回滚是否正确恢复


__all__ = [
    "EvolutionState",
    "EvolutionTrigger",
    "EvolutionDomain",
    "FORBIDDEN_DOMAINS",
    "ImpactLevel",
    "ImpactAssessment",
    "EvolutionProposal",
    "RollbackReason",
    "RollbackRecord",
]
