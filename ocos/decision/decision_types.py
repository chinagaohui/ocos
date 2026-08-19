"""Phase 43: Decision Types — 个人决策智能核心类型定义。

Decision Intelligence 回答: "在当前情境下，我应该如何选择？"

输入:  Goal + Self Model + Personal Wisdom + World Model + Current Context
输出:  Decision Proposal (不是自动执行)

核心约束:
    D43-01: Decision ≠ Goal       — 分析世界不能产生目标
    D43-02: Decision ≠ Execution  — 必须经过 Capability→Permission→Execution
    D43-03: Wisdom ≠ Rule         — 过去经验形成倾向，不是"永远这样做"

决策流水线:
    Context → Options → Risk Analysis → Value Evaluation → Decision Proposal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 决策请求
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DecisionContext:
    """决策上下文 — 聚合所有输入。

    包含:
        - goal_summary:   当前活跃目标的摘要
        - self_summary:   SelfModel 的关键信息
        - wisdom_hints:   Phase 41 中与此决策相关的智慧
        - world_snapshot: Phase 42 中与此决策相关的世界状态
        - constraints:    显式约束条件
    """

    context_id: str
    goal_summary: str = ""
    self_summary: str = ""
    wisdom_hints: list[str] = field(default_factory=list)
    world_snapshot: str = ""  # 世界模型的相关部分摘要
    constraints: list[str] = field(default_factory=list)
    tick_id: int = 0

    @property
    def is_empty(self) -> bool:
        return not any([
            self.goal_summary, self.self_summary,
            self.wisdom_hints, self.world_snapshot,
        ])


# ═══════════════════════════════════════════════════════════════════════════════
# 决策选项
# ═══════════════════════════════════════════════════════════════════════════════


class OptionType(Enum):
    """选项类型。"""
    DO_NOTHING = "do_nothing"     # 不行动
    DIRECT_ACTION = "direct_action"  # 直接行动
    DELEGATE = "delegate"         # 委派
    INVESTIGATE = "investigate"   # 先调查
    DEFER = "defer"               # 推迟决策


@dataclass(frozen=True)
class DecisionOption:
    """决策选项 — 一个可选的行动路线。

    每个选项有:
        - 描述、置信度
        - 预期影响（预期结果摘要）
        - 关联的风险/价值评估 (risk/value)
        - 来源（生成方式）

    注意: 选项本身不包含执行逻辑，只是结构化描述。
    """

    option_id: str
    description: str
    option_type: OptionType = OptionType.INVESTIGATE
    confidence: float = 0.0  # 对此选项的置信度 [0, 1]
    expected_outcome: str = ""  # 预期结果
    prerequisites: list[str] = field(default_factory=list)  # 前置条件
    risk_score: float = 0.0  # 风险评分 [0, 1]
    value_score: float = 0.0  # 价值评分 [0, 1]
    source: str = "generated"  # generated | wisdom_suggested | user_specified
    evidence: list[str] = field(default_factory=list)  # 支持证据


# ═══════════════════════════════════════════════════════════════════════════════
# 风险
# ═══════════════════════════════════════════════════════════════════════════════


class RiskCategory(Enum):
    OPERATIONAL = "operational"    # 操作风险（执行失败）
    RESOURCE = "resource"          # 资源风险（时间/算力/资金）
    REPUTATIONAL = "reputational"  # 声誉风险
    SECURITY = "security"          # 安全风险
    DEPENDENCY = "dependency"      # 依赖风险（外部系统）
    UNKNOWN = "unknown"            # 未知风险


class RiskLevel(Enum):
    NEGLIGIBLE = "negligible"  # 可忽略
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RiskAssessment:
    """风险评价 — 对一个决策选项的风险分析。"""

    option_id: str
    assessment_id: str
    category: RiskCategory = RiskCategory.OPERATIONAL
    level: RiskLevel = RiskLevel.MEDIUM
    score: float = 0.5  # [0, 1]
    description: str = ""
    mitigation: str = ""  # 缓解措施
    probability: float = 0.5  # 发生概率 [0, 1]


# ═══════════════════════════════════════════════════════════════════════════════
# 价值
# ═══════════════════════════════════════════════════════════════════════════════


class ValueDimension(Enum):
    """价值维度 — 决策评估中的不同价值方向。"""
    EFFICIENCY = "efficiency"      # 效率
    RELIABILITY = "reliability"    # 可靠性
    LEARNING = "learning"          # 学习价值
    ALIGNMENT = "alignment"        # 与用户目标的对齐度
    SAFETY = "safety"              # 安全性
    NOVELTY = "novelty"            # 新颖性/探索价值


@dataclass(frozen=True)
class ValueEvaluation:
    """价值评价 — 对一个决策选项的多维度价值评估。"""

    option_id: str
    evaluation_id: str
    dimensions: dict[ValueDimension, float] = field(default_factory=dict)
    overall_score: float = 0.0  # [0, 1]

    def weighted_score(self, weights: dict[ValueDimension, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        for dim, w in weights.items():
            total += self.dimensions.get(dim, 0.0) * w
            weight_sum += w
        return total / weight_sum if weight_sum else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 决策提案
# ═══════════════════════════════════════════════════════════════════════════════


class DecisionState(Enum):
    DRAFT = "draft"            # 草稿
    ANALYZING = "analyzing"    # 分析中
    PROPOSED = "proposed"      # 已提案（等待审批）
    APPROVED = "approved"      # 已批准（可执行）
    REJECTED = "rejected"      # 已拒绝
    EXECUTED = "executed"      # 已执行
    ARCHIVED = "archived"      # 已归档


@dataclass(frozen=True)
class DecisionProposal:
    """决策提案 — 决策引擎的输出。

    包含:
        - 推荐的选项（ranked）
        - 风险总览
        - 价值总览
        - 决策理由（可追溯）

    约束:
        - 不是自动执行指令（Decision ≠ Execution）
        - 必须在 Permission Gateway 后才能转化为 Action
    """

    proposal_id: str
    context_id: str
    ranked_options: list[DecisionOption] = field(default_factory=list)
    risk_summary: str = ""
    value_summary: str = ""
    rationale: str = ""  # 为什么推荐这个选项
    state: DecisionState = DecisionState.DRAFT
    created_tick: int = 0

    @property
    def recommended(self) -> DecisionOption | None:
        """推荐的最佳选项。"""
        if not self.ranked_options:
            return None
        # 按 value_score - risk_score 排序
        scored = sorted(
            self.ranked_options,
            key=lambda o: o.value_score - o.risk_score,
            reverse=True,
        )
        return scored[0]

    @property
    def is_ready(self) -> bool:
        return self.state == DecisionState.PROPOSED


# ═══════════════════════════════════════════════════════════════════════════════
# 决策追踪
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DecisionTrace:
    """决策追踪记录 — 记录一个决策提案的完整生成过程。

    用于事后审计:
        - 哪些数据被使用了
        - 哪些选项被生成/考虑/淘汰了
        - 风险和价值分析结论
    """

    trace_id: str
    proposal_id: str
    context_snapshot: DecisionContext
    generated_options: list[DecisionOption]
    discarded_options: list[str] = field(default_factory=list)  # 被淘汰的理由
    risk_assessments: list[RiskAssessment] = field(default_factory=list)
    value_evaluations: list[ValueEvaluation] = field(default_factory=list)
    tick_id: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════════════════════
# 聚合结果
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DecisionResult:
    """决策结果 — 包含提案和可选追踪。"""

    proposal: DecisionProposal
    trace: DecisionTrace | None = None

    @property
    def accepted(self) -> bool:
        return self.proposal.state == DecisionState.PROPOSED


__all__ = [
    # 上下文
    "DecisionContext",
    # 选项
    "OptionType",
    "DecisionOption",
    # 风险
    "RiskCategory",
    "RiskLevel",
    "RiskAssessment",
    # 价值
    "ValueDimension",
    "ValueEvaluation",
    # 提案
    "DecisionState",
    "DecisionProposal",
    # 追踪
    "DecisionTrace",
    "DecisionResult",
]
