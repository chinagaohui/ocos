"""P1-A 验收测试 — Belief/Pattern 持久化写路径。

覆盖:
    1. BeliefSystem 无 hub → 行为不变（纯内存）
    2. BeliefSystem + hub → L6 门控通过 → hub.belief 持久化（evidence 溯源）
    3. L6 门控拒绝（六类禁止词）→ 仅内存，rejected_count 累加
    4. 同 statement 重复 add → 幂等更新（不产生重复行）
    5. consolidate_episodes → Episode → Belief 迁移轨迹（evidence 含 episode id）
    6. consolidate 幂等（重跑不重复）
    7. learning_trigger → 重复 (condition, action) 聚合出 Pattern
    8. learning_trigger 幂等（重跑不重复）

运行: pytest ocos/tests/test_belief_consolidation.py -v
"""

from __future__ import annotations

import uuid

import pytest

from ocos.agent.belief_consolidation import consolidate_episodes
from ocos.agent.belief_system import BeliefSource, BeliefSystem
from ocos.agent.learning_trigger import scan_for_patterns
from ocos.memory.episode.models import Episode
from ocos.memory.hub import MemoryHub
from ocos.memory.pattern.models import PatternStatus


@pytest.fixture()
def hub():
    h = MemoryHub(":memory:")
    h.initialize()
    yield h


def _make_episode(hub, action="打开门", condition="遇到门", significance=0.8,
                  decision="", source="decision", experience_id=None) -> Episode:
    ep = Episode.from_candidate(
        experience_id=experience_id or f"EXP-{uuid.uuid4().hex[:8]}",
        context={"scene": "test"},
        goal="测试目标",
        decision=decision or action,
        action=action,
        outcome={"success": True},
        condition=condition,
        significance_score=significance,
        evaluation_trace={},
        source=source,
    )
    hub.episode.save(ep)
    return ep


# ── 1. 无 hub 行为不变 ──────────────────────────────────────────────────

def test_add_without_hub_keeps_memory_only():
    bs = BeliefSystem()
    bs.add("当前系统运行于 Linux", 0.8)
    assert bs.belief_count == 1
    assert bs.persisted_count == 0
    assert bs.rejected_count == 0
    assert bs.get_held()[0].statement == "当前系统运行于 Linux"


# ── 2. L6 门控通过 → 持久化 + evidence 溯源 ─────────────────────────────

def test_add_persists_valid_statement(hub):
    bs = BeliefSystem(hub=hub)
    bs.add("当前系统运行于 Linux", 0.8, source=BeliefSource.OBSERVATION,
           evidence_ids=("EPI-ABC123",))
    assert bs.persisted_count == 1

    persisted = hub.belief.get_all_active()
    assert len(persisted) == 1
    b = persisted[0]
    assert b.statement == "当前系统运行于 Linux"
    assert b.confidence == pytest.approx(0.8)
    assert len(b.evidence_ids) == 1  # Evidence 溯源非空


# ── 3. L6 门控拒绝 ─────────────────────────────────────────────────────

def test_add_rejects_forbidden_statement(hub):
    bs = BeliefSystem(hub=hub)
    # 六类禁止词之一（情感/偏好类）——门控拒绝
    bs.add("当前系统喜欢用户", 0.9)
    assert bs.rejected_count == 1
    assert bs.persisted_count == 0
    assert bs.belief_count == 1          # 内存仍保留
    assert hub.belief.get_all_active() == []


# ── 4. 幂等更新 ─────────────────────────────────────────────────────────

def test_add_same_statement_updates_not_duplicates(hub):
    bs = BeliefSystem(hub=hub)
    bs.add("当前系统运行于 Linux", 0.6)
    bs.add("当前系统运行于 Linux", 0.9)
    persisted = hub.belief.get_all_active()
    assert len(persisted) == 1
    assert persisted[0].confidence == pytest.approx(0.9)  # max 合并


# ── 5. Episode → Belief 迁移轨迹 ───────────────────────────────────────

def test_consolidate_episodes_creates_trail(hub):
    ep1 = _make_episode(hub, action="打开门", significance=0.8)
    ep2 = _make_episode(hub, action="关闭灯", significance=0.7)

    records = consolidate_episodes(hub, limit=10)
    assert len(records) == 2
    assert all(r.status == "consolidated" for r in records)

    by_ep = {r.episode_id: r for r in records}
    assert by_ep[ep1.id].belief_id
    assert by_ep[ep2.id].belief_id

    persisted = hub.belief.get_all_active()
    assert len(persisted) == 2
    # 迁移轨迹: belief 的 evidence 溯源 → episode id（经 _trail 冗余标记）
    for b in persisted:
        assert b.scope["_trail"] == [ep1.id] or b.scope["_trail"] == [ep2.id]
        assert b.statement.startswith("当前系统 ")
        assert len(b.evidence_ids) == 1  # Evidence id 已写入


# ── 6. consolidate 幂等 ────────────────────────────────────────────────

def test_consolidate_idempotent(hub):
    _make_episode(hub, action="打开门", significance=0.8)

    first = consolidate_episodes(hub, limit=10)
    assert len(first) == 1
    assert first[0].status == "consolidated"

    second = consolidate_episodes(hub, limit=10)
    assert len(second) == 1
    assert second[0].status == "skipped_duplicate"
    assert len(hub.belief.get_all_active()) == 1  # 不重复


# ── 7. learning_trigger → Pattern ──────────────────────────────────────

def test_learning_trigger_creates_pattern(hub):
    for _ in range(3):
        _make_episode(hub, action="重试连接", condition="网络超时", significance=0.6)

    records = scan_for_patterns(hub, min_support=3)
    assert len(records) == 1
    assert records[0].status == "created"
    assert records[0].support == 3

    patterns = hub.pattern.query_by_status(PatternStatus.CANDIDATE)
    assert len(patterns) == 1
    p = patterns[0]
    assert "网络超时" in p.observed_relation
    assert p.supporting_episode_count == 3


# ── 8. learning_trigger 幂等 ───────────────────────────────────────────

def test_learning_trigger_idempotent(hub):
    for _ in range(3):
        _make_episode(hub, action="重试连接", condition="网络超时", significance=0.6)

    first = scan_for_patterns(hub, min_support=3)
    second = scan_for_patterns(hub, min_support=3)
    assert first[0].status == "created"
    assert second[0].status == "skipped_duplicate"
    assert len(hub.pattern.query_by_status(PatternStatus.CANDIDATE)) == 1


# ── 补充: 不足 min_support 不触发 ──────────────────────────────────────

def test_learning_trigger_below_support(hub):
    _make_episode(hub, action="重试连接", condition="网络超时", significance=0.6)
    _make_episode(hub, action="重试连接", condition="网络超时", significance=0.6)
    records = scan_for_patterns(hub, min_support=3)
    assert records == []
    assert hub.pattern.query_by_status(PatternStatus.CANDIDATE) == []
