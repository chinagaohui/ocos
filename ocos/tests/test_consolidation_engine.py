"""Phase 8 测试 — Consolidation Engine（信息合并引擎）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ocos.engines.consolidation_engine import ConsolidationEngine
from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.knowledge.knowledge_abi import KnowledgeABI
from ocos.knowledge.knowledge_ontology import KnowledgeLevel
from ocos.models.information import (
    InformationMetadata,
    InformationState,
    PersistenceLevel,
    SemanticRole,
    UniversalAddress,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_abi() -> KnowledgeABI:
    abi = MagicMock(spec=KnowledgeABI)
    abi.create_unit.return_value = (True, "ku-consolidated-001")
    return abi


@pytest.fixture
def engine(mock_abi) -> ConsolidationEngine:
    return ConsolidationEngine(knowledge_abi=mock_abi)


@pytest.fixture
def engine_with_bus(mock_abi) -> tuple[ConsolidationEngine, EventBus]:
    bus = EventBus()
    engine = ConsolidationEngine(knowledge_abi=mock_abi, event_bus=bus)
    return engine, bus


def _make_meta(
    address_id: str = "i1",
    role: SemanticRole = SemanticRole.OBSERVATION,
    state: InformationState = InformationState.VALIDATED,
) -> InformationMetadata:
    return InformationMetadata(
        address=UniversalAddress(namespace="test", type="info", id=address_id),
        state=state,
        semantic_role=role,
        persistence_level=PersistenceLevel.PERSISTENT,
        importance=0.5,
    )


# ══════════════════════════════════════════════════════════════════════════
# consolidate
# ══════════════════════════════════════════════════════════════════════════


class TestConsolidate:
    def test_consolidate_two_sources(self, engine, mock_abi):
        """两条源信息可成功合并。"""
        sources = [_make_meta("i1"), _make_meta("i2")]
        ok, msg = engine.consolidate(sources)
        assert ok
        assert msg == "ku-consolidated-001"
        mock_abi.create_unit.assert_called_once()

    def test_consolidate_three_sources(self, engine, mock_abi):
        """多条源信息合并。"""
        sources = [_make_meta(f"i{i}") for i in range(3)]
        ok, msg = engine.consolidate(sources)
        assert ok

    def test_consolidate_less_than_two_fails(self, engine):
        """不足 2 条源信息失败。"""
        sources = [_make_meta("i1")]
        ok, msg = engine.consolidate(sources)
        assert not ok
        assert "至少需要" in msg

    def test_consolidate_empty_list_fails(self, engine):
        """空列表失败。"""
        ok, msg = engine.consolidate([])
        assert not ok
        assert "至少需要" in msg

    def test_consolidate_without_abi(self):
        """无 KnowledgeABI 时仍可成功（仅发射事件、不做桥接）。"""
        engine = ConsolidationEngine(knowledge_abi=None)
        sources = [_make_meta("i1"), _make_meta("i2")]
        ok, msg = engine.consolidate(sources)
        assert ok
        assert msg == "consolidated"

    def test_consolidate_target_level(self, engine, mock_abi):
        """显式指定目标层级。"""
        sources = [_make_meta("i1"), _make_meta("i2")]
        ok, msg = engine.consolidate(sources, target_level=KnowledgeLevel.PATTERN)
        assert ok
        # 验证 create_unit 使用了指定层级
        call_kwargs = mock_abi.create_unit.call_args.kwargs
        assert call_kwargs["level"] == KnowledgeLevel.PATTERN

    def test_consolidate_auto_target_level(self, engine, mock_abi):
        """不指定目标层级时自动推断。"""
        sources = [
            _make_meta("i1", role=SemanticRole.OBSERVATION),
            _make_meta("i2", role=SemanticRole.OBSERVATION),
        ]
        ok, msg = engine.consolidate(sources)
        assert ok

    def test_consolidate_emits_status_changed(self, engine_with_bus):
        """合并后发射 INFORMATION_STATUS_CHANGED 事件（每个源一个）。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.INFORMATION_STATUS_CHANGED, received.append)

        sources = [_make_meta("i1"), _make_meta("i2")]
        engine.consolidate(sources)

        # 每个源发射一个事件
        assert len(received) == 2
        for evt in received:
            assert evt.event_type == EventType.INFORMATION_STATUS_CHANGED

    def test_consolidate_emits_candidate_proposed(self, engine_with_bus):
        """合并后发射 KNOWLEDGE_CANDIDATE_PROPOSED 事件。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.KNOWLEDGE_CANDIDATE_PROPOSED, received.append)

        sources = [_make_meta("i1"), _make_meta("i2")]
        engine.consolidate(sources)

        assert len(received) == 1
        assert received[0].event_type == EventType.KNOWLEDGE_CANDIDATE_PROPOSED
        assert "source_ids" in received[0].payload
        assert received[0].payload["source_count"] == 2

    def test_abi_failure_propagates(self, mock_abi):
        """ABI 创建失败时返回错误。"""
        mock_abi.create_unit.return_value = (False, "invalid level")
        engine = ConsolidationEngine(knowledge_abi=mock_abi)
        sources = [_make_meta("i1"), _make_meta("i2")]
        ok, msg = engine.consolidate(sources)
        assert not ok
        assert "知识单元创建失败" in msg


# ══════════════════════════════════════════════════════════════════════════
# propose_candidate
# ══════════════════════════════════════════════════════════════════════════


class TestProposeCandidate:
    def test_propose_basic(self, engine, mock_abi):
        """直接提交候选知识。"""
        ok, msg = engine.propose_candidate(
            content={"summary": "test pattern"},
            source_ids=["i1", "i2", "i3"],
        )
        assert ok

    def test_propose_too_few_sources(self, engine):
        """来源不足失败。"""
        ok, msg = engine.propose_candidate(
            content={"summary": "test"},
            source_ids=["i1"],
        )
        assert not ok
        assert "至少需要" in msg

    def test_propose_empty_content(self, engine):
        """内容为空失败。"""
        ok, msg = engine.propose_candidate(
            content={},
            source_ids=["i1", "i2"],
        )
        assert not ok
        assert "不能为空" in msg

    def test_propose_with_target_level(self, engine, mock_abi):
        """指定目标层级。"""
        ok, msg = engine.propose_candidate(
            content={"summary": "principle"},
            source_ids=["i1", "i2"],
            target_level=KnowledgeLevel.PRINCIPLE,
        )
        assert ok
        call_kwargs = mock_abi.create_unit.call_args.kwargs
        assert call_kwargs["level"] == KnowledgeLevel.PRINCIPLE

    def test_propose_without_abi(self):
        """无 ABI 时仍可成功（不桥接）。"""
        engine = ConsolidationEngine(knowledge_abi=None)
        ok, msg = engine.propose_candidate(
            content={"summary": "test"},
            source_ids=["i1", "i2"],
        )
        assert ok
        assert msg == "proposed"

    def test_propose_emits_event(self, engine_with_bus):
        """propose_candidate 发射 KNOWLEDGE_CANDIDATE_PROPOSED 事件。"""
        engine, bus = engine_with_bus
        received: list[Event] = []
        bus.subscribe(EventType.KNOWLEDGE_CANDIDATE_PROPOSED, received.append)

        engine.propose_candidate(
            content={"summary": "test"},
            source_ids=["i1", "i2"],
        )
        assert len(received) == 1
        assert received[0].event_type == EventType.KNOWLEDGE_CANDIDATE_PROPOSED
