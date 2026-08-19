"""Phase 24.2-A — Significance Gate Tests。

验证:
  24.2-01: 低价值经历 → FAIL
  24.2-02: 高价值经历 → PASS (失败+Goal关联+Reflection)
  24.2-03: INCOMPLETE → 自动 FAIL (不评估)
  24.2-04: 可配置阈值
  24.2-05: 四维度独立计算
  24.2-06: 批量评估
  24.2-07: Passed/Failed 过滤
  24.2-08: Decision 历史可检索
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.experience.models import (
    TraceBundle,
    ExperienceCandidate,
    ExperienceStatus,
    ExperienceSource,
)
from ocos.memory.experience.builder import ExperienceBuilder
from ocos.memory.significance.models import (
    SignificanceScore,
    DimensionScore,
    GateDecision,
    GateVerdict,
)
from ocos.memory.significance.rules import (
    SignificanceConfig,
    score_goal_impact,
    score_prediction_error,
    score_knowledge_change,
    score_future_relevance,
)
from ocos.memory.significance.evaluator import SignificanceEvaluator


# ── Helpers ──────────────────────────────────────────────────────────────────


def _complete_candidate(
    outcome: dict | None = None,
    context: dict | None = None,
    source: ExperienceSource = ExperienceSource.DECISION,
    goal_context: dict | None = None,
    reflection_trace_id: str | None = None,
) -> ExperienceCandidate:
    """创建 COMPLETE ExperienceCandidate。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed"},
        outcome=outcome or {"success": True},
        reflection_trace_id=reflection_trace_id,
        goal_context=goal_context,
    )
    builder = ExperienceBuilder()
    return builder.build(bundle, source, context or {})


def _failure_candidate() -> ExperienceCandidate:
    """高价值: 失败 + Goal 关联 + Reflection。"""
    return _complete_candidate(
        outcome={"success": False, "error": "ResourceExhausted"},
        context={"goal_id": "g1"},
        goal_context={"goal_id": "g1"},
        source=ExperienceSource.ANOMALY,
        reflection_trace_id="refl-001",
    )


# ── 24.2-01: 低价值 → FAIL ────────────────────────────────────────────────────


def test_low_significance_fails() -> None:
    """普通成功执行，无 Goal 关联，无 Reflection。"""
    candidate = _complete_candidate(
        outcome={"success": True},
    )
    evaluator = SignificanceEvaluator()
    decision = evaluator.evaluate(candidate)

    assert decision.verdict == GateVerdict.FAIL
    assert decision.score.weighted_total < 0.5


# ── 24.2-02: 高价值 → PASS ────────────────────────────────────────────────────


def test_high_significance_passes() -> None:
    """失败 + Goal 关联 + Reflection → PASS。"""
    candidate = _failure_candidate()
    evaluator = SignificanceEvaluator(
        active_goals=["g1"],
    )
    decision = evaluator.evaluate(candidate)

    assert decision.verdict == GateVerdict.PASS


def test_high_significance_score_breakdown() -> None:
    """验证高价值经历的四个维度都有非零分。"""
    candidate = _failure_candidate()
    evaluator = SignificanceEvaluator(active_goals=["g1"])
    decision = evaluator.evaluate(candidate)

    score = decision.score
    assert score.goal_impact.raw_score > 0.5, "Goal match should score high"
    assert score.prediction_error.raw_score > 0.5, "Failure should score high"
    assert score.knowledge_change.raw_score > 0.5, "Reflection+error should score"
    assert score.future_relevance.raw_score > 0.3, "Anomaly should be relevant"


# ── 24.2-03: INCOMPLETE → 自动 FAIL ──────────────────────────────────────────


def test_incomplete_auto_fails() -> None:
    """INCOMPLETE Candidate 不应进入评估，直接 FAIL。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="",  # missing
        action_result={"status": "done"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate.status == ExperienceStatus.INCOMPLETE

    evaluator = SignificanceEvaluator()
    decision = evaluator.evaluate(candidate)

    assert decision.verdict == GateVerdict.FAIL
    assert "INCOMPLETE" in decision.reason


# ── 24.2-04: 可配置阈值 ───────────────────────────────────────────────────────


def test_configurable_threshold_low() -> None:
    """低阈值: 即使普通经历也能 PASS。"""
    candidate = _complete_candidate(outcome={"success": True})
    # 降低阈值到 0.05 — 几乎所有经历都能通过
    config = SignificanceConfig(threshold=0.05)
    evaluator = SignificanceEvaluator(config=config)
    decision = evaluator.evaluate(candidate)

    assert decision.verdict == GateVerdict.PASS


def test_configurable_threshold_high() -> None:
    """高阈值: 大多数经历被拒绝。"""
    candidate = _complete_candidate(
        outcome={"success": True},
        context={"goal_id": "g1"},
        goal_context={"goal_id": "g1"},
    )
    # 提高阈值到 0.9
    config = SignificanceConfig(threshold=0.9)
    evaluator = SignificanceEvaluator(config=config, active_goals=["g1"])
    decision = evaluator.evaluate(candidate)

    assert decision.verdict == GateVerdict.FAIL


def test_configurable_weights() -> None:
    """自定义权重应被正确应用。"""
    candidate = _complete_candidate(outcome={"success": True})
    # Goal Impact 权重提高到 0.7 — 即使没有 Goal，总分也低
    config = SignificanceConfig(
        goal_impact_weight=0.7,
        prediction_error_weight=0.1,
        knowledge_change_weight=0.1,
        future_relevance_weight=0.1,
    )
    evaluator = SignificanceEvaluator(config=config)
    decision = evaluator.evaluate(candidate)
    # 没有任何高价值信号 → FAIL
    assert decision.verdict == GateVerdict.FAIL


# ── 24.2-05: 四维度独立计算 ───────────────────────────────────────────────────


def test_dimension_goal_impact() -> None:
    """Goal Impact: 匹配活跃 Goal → 高分。"""
    candidate = _complete_candidate(
        goal_context={"goal_id": "g1"},
        context={"goal_id": "g1"},
    )
    score, evidence = score_goal_impact(candidate, active_goals=["g1"])
    assert score == 1.0
    assert any("g1" in e for e in evidence)


def test_dimension_goal_impact_no_match() -> None:
    """Goal Impact: 无关联 → 0。"""
    candidate = _complete_candidate()
    score, _ = score_goal_impact(candidate, active_goals=["g1"])
    assert score == 0.0


def test_dimension_prediction_error() -> None:
    """Prediction Error: 失败 → 高分。"""
    candidate = _complete_candidate(outcome={"success": False, "error": "timeout"})
    score, evidence = score_prediction_error(candidate)
    assert score >= 0.7
    assert any("failure" in e for e in evidence)


def test_dimension_prediction_error_match() -> None:
    """Prediction Error: 正常 → 0。"""
    candidate = _complete_candidate(outcome={"success": True})
    score, _ = score_prediction_error(candidate)
    assert score == 0.0


def test_dimension_prediction_error_mismatch() -> None:
    """Prediction Error: 与预期不匹配 → 中等分数。"""
    candidate = _complete_candidate(
        outcome={"success": True, "duration": 50}
    )
    score, evidence = score_prediction_error(
        candidate, expected_outcome={"duration": 10}
    )
    assert score >= 0.5
    assert len(evidence) > 0


def test_dimension_knowledge_change() -> None:
    """Knowledge Change: 有 new_knowledge → 高分。"""
    candidate = _complete_candidate(
        outcome={"success": True, "new_knowledge": "Strategy X fails on GPU"}
    )
    score, _ = score_knowledge_change(candidate)
    assert score >= 0.8


def test_dimension_knowledge_change_reflection() -> None:
    """Knowledge Change: 有 Reflection → 中等。"""
    candidate = _complete_candidate(
        outcome={"success": True},
        reflection_trace_id="refl-001",
    )
    score, _ = score_knowledge_change(candidate)
    assert score >= 0.4


def test_dimension_future_relevance_anomaly() -> None:
    """Future Relevance: ANOMALY → 高分。"""
    candidate = _complete_candidate(
        source=ExperienceSource.ANOMALY,
    )
    score, _ = score_future_relevance(candidate)
    assert score >= 0.6


# ── 24.2-06: 批量评估 ────────────────────────────────────────────────────────


def test_batch_evaluation() -> None:
    """批量评估应正确处理所有 Candidate。"""
    c1 = _complete_candidate(outcome={"success": True})
    c2 = _failure_candidate()

    evaluator = SignificanceEvaluator(active_goals=["g1"])
    decisions = evaluator.evaluate_all([c1, c2])

    assert len(decisions) == 2
    assert decisions[0].candidate_id == c1.id
    assert decisions[1].candidate_id == c2.id


# ── 24.2-07: Passed/Failed 过滤 ──────────────────────────────────────────────


def test_passed_failed_filter() -> None:
    """get_passed() / get_failed() 应正确过滤。"""
    c_low = _complete_candidate(outcome={"success": True})
    c_high = _failure_candidate()

    evaluator = SignificanceEvaluator(active_goals=["g1"])
    evaluator.evaluate_all([c_low, c_high])

    assert len(evaluator.get_passed()) == 1
    assert evaluator.get_passed()[0].candidate_id == c_high.id
    assert len(evaluator.get_failed()) == 1
    assert evaluator.get_failed()[0].candidate_id == c_low.id


# ── 24.2-08: Decision 历史可检索 ─────────────────────────────────────────────


def test_decision_retrievable() -> None:
    """历史 Decision 应可通过 candidate_id 检索。"""
    candidate = _failure_candidate()
    evaluator = SignificanceEvaluator(active_goals=["g1"])
    evaluator.evaluate(candidate)

    retrieved = evaluator.get_by_candidate_id(candidate.id)
    assert retrieved is not None
    assert retrieved.candidate_id == candidate.id
    assert retrieved.passed()


def test_clear_decisions() -> None:
    """clear() 应清空历史。"""
    candidate = _complete_candidate()
    evaluator = SignificanceEvaluator()
    evaluator.evaluate(candidate)

    assert len(evaluator._decisions) == 1
    evaluator.clear()
    assert len(evaluator._decisions) == 0


def test_get_by_id_returns_none_for_unknown() -> None:
    """检索不存在的 ID 返回 None。"""
    evaluator = SignificanceEvaluator()
    assert evaluator.get_by_candidate_id("nonexistent") is None


# ── 模型测试 ──────────────────────────────────────────────────────────────────


def test_significance_score_all_evidence() -> None:
    """all_evidence() 应收集所有维度证据。"""
    score = SignificanceScore(
        goal_impact=DimensionScore("goal_impact", 1.0, 0.25, ["g1 match"]),
        prediction_error=DimensionScore("prediction_error", 0.8, 0.30, ["failure"]),
        knowledge_change=DimensionScore("knowledge_change", 0.0, 0.20, ["none"]),
        future_relevance=DimensionScore("future_relevance", 0.7, 0.25, ["anomaly"]),
    )
    evidence = score.all_evidence()
    assert "g1 match" in evidence
    assert "failure" in evidence
    assert "anomaly" in evidence


def test_significance_score_weighted_total() -> None:
    """加权总分计算正确。"""
    score = SignificanceScore(
        goal_impact=DimensionScore("goal_impact", 1.0, 0.25, []),
        prediction_error=DimensionScore("prediction_error", 0.5, 0.30, []),
        knowledge_change=DimensionScore("knowledge_change", 0.0, 0.20, []),
        future_relevance=DimensionScore("future_relevance", 0.0, 0.25, []),
    )
    expected = 1.0 * 0.25 + 0.5 * 0.30 + 0.0 * 0.20 + 0.0 * 0.25  # = 0.40
    assert abs(score.weighted_total - expected) < 0.001


def test_dimension_summary() -> None:
    """dimension_summary() 应返回正确结构。"""
    score = SignificanceScore(
        goal_impact=DimensionScore("goal_impact", 1.0, 0.25, []),
        prediction_error=DimensionScore("prediction_error", 0.0, 0.30, []),
        knowledge_change=DimensionScore("knowledge_change", 0.0, 0.20, []),
        future_relevance=DimensionScore("future_relevance", 0.0, 0.25, []),
    )
    summary = score.dimension_summary()
    assert set(summary.keys()) == {
        "goal_impact", "prediction_error", "knowledge_change", "future_relevance"
    }
    assert summary["goal_impact"] == 0.25


def test_gate_decision_helpers() -> None:
    """GateDecision.passed() / failed() 正确。"""
    score = SignificanceScore(
        goal_impact=DimensionScore("goal_impact", 0.0, 0.25, []),
        prediction_error=DimensionScore("prediction_error", 0.0, 0.30, []),
        knowledge_change=DimensionScore("knowledge_change", 0.0, 0.20, []),
        future_relevance=DimensionScore("future_relevance", 0.0, 0.25, []),
    )
    passed = GateDecision("id-pass", GateVerdict.PASS, score, "good")
    failed = GateDecision("id-fail", GateVerdict.FAIL, score, "bad")

    assert passed.passed() and not passed.failed()
    assert failed.failed() and not failed.passed()


# ── 配置测试 ──────────────────────────────────────────────────────────────────


def test_config_weight_sum_validation() -> None:
    """权重总和不等于 1.0 应报错。"""
    with pytest.raises(ValueError, match="Weight sum"):
        SignificanceConfig(goal_impact_weight=0.5, prediction_error_weight=0.5)


def test_config_default_is_valid() -> None:
    """默认配置应有效。"""
    config = SignificanceConfig()
    # 不抛异常 = 通过
    assert config.threshold == 0.5


# ── 边界案例 ──────────────────────────────────────────────────────────────────


def test_evaluator_with_no_active_goals() -> None:
    """无活跃 Goal 时，Goal Impact 应为 0 → FAIL。"""
    candidate = _complete_candidate(outcome={"success": True})
    evaluator = SignificanceEvaluator(active_goals=[])
    decision = evaluator.evaluate(candidate)

    assert decision.score.goal_impact.raw_score == 0.0


def test_evaluator_empty_candidates() -> None:
    """空列表评估应返回空列表。"""
    evaluator = SignificanceEvaluator()
    decisions = evaluator.evaluate_all([])
    assert decisions == []


def test_high_priority_scores_max() -> None:
    """high_priority 标记 → future_relevance = 1.0。"""
    candidate = _complete_candidate(
        outcome={"success": False, "error": "timeout"},
        context={"high_priority": True},
        source=ExperienceSource.ANOMALY,
    )
    score, evidence = score_future_relevance(candidate)
    assert score == 1.0
    assert any("high_priority" in e for e in evidence)
