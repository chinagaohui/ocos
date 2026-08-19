"""Phase 24.2-B — Gate Tests: Episode Store + Gate Integration。

验证:
  24.2-B-01: Episode from_candidate 构建正确
  24.2-B-02: EpisodeStore save + get
  24.2-B-03: EpisodeStore archive
  24.2-B-04: 查询: by_goal / by_time / by_significance / by_tag
  24.2-B-05: Gate Integration: PASS → Episode, FAIL → None
  24.2-B-06: evaluation_trace 审计
  24.2-B-07: Episode 不可变 (frozen)
  24.2-B-08: Self 字段不存在于 Episode
  24.2-B-09: 幂等 save (同一 experience_id 不重复)
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
from ocos.memory.significance.evaluator import SignificanceEvaluator
from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.episode.store import EpisodeStore
from ocos.memory.episode.gate import episode_from_decision, EpisodeGate


# ── Helpers ──────────────────────────────────────────────────────────────────


def _high_significance_candidate() -> ExperienceCandidate:
    """产生高 Significance 的 Candidate（失败 + Goal + Reflection + Anomaly）。"""
    bundle = TraceBundle(
        observation={"type": "user_query", "content": "critical task"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed", "method": "strategy_x"},
        outcome={"success": False, "error": "ResourceExhausted", "new_knowledge": "strategy_x fails under load"},
        reflection_trace_id="refl-001",
        goal_context={"goal_id": "g-critical"},
    )
    builder = ExperienceBuilder()
    return builder.build(
        bundle,
        ExperienceSource.ANOMALY,
        context={"goal_id": "g-critical"},
    )


def _new_store() -> EpisodeStore:
    """创建新的内存数据库存储。"""
    store = EpisodeStore(":memory:")
    store.initialize()
    return store


# ── 24.2-B-01: Episode from_candidate ────────────────────────────────────────


def test_episode_from_candidate() -> None:
    """from_candidate 应正确构建 Episode。"""
    episode = Episode.from_candidate(
        experience_id="EXP-001",
        context={"env": "production"},
        goal="g1",
        decision="retry_with_backoff",
        action="execute_retry",
        outcome={"success": True, "attempts": 3},
        condition="cpu>80%",
        significance_score=0.75,
        evaluation_trace={"verdict": "PASS"},
        source="anomaly",
        tags=["network", "retry"],
    )

    assert episode.id.startswith("EPI-")
    assert episode.experience_id == "EXP-001"
    assert episode.goal == "g1"
    assert episode.significance_score == 0.75
    assert episode.source == "anomaly"
    assert episode.status == EpisodeStatus.ACTIVE
    assert episode.is_active()
    assert episode.has_tag("network")
    assert "network" in episode.tags


def test_episode_summary() -> None:
    """summary() 应返回可读摘要。"""
    episode = Episode.from_candidate(
        experience_id="EXP-001",
        context={},
        goal="g1",
        decision="d1",
        action="a1",
        outcome={"success": True},
        condition="",
        significance_score=0.8,
        evaluation_trace={},
    )
    summary = episode.summary()
    assert "EPI-" in summary
    assert "[g1]" in summary
    assert "score=0.800" in summary


# ── 24.2-B-02: EpisodeStore save + get ───────────────────────────────────────


def test_store_save_and_get() -> None:
    """保存后应能按 ID 获取。"""
    store = _new_store()
    episode = Episode.from_candidate(
        experience_id="EXP-001",
        context={"env": "test"},
        goal="g1",
        decision="d1",
        action="a1",
        outcome={"success": True},
        condition="",
        significance_score=0.6,
        evaluation_trace={},
    )
    store.save(episode)
    assert store.count() == 1

    retrieved = store.get(episode.id)
    assert retrieved is not None
    assert retrieved.id == episode.id
    assert retrieved.goal == "g1"
    assert retrieved.significance_score == 0.6


def test_store_get_nonexistent() -> None:
    """获取不存在的 ID 返回 None。"""
    store = _new_store()
    assert store.get("nonexistent") is None


# ── 24.2-B-03: archive ───────────────────────────────────────────────────────


def test_store_archive() -> None:
    """archive 应将 Episode 状态改为 ARCHIVED。"""
    store = _new_store()
    episode = Episode.from_candidate(
        experience_id="EXP-001",
        context={},
        goal="g1",
        decision="d1",
        action="a1",
        outcome={},
        condition="",
        significance_score=0.5,
        evaluation_trace={},
    )
    store.save(episode)

    assert store.archive(episode.id) is True
    retrieved = store.get(episode.id)
    assert retrieved is not None
    assert retrieved.status == EpisodeStatus.ARCHIVED
    assert not retrieved.is_active()


def test_store_archive_nonexistent() -> None:
    """archive 不存在的 ID 返回 False。"""
    store = _new_store()
    assert store.archive("nonexistent") is False


# ── 24.2-B-04: 查询 ──────────────────────────────────────────────────────────


def test_query_by_goal() -> None:
    """by_goal 应只返回匹配 Goal 的 Episode。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {"s": True}, "", 0.8, {})
    e2 = Episode.from_candidate("EXP-002", {}, "g2", "d2", "a2", {"s": True}, "", 0.6, {})
    e3 = Episode.from_candidate("EXP-003", {}, "g1", "d3", "a3", {"s": False}, "", 0.9, {})

    for e in [e1, e2, e3]:
        store.save(e)

    results = store.query_by_goal("g1")
    assert len(results) == 2
    assert all(e.goal == "g1" for e in results)
    # 按 significance_score DESC 排序
    assert results[0].significance_score >= results[1].significance_score


def test_query_by_goal_archived_excluded() -> None:
    """active_only=True 应排除 ARCHIVED Episode。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {}, "", 0.5, {})
    store.save(e1)
    store.archive(e1.id)

    results = store.query_by_goal("g1", active_only=True)
    assert len(results) == 0

    # active_only=False 应包含
    results_all = store.query_by_goal("g1", active_only=False)
    assert len(results_all) == 1


def test_query_by_time() -> None:
    """by_time 应按创建时间倒序。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {}, "", 0.5, {})
    e2 = Episode.from_candidate("EXP-002", {}, "g2", "d2", "a2", {}, "", 0.6, {})
    store.save(e1)
    store.save(e2)

    results = store.query_by_time()
    assert len(results) >= 2


def test_query_by_significance() -> None:
    """by_significance 应按分数阈值过滤。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {}, "", 0.4, {})
    e2 = Episode.from_candidate("EXP-002", {}, "g2", "d2", "a2", {}, "", 0.75, {})
    store.save(e1)
    store.save(e2)

    results = store.query_by_significance(min_score=0.5)
    assert len(results) == 1
    assert results[0].significance_score == 0.75


def test_query_by_tag() -> None:
    """by_tag 应返回包含指定 Tag 的 Episode。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {}, "", 0.5, {}, tags=["network", "retry"])
    e2 = Episode.from_candidate("EXP-002", {}, "g2", "d2", "a2", {}, "", 0.6, {}, tags=["disk"])
    store.save(e1)
    store.save(e2)

    results = store.query_by_tag("network")
    assert len(results) == 1
    assert results[0].has_tag("network")

    results2 = store.query_by_tag("nonexistent")
    assert len(results2) == 0


# ── 24.2-B-05: Gate Integration ──────────────────────────────────────────────


def test_episode_gate_pass_creates_episode() -> None:
    """高 Significance Candidate → PASS → Episode 创建并入库。"""
    store = _new_store()
    candidate = _high_significance_candidate()
    gate = EpisodeGate(store, evaluator=SignificanceEvaluator(active_goals=["g-critical"]))

    episode = gate.process(candidate)
    assert episode is not None
    assert episode.id.startswith("EPI-")
    assert episode.goal == "g-critical"
    assert episode.significance_score >= 0.5

    # 验证入库
    assert store.count() == 1
    assert store.get(episode.id) is not None


def test_episode_gate_fail_returns_none() -> None:
    """低 Significance Candidate → FAIL → 返回 None，不入库。"""
    store = _new_store()
    bundle = TraceBundle(
        observation={"type": "ping"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "ok"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    gate = EpisodeGate(store)
    episode = gate.process(candidate)
    assert episode is None
    assert store.count() == 0


def test_episode_gate_process_all() -> None:
    """批量处理: PASS 的入库，FAIL 的忽略。"""
    store = _new_store()
    high = _high_significance_candidate()

    bundle = TraceBundle(
        observation={"type": "ping"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "ok"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    low = builder.build(bundle, ExperienceSource.DECISION, {})

    gate = EpisodeGate(store, evaluator=SignificanceEvaluator(active_goals=["g-critical"]))
    episodes = gate.process_all([low, high])

    assert len(episodes) == 1
    assert episodes[0].goal == "g-critical"
    assert store.count() == 1


# ── 24.2-B-06: evaluation_trace 审计 ─────────────────────────────────────────


def test_episode_from_decision_has_evaluation_trace() -> None:
    """episode_from_decision 应包含完整 evaluation_trace。"""
    candidate = _high_significance_candidate()
    evaluator = SignificanceEvaluator(active_goals=["g-critical"])
    decision = evaluator.evaluate(candidate)

    episode = episode_from_decision(candidate, decision)
    trace = episode.evaluation_trace

    assert "experience_id" in trace
    assert trace["experience_id"] == candidate.id
    assert "dimensions" in trace
    assert set(trace["dimensions"].keys()) == {
        "goal_impact", "prediction_error", "knowledge_change", "future_relevance"
    }
    assert "weights" in trace
    assert "weighted_total" in trace
    assert "threshold" in trace
    assert trace["verdict"] == "pass"


def test_episode_from_decision_fails_on_fail_verdict() -> None:
    """FAIL 的 decision 不应创建 Episode。"""
    bundle = TraceBundle(
        observation={"type": "ping"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "ok"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})
    evaluator = SignificanceEvaluator()
    decision = evaluator.evaluate(candidate)

    assert decision.verdict.value == "fail"
    with pytest.raises(ValueError, match="FAIL"):
        episode_from_decision(candidate, decision)


# ── 24.2-B-07: Episode 不可变 ────────────────────────────────────────────────


def test_episode_is_immutable() -> None:
    """Episode 是 frozen dataclass，不可修改。"""
    episode = Episode.from_candidate(
        "EXP-001", {}, "g1", "d1", "a1", {}, "", 0.5, {}
    )
    with pytest.raises(Exception):
        episode.significance_score = 0.9  # type: ignore[misc]


# ── 24.2-B-08: Self 字段不存在 ──────────────────────────────────────────────


def test_episode_has_no_self_fields() -> None:
    """Episode 的字段名中不得出现 Self 相关词汇。"""
    fields = {f.name for f in Episode.__dataclass_fields__.values()}
    forbidden = {"self", "identity", "personality", "value", "mission"}
    overlap = fields & forbidden
    assert len(overlap) == 0, f"Episode has forbidden fields: {overlap}"


# ── 24.2-B-09: 幂等 save ─────────────────────────────────────────────────────


def test_store_save_idempotent() -> None:
    """同一 experience_id 不重复创建 Episode。"""
    store = _new_store()
    e1 = Episode.from_candidate("EXP-001", {}, "g1", "d1", "a1", {}, "", 0.5, {})
    e2 = Episode.from_candidate("EXP-001", {}, "g1", "d2", "a2", {}, "", 0.6, {})

    store.save(e1)
    store.save(e2)  # same experience_id → skip

    assert store.count() == 1
    retrieved = store.get(e1.id)
    assert retrieved is not None
    # 第一次保存的版本保留
    assert retrieved.significance_score == 0.5


# ── 边界案例 ──────────────────────────────────────────────────────────────────


def test_store_empty_query() -> None:
    """空数据库查询应返回空列表。"""
    store = _new_store()
    assert store.query_by_goal("g1") == []
    assert store.query_by_time() == []
    assert store.query_by_significance() == []
    assert store.query_by_tag("tag") == []


def test_episode_roundtrip_json_fields() -> None:
    """JSON 字段 (context, outcome, evaluation_trace, tags) 应正确往返。"""
    store = _new_store()
    episode = Episode.from_candidate(
        experience_id="EXP-001",
        context={"env": "prod", "region": "us-east-1"},
        goal="g1",
        decision="d1",
        action="a1",
        outcome={"success": False, "error": "timeout", "retries": 3},
        condition="load>1000",
        significance_score=0.85,
        evaluation_trace={"dimensions": {"goal_impact": 1.0}, "verdict": "PASS"},
        source="anomaly",
        tags=["critical", "timeout", "network"],
    )
    store.save(episode)

    retrieved = store.get(episode.id)
    assert retrieved is not None
    assert retrieved.context == {"env": "prod", "region": "us-east-1"}
    assert retrieved.outcome == {"success": False, "error": "timeout", "retries": 3}
    assert retrieved.evaluation_trace["verdict"] == "PASS"
    assert set(retrieved.tags) == {"critical", "timeout", "network"}
