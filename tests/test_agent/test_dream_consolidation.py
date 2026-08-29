"""P2-C Dream Consolidation 契约测试（L4 演化性）。

覆盖：Episode → Belief/Pattern 巩固、增强、幂等、弱模式修剪、降级。
"""

from datetime import datetime, timedelta, timezone

import pytest

from ocos.memory.belief.models import Belief, BeliefStatus
from ocos.memory.belief.store import BeliefStore
from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.episode.store import EpisodeStore
from ocos.memory.pattern.store import PatternStore

NOW = datetime.now(timezone.utc)


def _make_episode(
    ep_id: str,
    *,
    goal: str = "测试目标",
    condition: str = "online",
    outcome: dict | None = None,
    created_at: datetime = NOW,
) -> Episode:
    return Episode(
        id=ep_id,
        experience_id=f"exp-{ep_id}",
        created_at=created_at,
        goal=goal,
        decision=f"决策-{ep_id}",
        action=f"动作-{ep_id}",
        outcome=outcome or {"success": True, "result": "ok"},
        condition=condition,
        significance_score=0.8,
        status=EpisodeStatus.ACTIVE,
    )


@pytest.fixture
def agent():
    """最小 MasterAgent：真实三存储 + MagicMock 非关键依赖。"""
    from unittest.mock import MagicMock

    from ocos.agent.master_agent import MasterAgent

    episode_store = EpisodeStore(db_path=":memory:")
    episode_store.initialize()
    belief_store = BeliefStore(db_path=":memory:")
    belief_store.initialize()
    pattern_store = PatternStore(db_path=":memory:")
    pattern_store.initialize()

    identity = MagicMock()
    identity.verify.return_value = True
    goal_stack = MagicMock()
    intent = MagicMock()
    attention = MagicMock()
    working_memory = MagicMock()
    capability_manager = MagicMock()
    execution_manager = MagicMock()

    agent = MasterAgent(
        agent_id="test-dream",
        identity=identity,
        goal_stack=goal_stack,
        intent=intent,
        attention=attention,
        working_memory=working_memory,
        capability_manager=capability_manager,
        execution_manager=execution_manager,
        episode_store=episode_store,
        belief_store=belief_store,
        pattern_store=pattern_store,
    )
    agent._episode_store = episode_store
    agent._belief_store = belief_store
    agent._pattern_store = pattern_store
    return agent


class TestConsolidateEpisodes:
    def test_consolidate_creates_belief_and_pattern(self, agent):
        """今日 3 条同 goal/condition Episode → 巩固出 1 Belief + 1 Pattern，Episode 置 CONSOLIDATED。"""
        for i in range(3):
            agent._episode_store.save(_make_episode(f"EPI-{i}"))

        stats = agent._consolidate_episodes()

        assert stats["replayed"] == 3
        assert stats["beliefs_created"] == 1
        assert stats["patterns_created"] == 1

        # Episode 状态位：ACTIVE → CONSOLIDATED（幂等标记）
        for i in range(3):
            ep = agent._episode_store.get(f"EPI-{i}")
            assert ep.status == EpisodeStatus.CONSOLIDATED

        # Belief 落库且置信达 ACTIVE 阈值
        beliefs = agent._belief_store.query_by_status(BeliefStatus.ACTIVE)
        assert len(beliefs) == 1
        assert beliefs[0].confidence == pytest.approx(0.6)
        assert len(beliefs[0].evidence_ids) == 3

        # Pattern 落库（同 condition+outcome 聚合）
        assert agent._pattern_store.count() >= 1

    def test_consolidate_strengthens_existing_belief(self, agent):
        """二次巩固：新 Episode 同主题 → Belief 证据追加 + confidence 增强 0.1。"""
        for i in range(3):
            agent._episode_store.save(_make_episode(f"EPI-{i}"))
        agent._consolidate_episodes()

        # 注入 1 条新 Episode（同 goal），先置回 ACTIVE 语义：新 id 天然 ACTIVE
        agent._episode_store.save(_make_episode("EPI-NEW"))

        stats = agent._consolidate_episodes()

        assert stats["replayed"] == 1
        assert stats["beliefs_strengthened"] == 1
        assert stats["beliefs_created"] == 0

        beliefs = agent._belief_store.query_by_status(BeliefStatus.ACTIVE)
        assert len(beliefs) == 1
        assert beliefs[0].confidence == pytest.approx(0.7)  # 0.6 + 0.1
        assert "EPI-NEW" in beliefs[0].evidence_ids
        assert len(beliefs[0].evidence_ids) == 4

    def test_consolidate_idempotent(self, agent):
        """同一批 Episode 二次巩固 → 零重放（CONSOLIDATED 状态位天然幂等）。"""
        for i in range(3):
            agent._episode_store.save(_make_episode(f"EPI-{i}"))
        first = agent._consolidate_episodes()

        second = agent._consolidate_episodes()

        assert first["replayed"] == 3
        assert second["replayed"] == 0  # 已巩固不重放
        assert second["beliefs_created"] == 0
        assert second["patterns_created"] == 0

    def test_consolidate_prunes_weak_belief(self, agent):
        """预置弱 Belief（conf=0.3 < 0.35）→ 修剪为 ARCHIVED，stats.pruned ≥ 1。"""
        for i in range(3):
            agent._episode_store.save(_make_episode(f"EPI-{i}"))
        # 预置弱 Belief（同主题，低置信）
        weak = Belief(
            id="BLF-weak",
            statement="主题「测试目标」相关经历持续出现",
            source_knowledge_ids=(),
            evidence_ids=("EPI-0",),
            confidence=0.3,
            uncertainty=0.7,
            scope={"domain": "测试目标"},
            status=BeliefStatus.ACTIVE,
            created_at=NOW,
            last_updated=NOW,
        )
        agent._belief_store.save(weak)

        stats = agent._consolidate_episodes()

        assert stats["pruned"] >= 1
        pruned = agent._belief_store.get("BLF-weak")
        assert pruned.status == BeliefStatus.ARCHIVED

    def test_consolidate_ignores_yesterday_episodes(self, agent):
        """昨日 Episode 不进入当日巩固窗口。"""
        yesterday = NOW - timedelta(days=1)
        agent._episode_store.save(_make_episode("EPI-OLD", created_at=yesterday))

        stats = agent._consolidate_episodes()

        assert stats["replayed"] == 0
        assert stats["beliefs_created"] == 0
        ep = agent._episode_store.get("EPI-OLD")
        assert ep.status == EpisodeStatus.ACTIVE  # 未动

    def test_consolidate_degrades_without_episode_store(self):
        """无 Episode 存储 → 降级返回空 stats，不抛。"""
        from unittest.mock import MagicMock

        from ocos.agent.master_agent import MasterAgent

        agent = MasterAgent(
            agent_id="test-no-store",
            identity=MagicMock(),
            goal_stack=MagicMock(),
            intent=MagicMock(),
            attention=MagicMock(),
            working_memory=MagicMock(),
            capability_manager=MagicMock(),
            execution_manager=MagicMock(),
            episode_store=None,
        )

        stats = agent._consolidate_episodes()

        assert stats == {
            "replayed": 0,
            "beliefs_created": 0,
            "beliefs_strengthened": 0,
            "patterns_created": 0,
            "patterns_strengthened": 0,
            "pruned": 0,
        }

    def test_dream_reports_consolidation_stats(self, agent):
        """dream() 全链路：consolidation 结果含 consolidation_stats（L4 演化性证据）。"""
        from ocos.agent.lifecycle import LifecyclePhase

        for i in range(3):
            agent._episode_store.save(_make_episode(f"EPI-{i}"))
        # 合法相位链：BOOTING → ACTIVE → SLEEPING → DREAMING
        agent._lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)
        agent._lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)

        result = agent.dream()

        assert result["phase"] == "dream"
        stats = result["consolidation_stats"]
        assert stats["replayed"] == 3
        assert stats["beliefs_created"] == 1
