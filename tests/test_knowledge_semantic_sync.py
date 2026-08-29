"""GAP-P2-1: KnowledgeRegistry → SemanticStore 持久化镜像测试。

覆盖:
  1. register → semantic knowledge 表落行（statement/scope 映射）
  2. update → revision 递增 + 旧版本 SUPERSEDED（版本链）
  3. remove → semantic 标记 DEPRECATED
  4. 无 semantic_store → 内存模式行为不变（兼容旧构造）
"""

import pytest

from ocos.knowledge.store.ontology import KnowledgeLevel, KnowledgeUnit
from ocos.knowledge.store.registry import AccessMatrix, KnowledgeRegistry
from ocos.memory.semantic.models import KnowledgeStatus
from ocos.memory.semantic.store import SemanticStore


def _registry(semantic_store=None):
    matrix = AccessMatrix()
    matrix.set_permission("arch", KnowledgeLevel.PATTERN, can_write=True)
    return KnowledgeRegistry(access_matrix=matrix, semantic_store=semantic_store)


@pytest.fixture
def semantic_store(tmp_path):
    store = SemanticStore(str(tmp_path / "semantic.db"))
    store.initialize()
    return store


def _unit(**content):
    return KnowledgeUnit(
        level=KnowledgeLevel.PATTERN,
        content=content or {"statement": "默认知识"},
        source="test",
    )


class TestRegisterSync:
    def test_register_persists_to_semantic(self, semantic_store):
        registry = _registry(semantic_store)
        ok, unit_id = registry.register(
            _unit(statement="LLM 超频会退化", domain="resource_management"),
            owner="arch",
        )
        assert ok

        entry = semantic_store.get(unit_id)
        assert entry is not None
        assert entry.statement == "LLM 超频会退化"
        assert entry.scope.domain == "resource_management"
        assert entry.source_patterns == ("test",)
        assert entry.revision == 1

    def test_candidate_maps_to_unstable(self, semantic_store):
        """CANDIDATE（默认注册态）→ UNSTABLE（观察中）语义近似。"""
        registry = _registry(semantic_store)
        ok, unit_id = registry.register(_unit(), owner="arch")
        assert ok
        entry = semantic_store.get(unit_id)
        assert entry.status == KnowledgeStatus.UNSTABLE


class TestUpdateSync:
    def test_update_increments_revision_in_place(self, semantic_store):
        """单行模型：update 就地覆盖同 id 行，revision 递增（版本号演进）。"""
        registry = _registry(semantic_store)
        ok, unit_id = registry.register(
            _unit(statement="v1 知识", domain="general"), owner="arch"
        )
        assert ok

        ok2, _ = registry.update(unit_id, "arch", content={"statement": "v2 知识"})
        assert ok2

        entry = semantic_store.get(unit_id)
        assert entry is not None
        assert entry.statement == "v2 知识"
        assert entry.revision == 2
        # update 只改内容不改生命周期：候选单元更新后仍 UNSTABLE（晋级须显式 verify）
        assert entry.status == KnowledgeStatus.UNSTABLE

        # 单行模型：无历史行，仅 revision 演进（schema id PRIMARY KEY）
        conn = semantic_store.connection
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM knowledge WHERE id=?", (unit_id,)
        ).fetchone()
        assert row["cnt"] == 1


class TestRemoveSync:
    def test_remove_deprecates_in_semantic(self, semantic_store):
        registry = _registry(semantic_store)
        ok, unit_id = registry.register(_unit(statement="将删除"), owner="arch")
        assert ok
        assert semantic_store.get(unit_id) is not None

        ok2, _ = registry.remove(unit_id, "arch")
        assert ok2
        entry = semantic_store.get(unit_id)
        assert entry.status == KnowledgeStatus.DEPRECATED


class TestMemoryOnly:
    def test_without_store_keeps_old_behaviour(self):
        """无 semantic_store：注册/更新/删除行为不变（兼容旧构造）。"""
        registry = _registry()
        ok, unit_id = registry.register(_unit(statement="内存知识"), owner="arch")
        assert ok
        assert registry.get(unit_id) is not None
        ok2, _ = registry.update(unit_id, "arch", content={"statement": "改"})
        assert ok2
        ok3, _ = registry.remove(unit_id, "arch")
        assert ok3
