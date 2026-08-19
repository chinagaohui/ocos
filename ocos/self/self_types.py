"""Phase 40: Self Model ABI — 核心类型定义。

SelfModel = Runtime Self Representation（运行时自我投影）

不是:
    SelfModel ≠ Identity          — Identity.anchor 是不可变核心
    SelfModel ≠ Personality       — 不是人格生成器
    SelfModel ≠ Autonomous Desire — 不产生目标

是:
    "当前 OCOS 对自身状态的理解"
    建立在不可变 Identity.anchor 之上的可运行投影

四层边界:
    S40-01 Identity Boundary:     identity_ref 只引用不复制
    S40-02 Self ≠ Goal:           不生成目标
    S40-03 Self ≠ Belief:         自身状态判断 ≠ 世界判断
    S40-04 Self Update Source:    Experience | CapabilityRegistry | MemoryConsolidation | RuntimeObservation
                                  禁止 External Agent 直接更新
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 更新来源枚举
# ═══════════════════════════════════════════════════════════════════════════════


class SelfUpdateSource(Enum):
    """Self Model 更新来源 — 只有这些来源可以修改 SelfModel。

    禁止:
        EXTERNAL_AGENT — 外部 Agent 直接更新
    """

    EXPERIENCE = "experience"
    """从 Experience/Memory 中抽象出的经验模式。"""

    CAPABILITY_REGISTRY = "capability_registry"
    """从 Capability Registry 获取的能力列表。"""

    MEMORY_CONSOLIDATION = "memory_consolidation"
    """Memory Consolidation (Phase 24) 产出的模式。"""

    RUNTIME_OBSERVATION = "runtime_observation"
    """Runtime 对自身行为的观察（如 attention_history）。"""

    REFLECTION = "reflection"
    """Self-Reflection 模块产出的自我洞察。"""

    # ── 以下明确禁止 ──

    EXTERNAL_AGENT = "__forbidden__external_agent"
    """❌ 外部 Agent 直接更新 SelfModel。"""


# ═══════════════════════════════════════════════════════════════════════════════
# SelfUpdateContract
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SelfUpdateContract:
    """Self Model 更新合同 — 每次 SelfModel 变更必须附带此合同。

    合同校验:
        1. source ∈ ALLOWED_UPDATES
        2. source ∉ FORBIDDEN_UPDATES
        3. 不修改 identity_ref
        4. 变更字段在 allowed_fields 内
    """

    source: SelfUpdateSource
    reason: str
    tick_id: int
    fields_changed: tuple[str, ...]
    evidence_count: int = 0  # 证据数量
    confidence_impact: float = 0.0  # 对 self_confidence 的影响 [-1, 1]

    # 禁止的来源
    FORBIDDEN: frozenset[SelfUpdateSource] = frozenset({
        SelfUpdateSource.EXTERNAL_AGENT,
    })

    @property
    def is_valid(self) -> bool:
        """检查更新合同是否合法。"""
        if self.source in self.FORBIDDEN:
            return False
        if not self.fields_changed:
            return False
        if not self.reason.strip():
            return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# 知识域置信度
# ═══════════════════════════════════════════════════════════════════════════════


class KnowledgeConfidence(Enum):
    """知识域的置信级别。"""

    KNOWN = "known"             # 确信掌握
    UNCERTAIN = "uncertain"     # 不确定
    PARTIAL = "partial"         # 部分了解
    SURFACE = "surface"         # 表层了解
    UNKNOWN = "unknown"         # 已知未知
    NEEDS_VERIFICATION = "needs_verification"  # 需要外部验证


# ═══════════════════════════════════════════════════════════════════════════════
# Capability 声明
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CapabilityStatement:
    """SelfModel 对一项能力的声明。

    关键: 这是声明，不是实际能力。SelfModel 记录的是 OCOS "认为"自己
    有什么能力，而不是能力本身。实际能力在 ActionLayer 注册。
    """

    name: str           # 能力名称
    available: bool     # 是否当前可用
    confidence: float   # 置信度 [0, 1]
    source: str         # 来源（如 "capability_registry_v1"）
    last_verified_tick: int = 0
    notes: str = ""

    @property
    def is_known_available(self) -> bool:
        return self.available and self.confidence >= 0.7

    @property
    def is_known_unavailable(self) -> bool:
        return not self.available and self.confidence >= 0.7


# ═══════════════════════════════════════════════════════════════════════════════
# 知识域声明
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DomainStatement:
    """SelfModel 对一个知识域的认知声明。"""

    domain: str                     # 领域名
    confidence: KnowledgeConfidence # 置信级别
    evidence_count: int = 0         # 证据数量
    last_updated_tick: int = 0
    note: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 经验模式
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExperiencePattern:
    """从 Memory 中抽象出的经验模式。

    不是具体事件，而是统计性认知特征。
    """

    pattern_id: str
    label: str          # 模式标签
    category: str       # "successful" | "failure" | "neutral"
    frequency: int      # 出现次数
    confidence: float   # 置信度 [0, 1]
    evidence_ids: tuple[str, ...]  # 来源 Memory entry IDs
    abstracted_at_tick: int
    note: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 偏好类型
# ═══════════════════════════════════════════════════════════════════════════════


class PreferenceType(Enum):
    """偏好来源分类 — User Preference 和 OCOS Operational Preference 必须分离。"""

    USER = "user"
    """用户偏好 — 从用户行为/反馈中推断，不替代用户价值。"""

    OPERATIONAL = "operational"
    """OCOS 操作偏好 — 运行效率/成本权衡，不是价值判断。"""


@dataclass(frozen=True)
class PreferenceEntry:
    """单条偏好记录。

    User Preference 例: "详细解释"、"先给方案再执行"
    Operational Preference 例: "优先本地计算"、"批处理优于单条"
    """

    pref_id: str
    pref_type: PreferenceType
    key: str            # 偏好键名
    value: str          # 偏好值
    evidence: str       # 证据来源
    confidence: float   # [0, 1]
    updated_tick: int


# ═══════════════════════════════════════════════════════════════════════════════
# SelfBoundaryRules
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SelfBoundaryRules:
    """Self Model 的宪法边界 — 硬约束，不可被任何更新绕过。

    属性:
        identity_is_immutable: identity_ref 不能修改
        no_goal_generation: Self 不产生 Goal
        no_direct_belief_mutation: Self 不直接修改 Belief
        allowed_update_sources: 允许的更新来源
        self_confidence_bounds: 自信度边界
    """

    identity_is_immutable: bool = True
    no_goal_generation: bool = True
    no_direct_belief_mutation: bool = True

    allowed_update_sources: tuple[SelfUpdateSource, ...] = (
        SelfUpdateSource.EXPERIENCE,
        SelfUpdateSource.CAPABILITY_REGISTRY,
        SelfUpdateSource.MEMORY_CONSOLIDATION,
        SelfUpdateSource.RUNTIME_OBSERVATION,
        SelfUpdateSource.REFLECTION,
    )

    self_confidence_bounds: tuple[float, float] = (0.1, 1.0)

    def is_update_allowed(self, contract: SelfUpdateContract) -> tuple[bool, str]:
        """校验更新合同是否符合边界规则。"""
        if not contract.is_valid:
            return False, "invalid contract"
        if contract.source not in self.allowed_update_sources:
            return False, f"forbidden source: {contract.source.value}"
        if not (-1.0 <= contract.confidence_impact <= 1.0):
            return False, "confidence_impact out of range"
        return True, "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# SelfModel 主体
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SelfModel:
    """Self Model — Runtime Self Representation。

    identity_ref 是只读引用，不是副本。SelfModel 投影 Identity.anchor
    但不包含它。

    五个组件:
        capability_awareness  — "我能做什么"
        knowledge_boundary    — "我知道什么"
        experience_profile    — "我经历过什么"
        preference_model      — "我和用户偏好什么"  (User + Operational 分离)
        cognitive_state       — "我当前认知状态怎样"
    """

    # ── 核心引用 ──

    identity_ref: str
    """Identity.anchor 的引用（agent_id），只读，不可修改。"""

    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 五个组件 ──

    capability_awareness: Optional[Any] = None     # CapabilityAwareness
    knowledge_boundary: Optional[Any] = None       # KnowledgeBoundary
    experience_profile: Optional[Any] = None       # ExperienceProfile
    preference_model: Optional[Any] = None         # PreferenceModel
    cognitive_state: Optional[Any] = None          # CognitiveState

    # ── 元信息 ──

    self_confidence: float = 0.5
    """整体自我认知置信度 [0, 1]。
    
    初始值 0.5 表示 '我不确定我有多了解自己'。
    随 Experience 积累逐渐调整。
    """

    update_history: list[SelfUpdateContract] = field(default_factory=list)

    boundary_rules: SelfBoundaryRules = field(default_factory=SelfBoundaryRules)

    # ── 更新 API ──

    def update(
        self,
        contract: SelfUpdateContract,
        component: str,
        new_value: Any,
    ) -> bool:
        """带合同校验的组件更新。

        返回 True 如果更新成功，False 如果被拒绝。
        """
        # 边界校验
        allowed, reason = self.boundary_rules.is_update_allowed(contract)
        if not allowed:
            return False

        # 组件校验: identity_ref 不可写
        if component == "identity_ref":
            return False

        valid_components = {
            "capability_awareness", "knowledge_boundary",
            "experience_profile", "preference_model", "cognitive_state",
        }
        if component not in valid_components:
            return False

        # 执行更新
        setattr(self, component, new_value)
        self.updated_at = datetime.now(timezone.utc)
        self.self_confidence = max(
            self.boundary_rules.self_confidence_bounds[0],
            min(
                self.boundary_rules.self_confidence_bounds[1],
                self.self_confidence + contract.confidence_impact,
            )
        )
        self.update_history.append(contract)
        return True

    @property
    def has_capability_awareness(self) -> bool:
        return self.capability_awareness is not None

    @property
    def has_knowledge_boundary(self) -> bool:
        return self.knowledge_boundary is not None

    @property
    def components_loaded(self) -> int:
        return sum([
            self.capability_awareness is not None,
            self.knowledge_boundary is not None,
            self.experience_profile is not None,
            self.preference_model is not None,
            self.cognitive_state is not None,
        ])


# ── 禁止导出 ──

__all__ = [
    "SelfUpdateSource",
    "SelfUpdateContract",
    "SelfBoundaryRules",
    "KnowledgeConfidence",
    "CapabilityStatement",
    "DomainStatement",
    "ExperiencePattern",
    "PreferenceType",
    "PreferenceEntry",
    "SelfModel",
]
