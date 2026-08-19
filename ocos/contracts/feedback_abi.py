"""Phase 37: CognitiveFeedback ABI — Adaptive Cognitive Feedback Loop protocol.

Freeze v0.2 §1: 执行后的统一反馈结构。

层级:
  CognitiveFeedback   — 一条完整的认知反馈（frozen）
  ├── ExpectedOutcome  — 决策时的预测
  ├── ActualOutcome    — 执行后的实际结果
  ├── OutcomeEvaluation — 五维评估结果（来自 OutcomeEvaluator）
  └── LearningSignal   — 可安全写入经验层的信号

规则:
  - frozen=True, 一旦生成不可变
  - 必须经过 Validator → Evaluator → Feedback 链
  - 禁止 AgentResult → 直接 Feedback
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# §1.1 核心类型
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExpectedOutcome:
    """决策时的预测结果。"""

    predicted_success_prob: float = 0.5     # 0.0 ~ 1.0
    estimated_duration_ms: float = 0.0
    estimated_quality: float = 0.5          # 0.0 ~ 1.0
    prediction_confidence: float = 0.5       # 预测置信度


@dataclass(frozen=True)
class ActualOutcome:
    """执行后的实际结果 — 来自 StructuredResult 的验证后数据。"""

    success: bool
    quality_score: float               # 0.0 ~ 1.0
    duration_ms: float
    user_alignment: float              # 0.0 ~ 1.0


class EvaluationStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REJECTED_USER_MISALIGNED = "rejected_user_misaligned"


@dataclass(frozen=True)
class OutcomeEvaluation:
    """§2 五维评估结果。"""

    score: float = 0.0                 # 0.0 ~ 1.0, 加权评分
    status: EvaluationStatus = EvaluationStatus.ACCEPTED
    reason: str = ""

    # 五维分项（用于审计）
    s_score: float = 0.0               # Success
    q_score: float = 0.0               # Quality
    e_score: float = 0.0               # Efficiency
    r_score: float = 0.0               # Reliability
    a_score: float = 0.0               # User Alignment


@dataclass(frozen=True)
class LearningSignal:
    """可安全写入经验层的信号 — 不含任何系统自我修改指令。"""

    calibration_delta: float = 0.0     # 预测偏差（正值=乐观、负值=悲观）
    reliability_update: float = 0.0    # 能力/Provider 可靠性调整建议
    new_pattern_candidate: bool = False
    pattern_confidence: float = 0.0
    attention_hint: str = ""           # 给 Attention 层的提示（可选）


class FeedbackState(str, Enum):
    """§13: Feedback 生命周期状态。"""
    TEMPORARY = "temporary"
    CONFIRMED = "confirmed"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class CognitiveFeedback:
    """一次认知决策的完整反馈 — frozen, 不可被后续步骤篡改。

    §1.4 追溯性要求:
      - feedback_id: 唯一标识
      - source_result_id: 原始 ProcessedResult ID
      - evaluator_version: OutcomeEvaluator 版本号
    """

    feedback_id: str
    source_result_id: str              # §1.4: 追溯原始结果
    evaluator_version: str             # §1.4: 评估模型版本

    # ── 关联 ──
    trace_id: str = ""
    goal_id: str = ""
    execution_id: str = ""
    capability_id: str = ""
    provider_id: str = ""

    # ── 预测 vs 实际 ──
    expected: ExpectedOutcome = field(default_factory=lambda: ExpectedOutcome(
        predicted_success_prob=0.5, estimated_duration_ms=0.0, estimated_quality=0.5,
    ))
    actual: ActualOutcome = field(default_factory=lambda: ActualOutcome(
        success=False, quality_score=0.0, duration_ms=0.0, user_alignment=0.5,
    ))

    # ── 评估 ──
    evaluation: OutcomeEvaluation = field(default_factory=lambda: OutcomeEvaluation())

    # ── 学习信号 ──
    learning_signal: LearningSignal = field(default_factory=LearningSignal)

    # ── §13 生命周期 ──
    state: FeedbackState = FeedbackState.TEMPORARY
    calibration_samples: int = 0       # §3.4: 该 capability/provider 累计样本数

    timestamp: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════
# §5.4 Evidence — Feedback 到 Belief 的中间层
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class Evidence:
    """来自 Feedback 的证据片段 — 必须在 Evidence Pool 中累积后才影响 Belief。"""

    source_feedback_id: str
    statement: str                     # "Agent A 在 backend_design 上成功率 85%"
    confidence: float                  # 证据置信度
    sample_count: int = 1              # 证据来源的样本数
    created_at: float = field(default_factory=time.time)

    def merge(self, other: "Evidence") -> "Evidence":
        """合并两条同类证据，增加样本数，加权平均置信度。"""
        total = self.sample_count + other.sample_count
        merged_confidence = (
            self.confidence * self.sample_count + other.confidence * other.sample_count
        ) / total
        return Evidence(
            source_feedback_id=f"{self.source_feedback_id},{other.source_feedback_id}",
            statement=self.statement,
            confidence=merged_confidence,
            sample_count=total,
        )


# ══════════════════════════════════════════════════════════════════════════════
# §6 DriftAlert
# ══════════════════════════════════════════════════════════════════════════════


class DriftSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DriftType(str, Enum):
    GOAL = "goal"
    CAPABILITY = "capability"
    PREFERENCE = "preference"
    CONFIDENCE = "confidence"


@dataclass(frozen=True)
class DriftAlert:
    """§6: 认知漂移报警 — 只读，不触发自动修正。"""

    drift_type: DriftType
    severity: DriftSeverity
    metric: str                        # 触发指标名
    current_value: float
    threshold: float
    description: str = ""
    timestamp: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════════════════
# §4.4 Mutation Budget
# ══════════════════════════════════════════════════════════════════════════════

# 自适应参数：允许和禁止的键集合
ADAPTIVE_PARAM_KEYS = frozenset({
    "capability_reliability",
    "execution_cost_estimate",
    "attention_relevance_weight",
    "retrieval_ranking",
    "planning_confidence_threshold",
})

IMMUTABLE_PARAM_KEYS = frozenset({
    "constitution",
    "identity",
    "permission",
    "goal_ownership",
    "user_preference_authority",
})

# 自适应参数限制
MAX_SINGLE_STEP_DELTA = 0.1
MAX_DAILY_MUTATION_BUDGET = 0.2
CALIBRATION_MIN_SAMPLES = 5           # §3.4: 最小校准样本数
USER_ALIGNMENT_REJECT_THRESHOLD = 0.3  # §2.3: User Alignment 拒绝阈值
