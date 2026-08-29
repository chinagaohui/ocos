"""GAP-P2-4: wisdom_store 落盘 + personalization 补实现测试。

覆盖:
  1. WisdomStore + connection → add/promote 落库, load_from_db 重建
  2. personalize_content FORMAL → 结构化前缀
  3. personalize_options BOLD → 反转排序
"""

import sqlite3

from ocos.personal_memory.wisdom_store import WisdomStore
from ocos.personal_memory.wisdom_types import WisdomItem, WisdomState, WisdomEvidence
from ocos.personal_intelligence.personalization_engine import PersonalizationEngine
from ocos.personal_intelligence.pi_types import (
    CognitiveSignature,
    InteractionStyle,
    RiskTolerance,
)
from ocos.storage.schema import STORAGE_TABLES


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    for stmts in STORAGE_TABLES.values():
        for s in stmts:
            c.execute(s)
    return c


def _item(wid: str, principle: str = "先冻结接口边界") -> WisdomItem:
    return WisdomItem(
        wisdom_id=wid,
        principle=principle,
        source_patterns=("p1",),
        evidence=[WisdomEvidence("e1", "episode", "ep-1", True, 0.8, 1)],
    )


class TestWisdomStorePersistence:
    def test_add_persists_and_load_from_db(self):
        c = _conn()
        store = WisdomStore(connection=c)
        store.add_wisdom("u1", _item("w1"))

        reloaded = WisdomStore.load_from_db(c)
        item = reloaded.get_wisdom("u1", "w1")
        assert item is not None
        assert item.principle == "先冻结接口边界"
        assert item.source_patterns == ("p1",)
        assert len(item.evidence) == 1 and item.evidence[0].strength == 0.8

    def test_promote_persists_state(self):
        c = _conn()
        store = WisdomStore(connection=c)
        store.add_wisdom("u1", _item("w1"))
        assert store.promote_wisdom("u1", "w1", WisdomState.VALIDATING, tick_id=5)

        reloaded = WisdomStore.load_from_db(c)
        item = reloaded.get_wisdom("u1", "w1")
        assert item is not None and item.state == WisdomState.VALIDATING

    def test_deprecate_persists_state(self):
        c = _conn()
        store = WisdomStore(connection=c)
        store.add_wisdom("u1", _item("w1"))
        assert store.deprecate_wisdom("u1", "w1", tick_id=5)

        reloaded = WisdomStore.load_from_db(c)
        item = reloaded.get_wisdom("u1", "w1")
        assert item is not None and item.state == WisdomState.DEPRECATED

    def test_no_connection_stays_memory_only(self):
        store = WisdomStore()
        store.add_wisdom("u1", _item("w1"))
        assert store.user_wisdom_count("u1") == 1


class TestPersonalizationImplemented:
    def test_formal_content_prefix(self):
        sig = CognitiveSignature(
            interaction_style=InteractionStyle.FORMAL,
            pattern_confidence=0.9,
            total_observations=50,
        )
        engine = PersonalizationEngine()
        engine.signature_engine.signature = sig
        out = engine.personalize_response("核心结论")
        assert out.startswith("结构化总结：")
        assert "核心结论" in out

    def test_bold_options_reversed(self):
        sig = CognitiveSignature(
            risk_tolerance=RiskTolerance.BOLD,
            pattern_confidence=0.9,
            total_observations=50,
        )
        engine = PersonalizationEngine()
        engine.signature_engine.signature = sig
        out = engine.personalize_options(["方案A", "方案B", "方案C"])
        assert out == ["方案C", "方案B", "方案A"]

    def test_conservative_keeps_order(self):
        sig = CognitiveSignature(
            risk_tolerance=RiskTolerance.CONSERVATIVE,
            pattern_confidence=0.9,
            total_observations=50,
        )
        engine = PersonalizationEngine()
        engine.signature_engine.signature = sig
        out = engine.personalize_options(["方案A", "方案B", "方案C"])
        assert out == ["方案A", "方案B", "方案C"]
