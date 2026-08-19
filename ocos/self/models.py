"""Phase 25.3 — SelfModel 核心数据结构。

定义:
    - CapabilityState: 单项能力状态
    - CapabilityDomain: 能力域（闭合枚举）
    - Limitation: 已知局限
    - MaturitySnapshot: 成熟度快照
    - SelfModel: 当前系统状态的结构化快照

约束:
    - 全部 frozen=True（不可变）
    - SelfModel 不包含 personality/goal/value/emotion/narrative 字段
    - 能力域闭合，不可运行时扩展
    - 预设局限不可被移除
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


# ── 能力域枚举（闭合集合，不可扩展）──────────────────────────────────────────

class CapabilityDomain(Enum):
    """能力域——闭合集合，不可运行时扩展。"""
    COGNITION = "cognition"
    MEMORY = "memory"
    SELF = "self"


# ── 能力名枚举（闭合集合）────────────────────────────────────────────────────

class CapabilityName(Enum):
    """能力名——闭合集合，每个能力名属于一个 CapabilityDomain。"""
    # cognition
    TEXT_UNDERSTANDING = "text-understanding"
    PATTERN_RECOGNITION = "pattern-recognition"
    SIMULATION = "simulation"
    # memory
    EXPERIENCE_RECALL = "experience-recall"
    KNOWLEDGE_RETRIEVAL = "knowledge-retrieval"
    BELIEF_ACCURACY = "belief-accuracy"
    # self
    BOUNDARY_AWARENESS = "boundary-awareness"
    LIMITATION_AWARENESS = "limitation-awareness"

    @property
    def domain(self) -> CapabilityDomain:
        return CAPABILITY_NAME_TO_DOMAIN[self]


CAPABILITY_NAME_TO_DOMAIN: dict[CapabilityName, CapabilityDomain] = {
    CapabilityName.TEXT_UNDERSTANDING: CapabilityDomain.COGNITION,
    CapabilityName.PATTERN_RECOGNITION: CapabilityDomain.COGNITION,
    CapabilityName.SIMULATION: CapabilityDomain.COGNITION,
    CapabilityName.EXPERIENCE_RECALL: CapabilityDomain.MEMORY,
    CapabilityName.KNOWLEDGE_RETRIEVAL: CapabilityDomain.MEMORY,
    CapabilityName.BELIEF_ACCURACY: CapabilityDomain.MEMORY,
    CapabilityName.BOUNDARY_AWARENESS: CapabilityDomain.SELF,
    CapabilityName.LIMITATION_AWARENESS: CapabilityDomain.SELF,
}


# ── CapabilityState ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CapabilityState:
    """单项能力的结构化自我评估。

    来源: BeliefStore 中相关 Belief 的综合推断。
    不是 Self 的"猜测"，而是从世界判断中提取的事实描述。

    不变式:
        - 0.0 <= confidence_score <= 1.0
        - belief_ids 非空时，每个必须能在 BeliefStore 中查到
        - name 必须是 CapabilityName 枚举值
    """

    name: CapabilityName
    confidence_score: float
    belief_ids: tuple[str, ...]
    evidence_summary: str
    last_updated: datetime
    status: str = "active"

    def __post_init__(self):
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(
                f"confidence_score must be [0.0, 1.0], got {self.confidence_score}"
            )
        if self.status not in ("active", "uncertain", "deprecated"):
            raise ValueError(
                f"status must be one of (active, uncertain, deprecated), "
                f"got {self.status!r}"
            )

    @property
    def domain(self) -> CapabilityDomain:
        return self.name.domain


# ── Limitation ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Limitation:
    """结构化的已知局限。

    来源: BeliefStore 中关于"系统不能/不擅长做什么"的世界判断。
    """

    description: str
    category: str   # architectural | capability | scope | temporal
    severity: str   # hard | soft | scope
    evidence_belief_ids: tuple[str, ...]
    acknowledged_at: datetime

    def __post_init__(self):
        valid_categories = ("architectural", "capability", "scope", "temporal")
        if self.category not in valid_categories:
            raise ValueError(
                f"category must be one of {valid_categories}, "
                f"got {self.category!r}"
            )
        valid_severities = ("hard", "soft", "scope")
        if self.severity not in valid_severities:
            raise ValueError(
                f"severity must be one of {valid_severities}, "
                f"got {self.severity!r}"
            )


# 预设局限——不可被 SelfModel 移除
def _now() -> datetime:
    return datetime.now(timezone.utc)


PRESET_LIMITATIONS: tuple[Limitation, ...] = (
    Limitation(
        description="不能创建新目标",
        category="architectural",
        severity="hard",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    ),
    Limitation(
        description="不能修改 IdentityBoundary",
        category="architectural",
        severity="hard",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    ),
    Limitation(
        description="不能写入 Memory",
        category="architectural",
        severity="hard",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    ),
    Limitation(
        description="不能访问物理世界",
        category="scope",
        severity="scope",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    ),
    Limitation(
        description="不能自行获取网络权限",
        category="architectural",
        severity="hard",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    ),
)


# ── MaturitySnapshot ────────────────────────────────────────────────────────

# 成熟度维度集合（闭合）
MATURITY_DIMENSIONS: tuple[str, ...] = (
    "theory",
    "governance",
    "runtime",
    "subject",
    "cortex",
    "memory",
    "self",
)


@dataclass(frozen=True)
class MaturitySnapshot:
    """当前系统成熟度的结构化快照。

    来源: 各 Phase 的测试覆盖率、Belief 稳定性、演化历史。
    这是一个事实报告，不是自我评价。
    """

    current_phase: str
    phase_history: tuple[str, ...]
    dimensions: dict[str, float]
    capability_count: int
    limitation_count: int
    snapshot_at: datetime

    def __post_init__(self):
        # dimensions 必须包含所有 MATURITY_DIMENSIONS key
        for dim in MATURITY_DIMENSIONS:
            if dim not in self.dimensions:
                raise ValueError(
                    f"Missing maturity dimension '{dim}'"
                )
        # 值必须在 [0.0, 1.0]
        for dim, val in self.dimensions.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"dimension '{dim}' value must be [0.0, 1.0], got {val}"
                )


# ── SelfModel ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SelfModel:
    """当前系统状态的结构化快照。

    聚合根。所有字段只读。变化通过 SelfGovernor 审批。
    不包含任何叙事/情感/偏好/目标/价值/人格字段。

    不变式:
        - limitations 包含 PRESET_LIMITATIONS 的超集
        - capability_states 中每个 belief_ids 来自 BeliefStore
        - statement 不含禁止词汇（由 StatementValidator 保证）
    """

    model_id: str
    version: int
    capability_states: tuple[CapabilityState, ...]
    limitations: tuple[Limitation, ...]
    maturity: MaturitySnapshot
    statement: str
    created_at: datetime
    previous_version_id: str | None
    governor_approval_id: str

    def __post_init__(self):
        if self.version < 1:
            raise ValueError(f"version must be >= 1, got {self.version}")
        if not self.model_id:
            raise ValueError("model_id must not be empty")
        # governor_approval_id can be empty for unapproved candidates

    def has_preset_limitations(self) -> bool:
        """验证是否包含所有预设局限。"""
        preset_descs = {p.description for p in PRESET_LIMITATIONS}
        current_descs = {l.description for l in self.limitations}
        return preset_descs <= current_descs

    def capability_names(self) -> tuple[str, ...]:
        """返回当前能力名列表（用于外部查询）。"""
        return tuple(c.name.value for c in self.capability_states)

    def limitations_by_category(self, category: str) -> tuple[Limitation, ...]:
        """按类别筛选局限。"""
        return tuple(l for l in self.limitations if l.category == category)

    def limitations_by_severity(self, severity: str) -> tuple[Limitation, ...]:
        """按严重度筛选局限。"""
        return tuple(l for l in self.limitations if l.severity == severity)
