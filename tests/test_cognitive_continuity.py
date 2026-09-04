"""OCOS cognitive_continuity 测试。"""

import pytest
from ocos.cognitive_continuity.continuity_types import (
    TimeGranularity,
    TimeAnchor,
    ExperienceNode,
    TimeContainer,
    LifeMemoryGraph,
    TimelineEntry,
    CognitiveTimeline,
    IdentitySnapshot,
    KnowledgeAge,
    AgedKnowledge,
)


class TestTimeGranularity:
    def test_granularity_values(self):
        assert TimeGranularity.EXPERIENCE.value == "experience"
        assert TimeGranularity.DAY.value == "day"
        assert TimeGranularity.WEEK.value == "week"
        assert TimeGranularity.MONTH.value == "month"
        assert TimeGranularity.SEASON.value == "season"
        assert TimeGranularity.YEAR.value == "year"


class TestTimeAnchor:
    def test_anchor_values(self):
        assert TimeAnchor.PAST.value == "past"
        assert TimeAnchor.PRESENT.value == "present"
        assert TimeAnchor.FUTURE_INTENT.value == "future_intent"


class TestExperienceNode:
    def test_defaults(self):
        node = ExperienceNode()
        assert node.node_id == ""
        assert node.tick_id == 0
        assert node.summary == ""
        assert node.importance == 0.0
        assert node.tags == []

    def test_custom(self):
        node = ExperienceNode(
            node_id="e1",
            tick_id=42,
            summary="Test summary",
            importance=0.9,
            tags=["bug", "fix"],
            created_at_tick=100,
        )
        assert node.node_id == "e1"
        assert node.importance == 0.9


class TestTimeContainer:
    def test_defaults(self):
        tc = TimeContainer()
        assert tc.granularity == TimeGranularity.DAY
        assert tc.label == ""
        assert tc.entries == []
        assert tc.summary == ""
        assert tc.max_entries == 20

    def test_custom(self):
        tc = TimeContainer(
            granularity=TimeGranularity.WEEK,
            label="2026-W30",
            summary="Weekly summary",
        )
        assert tc.granularity == TimeGranularity.WEEK
        assert tc.label == "2026-W30"


class TestLifeMemoryGraph:
    def test_empty_graph(self):
        graph = LifeMemoryGraph()
        assert graph.total_experiences == 0
        assert graph.years == []
        assert graph.months == []

    def test_add_experience(self):
        graph = LifeMemoryGraph()
        node = ExperienceNode(node_id="e1", summary="Test")
        graph.experiences.append(node)
        assert graph.total_experiences == 1

    def test_structure(self):
        graph = LifeMemoryGraph(
            years=[TimeContainer(granularity=TimeGranularity.YEAR, label="2026")],
            months=[TimeContainer(granularity=TimeGranularity.MONTH, label="2026-09")],
            weeks=[TimeContainer(granularity=TimeGranularity.WEEK, label="2026-W30")],
            days=[TimeContainer(granularity=TimeGranularity.DAY, label="2026-09-04")],
        )
        assert len(graph.years) == 1
        assert len(graph.months) == 1


class TestTimelineEntry:
    def test_defaults(self):
        entry = TimelineEntry()
        assert entry.entry_id == ""
        assert entry.anchor == TimeAnchor.PRESENT
        assert entry.tick_id == 0
        assert entry.summary == ""
        assert entry.significance == 0.0

    def test_custom(self):
        entry = TimelineEntry(
            entry_id="t1",
            anchor=TimeAnchor.PAST,
            tick_id=42,
            label="Test event",
            summary="Something happened",
            significance=0.8,
        )
        assert entry.anchor == TimeAnchor.PAST
        assert entry.significance == 0.8


class TestCognitiveTimeline:
    def test_empty_timeline(self):
        ct = CognitiveTimeline()
        assert ct.past_count == 0
        assert ct.intent_count == 0

    def test_add_past_entry(self):
        ct = CognitiveTimeline()
        entry = TimelineEntry(entry_id="p1", label="Past event")
        ct.add_past(entry)
        assert ct.past_count == 1
        assert entry.anchor == TimeAnchor.PAST

    def test_add_present_entry(self):
        ct = CognitiveTimeline()
        entry = TimelineEntry(entry_id="pr1", label="Present event")
        ct.add_present(entry)
        assert len(ct.present) == 1
        assert entry.anchor == TimeAnchor.PRESENT

    def test_add_intent(self):
        ct = CognitiveTimeline()
        entry = TimelineEntry(entry_id="fi1", label="Future intent")
        ct.add_intent(entry)
        assert ct.intent_count == 1
        assert entry.anchor == TimeAnchor.FUTURE_INTENT


class TestKnowledgeAge:
    def test_age_values(self):
        assert KnowledgeAge.FRESH.value == "fresh"
        assert KnowledgeAge.CURRENT.value == "current"
        assert KnowledgeAge.AGING.value == "aging"
        assert KnowledgeAge.LEGACY.value == "legacy"
        assert KnowledgeAge.ARCHIVED.value == "archived"


class TestAgedKnowledge:
    def test_defaults(self):
        ak = AgedKnowledge()
        assert ak.knowledge_id == ""
        assert ak.content == ""
        assert ak.ticks_age == 0
        assert ak.age == KnowledgeAge.FRESH
        assert ak.reference_count == 0
        assert ak.weight == 1.0
        assert ak.is_core is False

    def test_custom(self):
        ak = AgedKnowledge(
            knowledge_id="k1",
            content="Important knowledge",
            ticks_age=500,
            age=KnowledgeAge.AGING,
            weight=0.7,
            is_core=True,
        )
        assert ak.age == KnowledgeAge.AGING
        assert ak.weight == 0.7
        assert ak.is_core is True