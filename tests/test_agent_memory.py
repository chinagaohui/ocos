"""OCOS agent episode_memory/experience_store 测试。"""

import pytest
from ocos.agent.episode_memory import Episode, EpisodeMemory
from ocos.agent.experience_store import Experience, ExperienceStore


class TestEpisode:
    def test_defaults(self):
        e = Episode()
        assert e.title == ""
        assert e.summary == ""
        assert e.events == []
        assert e.archived is False

    def test_custom(self):
        e = Episode(
            title="Test Episode",
            summary="A test",
            importance=8.0,
            emotional_mark="positive",
        )
        assert e.title == "Test Episode"
        assert e.importance == 8.0
        assert e.emotional_mark == "positive"


class TestEpisodeMemory:
    @pytest.fixture
    def memory(self):
        return EpisodeMemory(max_episodes=5)

    def test_empty_memory(self, memory):
        assert memory.count() == 0
        assert memory.recall() == []

    def test_record_and_recall(self, memory):
        ep = Episode(title="E1", summary="First episode", importance=7.0)
        eid = memory.record(ep)
        assert eid == ep.episode_id
        assert memory.count() == 1
        results = memory.recall()
        assert len(results) == 1
        assert results[0].title == "E1"

    def test_recall_with_query(self, memory):
        memory.record(Episode(title="Story A", summary="About cats"))
        memory.record(Episode(title="Story B", summary="About dogs"))
        results = memory.recall(query="cats")
        assert len(results) == 1
        assert "cats" in results[0].summary.lower()

    def test_recall_recent(self, memory):
        memory.record(Episode(title="E1"))
        memory.record(Episode(title="E2"))
        recent = memory.recall_recent(n=1)
        assert len(recent) == 1
        assert recent[0].title == "E2"

    def test_recall_important(self, memory):
        memory.record(Episode(title="Low", importance=2.0))
        memory.record(Episode(title="High", importance=8.0))
        important = memory.recall_important(threshold=5.0)
        assert len(important) == 1
        assert important[0].title == "High"

    def test_max_episodes_evicts_least_important(self, memory):
        for i in range(6):
            memory.record(Episode(title=f"E{i}", importance=float(i)))
        assert memory.count() == 6
        # Least important should be archived
        archived = [e for e in memory.recall() if e.archived]
        assert len(archived) == 1
        assert archived[0].title == "E0"

    def test_clear(self, memory):
        memory.record(Episode(title="E1"))
        memory.clear()
        assert memory.count() == 0


class TestExperience:
    def test_defaults(self):
        e = Experience(situation="S", action="A", outcome="O")
        assert e.reflection == ""
        assert e.importance == 0.5
        assert e.replayed_count == 0

    def test_custom(self):
        e = Experience(
            situation="Caught bug",
            action="Fixed it",
            outcome="Working",
            reflection="Need tests",
            importance=0.9,
            tags=["bug", "fix"],
        )
        assert e.reflection == "Need tests"
        assert e.importance == 0.9
        assert e.tags == ["bug", "fix"]


class TestExperienceStore:
    @pytest.fixture
    def store(self):
        return ExperienceStore(max_size=5, replay_batch_size=2)

    def test_empty_store(self, store):
        assert store.total_count == 0

    def test_record(self, store):
        exp_id = store.record("S1", "A1", "O1", "R1", importance=0.8)
        assert store.total_count == 1
        assert exp_id.startswith("exp-")

    def test_replay_random(self, store):
        store.record("S1", "A1", "O1")
        store.record("S2", "A2", "O2")
        replayed = store.replay_random(count=1)
        assert len(replayed) == 1
        assert replayed[0].replayed_count == 1

    def test_replay_recent(self, store):
        store.record("S1", "A1", "O1")
        store.record("S2", "A2", "O2")
        replayed = store.replay_recent(count=1)
        assert len(replayed) == 1

    def test_replay_important(self, store):
        store.record("S1", "A1", "O1", importance=0.3)
        store.record("S2", "A2", "O2", importance=0.9)
        replayed = store.replay_important(count=1)
        assert replayed[0].importance == 0.9

    def test_max_size_evicts_oldest(self, store):
        for i in range(6):
            store.record(f"S{i}", f"A{i}", f"O{i}")
        assert store.total_count == 5
        # Oldest should be evicted
        stats = store.get_stats()
        assert stats["total"] == 5

    def test_get_stats(self, store):
        store.record("S1", "A1", "O1", importance=0.5, duration=1.0)
        store.record("S2", "A2", "O2", importance=0.8, duration=2.0)
        stats = store.get_stats()
        assert stats["total"] == 2
        assert abs(stats["avg_importance"] - 0.65) < 0.01
        assert abs(stats["avg_duration"] - 1.5) < 0.01

    def test_clear(self, store):
        store.record("S1", "A1", "O1")
        store.clear()
        assert store.total_count == 0
