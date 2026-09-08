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
        """修复前恒空 → 修复后 lesson 可被召回。

        O-3 修复后稀疏库 (<50 条) 动态阈值 0.25 生效——context 须与
        lesson 内容有实质 bi-gram 重叠方能通过严格过滤。
        """
        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        hub.episode.save(_lesson_episode(1))
        recall = MemoryRecall(hub)
        results = recall.recall("分步总结比一次性输出", limit=10)
        exp = [r for r in results if r.source == "experience"]
        assert exp, "lesson 应被召回"
        assert "总结" in exp[0].content or "分步" in exp[0].content

    def test_no_lessons_no_crash(self, tmp_path):
        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        recall = MemoryRecall(hub)
        results = recall.recall("随便什么", limit=10)
        assert isinstance(results, list)


class TestRecallFixesO1O3:
    """O-1: 语义召回 content=statement（非 dataclass repr）。
    O-3: 动态阈值方向——有密度数据时生效（稀疏→严格）。
    """

    def test_semantic_content_is_statement_not_repr(self, tmp_path):
        from ocos.memory.semantic.models import (
            KnowledgeEntry,
            KnowledgeScope,
        )
        from ocos.memory.semantic.store import SemanticStore

        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        entry = KnowledgeEntry.create(
            statement="长文档应分步总结后再输出",
            source_patterns=["pat-1"],
            confidence=0.9,
            scope=KnowledgeScope(domain="document"),
            stability=0.8,
        )
        hub.semantic.save(entry)
        recall = MemoryRecall(hub)
        results = recall.recall("长文档分步总结", limit=10)
        sem = [r for r in results if r.source == "semantic"]
        assert sem, "语义条目应被召回"
        assert sem[0].content == "长文档应分步总结后再输出"
        assert not sem[0].content.startswith("KnowledgeEntry(")

    def test_sparse_memory_filters_irrelevant(self, tmp_path):
        """O-3: 稀疏库 (<50) 阈值 0.25 生效, 无重叠内容被过滤。"""
        hub = MemoryHub(str(tmp_path / "hub.db"))
        hub.initialize()
        hub.episode.save(_lesson_episode(1))
        recall = MemoryRecall(hub)
        results = recall.recall("完全无关的话题内容", limit=10)
        exp = [r for r in results if r.source == "experience"]
        assert exp == [], "无重叠 lesson 不应通过稀疏库严格阈值"

    def test_dynamic_threshold_uses_all_four_stores(self):
        """O-12: 密度统计覆盖 semantic_count / pattern_count。"""
        recall = MemoryRecall()

        class _FakeHub:
            def get_stats(self):
                return {"episode_count": 30, "belief_count": 10,
                        "semantic_count": 8, "pattern_count": 6}

        # 30+10+8+6 = 54 → 中密度 0.15（若漏算 semantic/pattern 则为 40 → 0.25）
        assert recall._dynamic_threshold(_FakeHub()) == 0.15
