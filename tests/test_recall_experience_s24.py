"""S2.4: recall experience 召回链路修复回归（白皮书 P2）。

原缺陷：_recall_experience 引用不存在的 hub.experience（MemoryHub 只有
episode/belief/semantic/pattern 四库）——经验召回恒空且无报错。
修复后经 hub.episode.query_by_source("lesson") 召回 LessonsLearned。
"""

from __future__ import annotations

import pytest

from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.episode.store import EpisodeStore
from ocos.memory.hub import MemoryHub
from ocos.memory.recall import MemoryRecall


def _lesson_episode(i: int) -> Episode:
    from datetime import datetime, timezone
    return Episode(
        id=f"LESSON-test-{i:04d}",
        experience_id=f"LESSON-{i}",
        created_at=datetime.now(timezone.utc),
        session_id="s1",
        context={"lesson_type": "lesson",
                 "source_experiences": ["exp-1", "exp-2"]},
        goal=None,
        decision="分步总结比一次性输出更可靠",
        action="summarize",
        outcome={"predicted": "更好", "confidence": 0.8},
        condition="当任务涉及长文档总结时",
        significance_score=0.7,
        source="lesson",
        status=EpisodeStatus.ACTIVE,
        tags=["synthesized", "lesson"],
    )


class TestEpisodeStoreQueryBySource:
    def test_query_by_source_lessons(self, tmp_path):
        store = EpisodeStore(str(tmp_path / "t.db"))
        store.initialize()
        store.save(_lesson_episode(1))
        store.save(_lesson_episode(2))
        rows = store.query_by_source("lesson", limit=10)
        assert len(rows) == 2
        assert rows[0].source == "lesson"
        # 非 lesson 的查不到
        assert store.query_by_source("decision", limit=10) == []


class TestRecallExperience:
    def test_lessons_now_recallable(self, tmp_path):
        """修复前恒空 → 修复后 lesson 可被召回。"""
        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        hub.episode.save(_lesson_episode(1))
        recall = MemoryRecall(hub)
        results = recall.recall("分步总结任务", limit=10)
        exp = [r for r in results if r.source == "experience"]
        assert exp, "lesson 应被召回"
        assert "总结" in exp[0].content or "分步" in exp[0].content

    def test_no_lessons_no_crash(self, tmp_path):
        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        recall = MemoryRecall(hub)
        results = recall.recall("随便什么", limit=10)
        assert isinstance(results, list)
