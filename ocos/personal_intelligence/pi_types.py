"""Phase 48: Personal Intelligence Types — 个人智能成熟度类型系统。

不是增加新器官，而是让 OCOS 成为真正属于某一个人的长期智能。

核心维度:
    - Cognitive Signature: 用户认知特征
    - Consistency: 长期一致性
    - Meta-Cognition: 元认知——"我为什么这样判断？"
    - Goal Coordination: 长期目标协调（不创造目标）
    - Personalization: 个性化适配

核心边界:
    PM48-01: Personalization ≠ Overfitting — 适应用户，不丧失通用能力
    PM48-02: Meta-cognition ≠ Self-doubt — 解释决策，不陷入瘫痪
    PM48-03: Goal Coordination ≠ Goal Creation — 帮助跟踪用户目标，不创造自主目标
    PM48-04: Consistency ≠ Rigidity — 保持身份稳定，同时允许治理下的演化
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 决策偏好
# ═══════════════════════════════════════════════════════════════════════════════


class RiskTolerance(Enum):
    """用户风险承受度。"""
    CONSERVATIVE = "conservative"     # 极低风险
    MODERATE = "moderate"             # 中等风险
    BOLD = "bold"                     # 高风...[truncated]


class ExplanationDepth(Enum):
    """解释深度偏好。"""
    MINIMAL = "minimal"     # 结果即可
    SUMMARY = "summary"     # 简要说明
    DETAILED = "detailed"   # 详细论证
    PEDAGOGICAL = "pedagogical"  # 教学级


class InteractionStyle(Enum):
    """交互风格。"""
    DIRECT = "direct"         # 简洁高效
    COLLABORATIVE = "collaborative"  # 讨论式
    SOCRATIC = "socratic"     # 追问式
    FORMAL = "formal"         # 正式学术


# ═══════════════════════════════════════════════════════════════════════════════
# 用户认知特征 (User Cognitive Signature)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DomainPriority:
    """用户重视的认知领域。"""
    domain: str = ""           # e.g. code, writing, research
    weight: float = 0.0         # [0, 1]
    confidence: float = 0.0     # 对此领域权重的置信度
    observation_count: int = 0  # 基于多少次观察


@dataclass
class CognitiveSignature:
    """用户认知特征——让 OCOS 知道"这是谁的个人智能"。"""

    # 决策特征
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    speed_over_accuracy: float = 0.5       # [0,1] 0=精度优先, 1=速度优先
    preference_for_options: int = 3         # 期望的方案数量

    # 交互特征
    explanation_depth: ExplanationDepth = ExplanationDepth.SUMMARY
    interaction_style: InteractionStyle = InteractionStyle.DIRECT
    formality: float = 0.5                 # [0,1] 0=极简, 1=极其正式

    # 领域优先级
    domain_priorities: list[DomainPriority] = field(default_factory=list)

    # 模式历史——从真实交互中学习的证据
    pattern_confidence: float = 0.0         # 整体特征置信度
    total_observations: int = 0             # 总观察次数
    last_updated_tick: int = 0

    def top_domains(self, n: int = 3) -> list[DomainPriority]:
        """获取权重最高的 N 个领域。"""
        sorted_domains = sorted(
            self.domain_priorities,
            key=lambda d: d.weight * d.confidence,
            reverse=True,
        )
        return sorted_domains[:n]

    def update_confidence(self, new_observations: int) -> None:
        """基于新观察更新置信度。"""
        self.total_observations += new_observations
        # 置信度随观察量增长，上限 0.95 (永远留不确定性)
        self.pattern_confidence = min(0.95, self.total_observations / (self.total_observations + 10))

    @property
    def is_reliable(self) -> bool:
        """特征是否足够可靠。"""
        return self.pattern_confidence > 0.5

    @property
    def summary(self) -> str:
        """可读特征摘要。"""
        return (
            f"Risk={self.risk_tolerance.value}, "
            f"Style={self.interaction_style.value}, "
            f"Depth={self.explanation_depth.value}, "
            f"Confidence={self.pattern_confidence:.2f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 一致性指标
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConsistencyMetrics:
    """长期一致性度量。"""
    identity_stability: float = 1.0     # Identity 稳定性 [0,1]
    memory_health: float = 1.0          # Memory 健康度
    wisdom_accumulation_rate: float = 0.0  # 智慧积累速率
    decision_pattern_stability: float = 1.0  # 决策模式稳定度
    goal_alignment: float = 1.0         # 目标对齐度
    personalization_depth: float = 0.0  # 个性化深度

    @property
    def overall_maturity(self) -> float:
        """综合成熟度分数。"""
        weights = {
            "identity_stability": 0.25,
            "memory_health": 0.15,
            "wisdom_accumulation_rate": 0.10,
            "decision_pattern_stability": 0.20,
            "goal_alignment": 0.15,
            "personalization_depth": 0.15,
        }
        score = (
            self.identity_stability * weights["identity_stability"]
            + self.memory_health * weights["memory_health"]
            + min(1.0, self.wisdom_accumulation_rate) * weights["wisdom_accumulation_rate"]
            + self.decision_pattern_stability * weights["decision_pattern_stability"]
            + self.goal_alignment * weights["goal_alignment"]
            + self.personalization_depth * weights["personalization_depth"]
        )
        return score


# ═══════════════════════════════════════════════════════════════════════════════
# 元认知
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DecisionRationale:
    """决策理由——"我为什么这样判断？" """
    decision_id: str = ""
    tick_id: int = 0
    question: str = ""                      # 面对什么问题
    chosen_option: str = ""                 # 选择了什么
    alternatives_considered: list[str] = field(default_factory=list)  # 考虑过的方案
    evidence_chain: list[str] = field(default_factory=list)           # 证据链
    past_similar_count: int = 0             # 类似决策历史
    confidence: float = 0.0                 # 决策置信度
    learning_from_past: str = ""            # 从过去学到了什么
    signature_influence: str = ""           # 用户特征如何影响
    world_context: str = ""                 # 世界模型当前状态


# ═══════════════════════════════════════════════════════════════════════════════
# 长期目标 (非创建，仅协调)
# ═══════════════════════════════════════════════════════════════════════════════


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


@dataclass
class LongTermGoal:
    """长期目标——由用户设定，OCOS 仅协助跟踪。"""
    goal_id: str = ""
    title: str = ""
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    created_by: str = "user"            # 永远 "user" (PM48-03)
    created_tick: int = 0
    milestones: list[dict] = field(default_factory=list)   # [{title, done}]
    progress: float = 0.0               # [0, 1]
    last_reviewed_tick: int = 0
    notes: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 成熟度等级
# ═══════════════════════════════════════════════════════════════════════════════


class MaturityLevel(Enum):
    """个人智能成熟度等级。"""
    INITIALIZING = "initializing"   # 刚启动，无足够数据
    LEARNING = "learning"           # 正在学习用户模式
    ADAPTING = "adapting"           # 开始适配
    MATURE = "mature"               # 个性化稳定可靠
    DEEPENING = "deepening"         # 持续深化


__all__ = [
    "RiskTolerance",
    "ExplanationDepth",
    "InteractionStyle",
    "DomainPriority",
    "CognitiveSignature",
    "ConsistencyMetrics",
    "DecisionRationale",
    "GoalStatus",
    "LongTermGoal",
    "MaturityLevel",
]
