"""Phase 24.2-A — Significance 评分规则。

四个维度的评分函数 + 权重配置 + 阈值默认值。

核心原则:
    "重要" ≠ "有情绪"
    OCOS Memory 的核心单位是 Behavior-changing Experience
    而不是 Interesting Event
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ocos.memory.experience.models import ExperienceCandidate, ExperienceStatus


# ── 默认配置 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SignificanceConfig:
    """Significance Gate 配置。

    权重总和 = 1.0。
    阈值: weighted_total >= threshold → PASS。
    """

    # 维度权重
    goal_impact_weight: float = 0.25
    prediction_error_weight: float = 0.30
    knowledge_change_weight: float = 0.20
    future_relevance_weight: float = 0.25

    # 判定阈值
    threshold: float = 0.5

    def __post_init__(self) -> None:
        total = (
            self.goal_impact_weight
            + self.prediction_error_weight
            + self.knowledge_change_weight
            + self.future_relevance_weight
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Weight sum must be 1.0, got {total}"
            )


# ── 维度 1: Goal Impact ──────────────────────────────────────────────────────


def score_goal_impact(
    candidate: ExperienceCandidate,
    active_goals: Optional[list[str]] = None,
) -> tuple[float, list[str]]:
    """评估经历是否与活跃 Goal 相关。

    规则:
      - goal_context 中有活跃 goal id → 1.0
      - context 中有关键词命中 → 0.6
      - 观察中存在 goal-like 结构 → 0.3
      - 无关 → 0.0
    """
    evidence: list[str] = []
    ctx = candidate.context or {}
    goal_ctx = (
        candidate.trace_bundle.goal_context or {}
    )

    if active_goals is None:
        active_goals = []

    # 直接 Goal ID 匹配
    goal_id = goal_ctx.get("goal_id") or ctx.get("goal_id")
    if goal_id and goal_id in active_goals:
        return (1.0, [f"matched active goal '{goal_id}'"])

    # goal_context 非空 → 有 Goal 关联
    if goal_ctx:
        evidence.append("goal_context present")
        return (0.8, evidence)

    # context 中有 goal 关键词
    goal_keywords = ctx.get("goal_keywords", [])
    if goal_keywords:
        evidence.append(f"goal keywords: {goal_keywords}")


    # observation 中有 goal-like 结构
    obs = candidate.trace_bundle.observation
    if isinstance(obs, dict) and obs.get("goal"):
        return (0.6, evidence + ["observation contains goal field"])

    # 无 Goal 关联
    return (0.0, ["no goal association found"])


# ── 维度 2: Prediction Error ─────────────────────────────────────────────────


def score_prediction_error(
    candidate: ExperienceCandidate,
    expected_outcome: Optional[dict] = None,
) -> tuple[float, list[str]]:
    """评估结果与预期的偏差程度。

    规则:
      - 结果标记 failure/error → 0.8
      - 结果与预期不匹配 → 0.7
      - 结果有意外成分 (surprise field) → 0.5
      - 正常执行 → 0.0
    """
    evidence: list[str] = []
    outcome = candidate.trace_bundle.outcome

    # 失败/错误
    if isinstance(outcome, dict):
        success = outcome.get("success", True)
        error = outcome.get("error")
        if error or not success:
            evidence.append(f"failure detected: {error or 'unsuccessful'}")
            return (0.8, evidence)

    # 与预期不匹配
    if expected_outcome and isinstance(outcome, dict):
        mismatches = []
        for key, expected_val in expected_outcome.items():
            actual_val = outcome.get(key)
            if actual_val != expected_val:
                mismatches.append(f"{key}: expected={expected_val}, got={actual_val}")
        if mismatches:
            evidence.extend(mismatches)
            return (0.7, evidence)

    # 有意外标记
    if isinstance(outcome, dict) and outcome.get("surprise"):
        evidence.append(f"surprise: {outcome['surprise']}")
        return (0.5, evidence)

    return (0.0, ["outcome matches expectation"])


# ── 维度 3: Knowledge Change ─────────────────────────────────────────────────


def score_knowledge_change(
    candidate: ExperienceCandidate,
) -> tuple[float, list[str]]:
    """评估是否产生了新知识。

    规则:
      - outcome 中有 new_knowledge / learned → 0.9
      - 多次失败 (pattern 信号) → 0.7
      - 有 Reflection 追踪 → 0.5
      - 无 → 0.0
    """
    evidence: list[str] = []
    outcome = candidate.trace_bundle.outcome

    if isinstance(outcome, dict):
        if outcome.get("new_knowledge") or outcome.get("learned"):
            evidence.append("outcome contains new_knowledge/learned")
            return (0.9, evidence)

        # 错误中包含可学习的信号
        if outcome.get("error"):
            evidence.append("error signal present → potential learning")
            return (0.7, evidence)

    # Reflection 存在 → 有内省，可能有知识沉淀
    if candidate.trace_bundle.reflection_trace_id:
        evidence.append("reflection present → introspection signal")
        return (0.5, evidence)

    return (0.0, ["no knowledge change signal"])


# ── 维度 4: Future Relevance ─────────────────────────────────────────────────


def score_future_relevance(
    candidate: ExperienceCandidate,
) -> tuple[float, list[str]]:
    """评估是否可能影响未来决策。

    规则:
      - context 标记为 high_priority → 1.0
      - 来源为 REFLECTION / ANOMALY → 0.7
      - 来源为 DECISION → 0.4
      - GOAL_COMPLETION → 0.3
      - 无上下文 → 0.1
    """
    evidence: list[str] = []
    ctx = candidate.context or {}

    # 高优先级标记
    if ctx.get("high_priority") or ctx.get("critical"):
        evidence.append("high_priority/critical mark")
        return (1.0, evidence)

    # Source 权重
    from ocos.memory.experience.models import ExperienceSource

    source_weights = {
        ExperienceSource.DECISION:       (0.4, "decision → routine"),
        ExperienceSource.REFLECTION:     (0.7, "reflection → introspective"),
        ExperienceSource.ANOMALY:        (0.7, "anomaly → unexpected/novel"),
        ExperienceSource.GOAL_COMPLETION: (0.3, "goal completion → archive"),
    }

    weight, desc = source_weights.get(
        candidate.source,
        (0.1, "unknown source → low relevance"),
    )
    evidence.append(desc)
    return (weight, evidence)
