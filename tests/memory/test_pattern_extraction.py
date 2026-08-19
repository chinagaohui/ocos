"""Phase 24.3-A — Gate Tests: Pattern Extraction。

验证:
  24.3-A-01: 多 Episode 可生成 PatternCandidate (n >= 3)
  24.3-A-02: 少于阈值不能生成 Pattern (n < 3)
  24.3-A-03: 高 prediction_error 单次事件允许候选
  24.3-A-04: 必须存在条件→结果关系 (trigger + observed_relation)
  24.3-A-05: Pattern 不引用 Episode ID (abstraction)
  24.3-A-06: Pattern 不含 Self 字段 (schema)
  24.3-A-07: Validator 拦截 Self 语义
  24.3-A-08: Episode → Pattern 单向流 (frozen PatternCandidate)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.pattern.models import PatternCandidate, Pattern, PatternStatus
from ocos.memory.pattern.validator import PatternValidator
from ocos.memory.pattern.extractor import PatternExtractor


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_episode(
    exp_id: str,
    condition: str = "cpu>80%",
    decision: str = "strategy_a",
    outcome: dict | None = None,
    significance: float = 0.8,
    trace_dims: dict | None = None,
) -> Episode:
    """快速构建 Episode。"""
    return Episode.from_candidate(
        experience_id=exp_id,
        context={},
        goal="g-critical",
        decision=decision,
        action="execute",
        outcome=outcome or {"success": False, "error": "timeout"},
        condition=condition,
        significance_score=significance,
        evaluation_trace={"dimensions": trace_dims or {"prediction_error": 0.85}, "verdict": "PASS"},
    )


# ── 24.3-A-01: 多 Episode → PatternCandidate ────────────────────────────────


def test_multiple_episodes_generate_pattern() -> None:
    """3+ Episode 共享 condition+outcome 应生成 PatternCandidate。"""
    episodes = [
        _make_episode("EXP-001", "cpu>80%", "strategy_a", {"success": False, "error": "timeout"}),
        _make_episode("EXP-002", "cpu>80%", "strategy_a", {"success": False, "error": "timeout"}),
        _make_episode("EXP-003", "cpu>80%", "strategy_a", {"success": False, "error": "timeout"}),
    ]

    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)

    assert len(candidates) >= 1
    c = candidates[0]
    assert c.supporting_episode_count >= 3
    assert "cpu" in c.trigger_condition.lower()
    assert "timeout" in c.observed_relation.lower()
    assert c.source == "episode_aggregation"


# ── 24.3-A-02: < 3 Episode → 不生成 ─────────────────────────────────────────


def test_insufficient_samples_no_pattern() -> None:
    """少于 3 个 Episode 共享 condition → 不生成聚合 PatternCandidate。"""
    episodes = [
        _make_episode("EXP-001", "cpu>80%", significance=0.3, trace_dims={"prediction_error": 0.1}),
        _make_episode("EXP-002", "cpu>80%", significance=0.3, trace_dims={"prediction_error": 0.1}),
        # 只有 2 个，且 significance+pred_error 低，不触发 anomaly
    ]

    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)

    assert len(candidates) == 0  # 聚合不足 + 异常不触发


# ── 24.3-A-03: 高 prediction_error 单事件 ────────────────────────────────────


def test_single_anomaly_candidate() -> None:
    """prediction_error > 0.8 的单次事件 → 生成 anomaly PatternCandidate。"""
    episodes = [
        _make_episode(
            "EXP-001",
            condition="unusual_state",
            significance=0.9,
            trace_dims={"prediction_error": 0.92},
        ),
    ]

    extractor = PatternExtractor(min_samples=3, single_event_threshold=0.8)
    candidates = extractor.extract(episodes)

    assert len(candidates) >= 1
    c = candidates[0]
    assert c.source == "single_anomaly"
    assert c.supporting_episode_count == 1


def test_low_prediction_error_no_single_candidate() -> None:
    """prediction_error < 0.8 的单次事件 → 不生成 anomaly PatternCandidate。"""
    episodes = [
        _make_episode(
            "EXP-001",
            significance=0.5,
            trace_dims={"prediction_error": 0.3},
        ),
    ]

    extractor = PatternExtractor(min_samples=3, single_event_threshold=0.8)
    candidates = extractor.extract(episodes)

    # 聚合和无异常都无结果
    assert all(c.source != "single_anomaly" for c in candidates) or len(candidates) == 0


# ── 24.3-A-04: 条件→结果关系 ────────────────────────────────────────────────


def test_validator_requires_causality() -> None:
    """trigger_condition 为空 → validator 拒绝。"""
    candidate = PatternCandidate.create(
        trigger_condition="",       # 空!
        observed_relation="timeout",
        causal_explanation="...",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert PatternStatus.REJECTED == status
    assert any("trigger_condition" in v for v in violations)


def test_validator_requires_observed_relation() -> None:
    """observed_relation 为空 → validator 拒绝。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="",       # 空!
        causal_explanation="...",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert any("observed_relation" in v for v in violations)


# ── 24.3-A-05: 不引用 Episode ID ─────────────────────────────────────────────


def test_validator_rejects_episode_id() -> None:
    """Pattern 包含 Episode ID → validator 拒绝。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80% from EPI-20260723-ABC12345",
        observed_relation="timeout",
        causal_explanation="source: EPI-20260723-ABC12345",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert PatternStatus.REJECTED == status
    assert any("Episode ID" in v for v in violations)


# ── 24.3-A-06: 无 Self 字段 ──────────────────────────────────────────────────


def test_pattern_candidate_no_self_fields() -> None:
    """PatternCandidate 的字段名不含 Self 相关词。"""
    from dataclasses import fields as dc_fields
    field_names = {f.name for f in dc_fields(PatternCandidate)}
    forbidden = {"self", "identity", "personality", "persona", "value", "mission", "owner"}
    overlap = field_names & forbidden
    assert len(overlap) == 0, f"PatternCandidate has forbidden fields: {overlap}"


# ── 24.3-A-07: Validator 拦截 Self 语义 ──────────────────────────────────────


def test_validator_rejects_first_person() -> None:
    """Pattern 包含 "I am" → validator 拒绝。"""
    candidate = PatternCandidate.create(
        trigger_condition="I am running slow",
        observed_relation="timeout",
        causal_explanation="Because I am a slow system",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert PatternStatus.REJECTED == status


def test_validator_rejects_identity_attribution() -> None:
    """Pattern 包含身份归因 "是一个" → validator 拒绝。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="timeout",
        causal_explanation="这表明我是一个不擅长并发的系统",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert PatternStatus.REJECTED == status


def test_validator_rejects_belief_language() -> None:
    """Pattern 包含 "应该" → validator 拒绝 (属于 Belief, 非 Knowledge)。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="timeout",
        causal_explanation="系统应该始终避免高负载",
        confidence=0.8,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert not passed
    assert PatternStatus.REJECTED == status


def test_validator_accepts_clean_pattern() -> None:
    """干净的 Pattern 应通过 Validator。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="请求超时概率增加",
        causal_explanation="高 CPU 负载导致请求队列堆积，延迟增加导致超时",
        confidence=0.85,
        supporting_episode_count=3,
    )

    passed, violations, status = PatternValidator.validate(candidate)
    assert passed
    assert PatternStatus.VALIDATED == status
    assert len(violations) == 0


# ── 24.3-A-08: Episode → Pattern 单向流 ─────────────────────────────────────


def test_pattern_candidate_is_immutable() -> None:
    """PatternCandidate 是 frozen dataclass。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="timeout",
        causal_explanation="...",
        confidence=0.8,
        supporting_episode_count=3,
    )

    with pytest.raises(Exception):
        candidate.confidence = 0.5  # type: ignore[misc]


def test_pattern_is_immutable() -> None:
    """Pattern 是 frozen dataclass。"""
    candidate = PatternCandidate.create(
        trigger_condition="cpu>80%",
        observed_relation="timeout",
        causal_explanation="...",
        confidence=0.8,
        supporting_episode_count=3,
    )
    pattern = Pattern(candidate=candidate)

    with pytest.raises(Exception):
        pattern.validated_at = None  # type: ignore[misc]


# ── 模型测试 ──────────────────────────────────────────────────────────────────


def test_pattern_candidate_factory() -> None:
    """create() 工厂方法应正确生成 PatternCandidate。"""
    c = PatternCandidate.create(
        trigger_condition="mem<10%",
        observed_relation="OOM 概率上升",
        causal_explanation="内存不足导致分配失败",
        confidence=0.75,
        supporting_episode_count=5,
    )

    assert c.id.startswith("PAT-")
    assert c.trigger_condition == "mem<10%"
    assert c.confidence == 0.75
    assert c.supporting_episode_count == 5
    assert c.status == PatternStatus.CANDIDATE
    assert not c.is_validated
    assert not c.is_rejected
    assert "PAT-" in c.summary()
    assert "mem<10%" in c.summary()


def test_pattern_wrapping() -> None:
    """Pattern 应正确包装 PatternCandidate。"""
    candidate = PatternCandidate.create(
        trigger_condition="disk>90%",
        observed_relation="写入延迟增加",
        causal_explanation="磁盘已满",
        confidence=0.9,
        supporting_episode_count=3,
    )
    pattern = Pattern(candidate=candidate)

    assert pattern.id == candidate.id
    assert pattern.trigger_condition == candidate.trigger_condition
    assert pattern.observed_relation == candidate.observed_relation
    assert pattern.confidence == candidate.confidence
    assert "[validated]" in pattern.summary()


# ── 边界案例 ──────────────────────────────────────────────────────────────────


def test_extractor_empty_input() -> None:
    """空列表输入 → 空输出。"""
    extractor = PatternExtractor()
    assert extractor.extract([]) == []


def test_extractor_varied_outcomes() -> None:
    """不同 outcome 不应被聚合到一起。"""
    episodes = [
        _make_episode("EXP-001", "cpu>80%", outcome={"success": False, "error": "timeout"}),
        _make_episode("EXP-002", "cpu>80%", outcome={"success": True}),
        _make_episode("EXP-003", "cpu>80%", outcome={"success": False, "error": "timeout"}),
        _make_episode("EXP-004", "cpu>80%", outcome={"success": False, "error": "timeout"}),
    ]

    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)

    # timeout outcome 有 3 个, success 只有 1 个
    timeout_candidates = [c for c in candidates if "timeout" in c.observed_relation]
    assert len(timeout_candidates) >= 1
    assert timeout_candidates[0].supporting_episode_count == 3


def test_extractor_empty_condition_excluded() -> None:
    """condition 为空的 Episode 不被聚合。"""
    episodes = [
        _make_episode("EXP-001", condition=""),
        _make_episode("EXP-002", condition=""),
        _make_episode("EXP-003", condition=""),
    ]

    extractor = PatternExtractor(min_samples=3)
    candidates = extractor.extract(episodes)

    # 空 condition 应被跳过 (normalize 返回 "")
    assert all(c.trigger_condition != "" for c in candidates)
