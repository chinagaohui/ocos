"""P1-1 G1 — Worldview Physical Seat 验证（T1–T9 矩阵，G1 IMPLEMENTATION_PLAN §5）。

对应验证矩阵：
    T1   worldview canonical round-trip（含 judgment 全字段 + hash 一致）
    T2   旧状态向后兼容（无 worldview 键 → worldview=None，hash 校验通过）
    T3   注册表完整性（_TYPE_REGISTRY 含 WorldView/WorldViewJudgment/StanceType/ContinuityKind）
    T4   白名单（update("worldview") True；假组件 False；identity_ref False）
    T5   治理门（EXTERNAL_AGENT source 更新 worldview 被拒：update False / commit_change 抛 SelfStateRejected）
    T6a  project() 自动包含 worldview 结构化段
    T6b  render()/brief() 逐字节不变（worldview 存在与否输出零差异；不泄漏世界观文本）
    T7   component_consumption("worldview") 形成正确 manifest
    T8   create_self_model → worldview None；initialize_empty_components → WorldView() 实例
    T9   全量回归（命令级运行既有套件，非本文件）

设计前提（G1 Shape Design §3/§6）：
    - StanceType/ContinuityKind/WorldViewJudgment 为 frozen/Enum 叶子，canonical 序列化泛化兼容
    - _TYPE_REGISTRY 注册 = 反序列化生死线
    - render()/brief() 属 G4 范畴，G1 不碰（本文件以字节级断言守边界）
"""

from __future__ import annotations

import json

import pytest

from ocos.self import (
    ContinuityKind,
    SelfModel,
    StanceType,
    WorldView,
    WorldViewJudgment,
    create_self_model,
    initialize_empty_components,
)
from ocos.self.self_model import update_worldview
from ocos.self.self_state import (
    SelfStateManager,
    SelfStateRejected,
    SelfStateStore,
    _TYPE_REGISTRY,
    deserialize_state,
    serialize_state,
)
from ocos.self.self_types import SelfUpdateContract, SelfUpdateSource

AGENT = "g1-test-agent"


class _Anchor:
    def __init__(self, agent_id: str = AGENT):
        self._id = agent_id

    def get_identity_id(self) -> str:
        return self._id


def _wv(claim_id: str = "cl-g1-1", evidence_ids=("ev-1",), tick: int = 10) -> WorldView:
    """构造含一条 judgment 的 WorldView。"""
    wv = WorldView()
    wv.declare(WorldViewJudgment(
        domain="task_execution",
        judgment="fallible tools need verification before trust",
        stance_type=StanceType.NORMATIVE,
        frame="verify-before-trust",
        confidence=0.8,
        evidence_ids=tuple(evidence_ids),
        source="reflection",
        claim_id=claim_id,
        created_tick=tick,
        last_updated_tick=tick,
        continuity=ContinuityKind.FIRST,
        note="formed after first tool failure",
    ))
    return wv


def _wv_contract(claim_id: str = "cl-g1-1", src: SelfUpdateSource = SelfUpdateSource.REFLECTION,
                 impact: float = 0.05):
    return SelfUpdateContract(
        source=src,
        reason="worldview update",
        tick_id=10,
        fields_changed=("worldview",),
        confidence_impact=impact,
        claim_id=claim_id,
        evidence_ids=("ev-1",),
    )


def _commit_worldview(db: str, claim_id: str = "cl-g1-1") -> SelfStateManager:
    """boot + 提交含 worldview 的 committed 态，返回 manager。"""
    m = SelfStateManager(db)
    m.boot(AGENT)
    c = m.build_candidate()
    c.worldview = _wv(claim_id=claim_id)
    m.commit_change(c, _wv_contract(claim_id=claim_id))
    return m


# ═══════════════════════════════════════════════════════════════════════════════
# T1 — worldview canonical round-trip
# ═══════════════════════════════════════════════════════════════════════════════


def test_t1_worldview_canonical_round_trip(tmp_path):
    db = str(tmp_path / "t1.db")
    m = _commit_worldview(db)
    assert m.version == 2

    # serialize → deserialize：全字段一致
    state_json, h1 = serialize_state(m.current)
    restored = deserialize_state(state_json, h1)
    assert restored.worldview is not None
    assert restored.worldview.count == 1
    assert restored.worldview.overall_confidence == 0.8

    j = restored.worldview.get("task_execution")
    assert j is not None
    assert j.judgment == "fallible tools need verification before trust"
    assert j.stance_type == StanceType.NORMATIVE
    assert j.continuity == ContinuityKind.FIRST
    assert j.confidence == 0.8
    assert j.evidence_ids == ("ev-1",)
    assert j.source == "reflection"
    assert j.claim_id == "cl-g1-1"
    assert j.created_tick == 10
    assert j.last_updated_tick == 10
    assert j.frame == "verify-before-trust"
    assert j.note == "formed after first tool failure"

    # reload 路径 hash 一致（同一提交态）
    reloaded = SelfStateStore(db).load(AGENT)
    _, h2 = serialize_state(reloaded)
    assert h1 == h2
    assert reloaded.worldview.get("task_execution").claim_id == "cl-g1-1"


# ═══════════════════════════════════════════════════════════════════════════════
# T2 — 旧状态向后兼容（无 worldview 键 → None）
# ═══════════════════════════════════════════════════════════════════════════════


def test_t2_old_state_without_worldview_key_loads_none(tmp_path):
    db = str(tmp_path / "t2.db")
    m = SelfStateManager(db)
    m.boot(AGENT)

    # 模拟旧格式：从 canonical 删除 worldview 键（旧代码产生的 state_json 无此键）
    state_json, _ = serialize_state(m.current)
    canonical = json.loads(state_json)
    assert "worldview" in canonical
    del canonical["worldview"]
    old_json = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))

    # 无 worldview 键 → _rebuild 经 default 回退 None；hash 校验通过
    rebuilt = deserialize_state(old_json, _hash_of(old_json))
    assert rebuilt.worldview is None
    assert rebuilt.identity_ref == AGENT


def _hash_of(state_json: str) -> str:
    import hashlib

    return hashlib.sha256(state_json.encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# T3 — 注册表完整性（反序列化生死线）
# ═══════════════════════════════════════════════════════════════════════════════


def test_t3_registry_contains_worldview_types():
    for name in ("WorldView", "WorldViewJudgment", "StanceType", "ContinuityKind"):
        assert name in _TYPE_REGISTRY, f"missing registry entry: {name}"


def test_t3_registry_rebuild_of_new_types():
    """4 新类型的 canonical `_rebuild` 成功（反序列化链路不抛 unknown type tag）。"""
    wv = _wv()
    state_json, h = serialize_state(SelfModel(identity_ref=AGENT, worldview=wv))
    rebuilt = deserialize_state(state_json, h)
    assert rebuilt.worldview.count == 1
    assert rebuilt.worldview.get("task_execution").stance_type == StanceType.NORMATIVE
    assert rebuilt.worldview.get("task_execution").continuity == ContinuityKind.FIRST


# ═══════════════════════════════════════════════════════════════════════════════
# T4 — valid_components 白名单
# ═══════════════════════════════════════════════════════════════════════════════


def test_t4_whitelist_worldview_ok_fake_and_identity_ref_rejected():
    sm = create_self_model(_Anchor())
    contract = SelfUpdateContract(
        source=SelfUpdateSource.REFLECTION,
        reason="wv",
        tick_id=1,
        fields_changed=("worldview",),
    )
    assert sm.update(contract, "worldview", WorldView()) is True
    assert sm.has_worldview

    # 假组件仍拒绝
    fake = SelfUpdateContract(
        source=SelfUpdateSource.REFLECTION,
        reason="x",
        tick_id=1,
        fields_changed=("fake_component",),
    )
    assert sm.update(fake, "fake_component", "x") is False

    # identity_ref 仍不可写
    assert sm.update(contract, "identity_ref", "other-agent") is False
    assert sm.identity_ref == AGENT


# ═══════════════════════════════════════════════════════════════════════════════
# T5 — 治理门（EXTERNAL_AGENT 被拒）
# ═══════════════════════════════════════════════════════════════════════════════


def test_t5_governance_rejects_external_agent_for_worldview(tmp_path):
    # SelfModel.update 路径
    sm = create_self_model(_Anchor())
    bad = SelfUpdateContract(
        source=SelfUpdateSource.EXTERNAL_AGENT,
        reason="x",
        tick_id=1,
        fields_changed=("worldview",),
    )
    assert sm.update(bad, "worldview", WorldView()) is False
    assert not sm.has_worldview

    # commit_change 路径：治理门抛 SelfStateRejected
    db = str(tmp_path / "t5.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    c = m.build_candidate()
    c.worldview = _wv()
    with pytest.raises(SelfStateRejected):
        m.commit_change(c, bad)
    assert m.current.worldview is None  # 无半状态落库


# ═══════════════════════════════════════════════════════════════════════════════
# T6a — project() 自动包含 worldview
# ═══════════════════════════════════════════════════════════════════════════════


def test_t6a_project_contains_worldview(tmp_path):
    db = str(tmp_path / "t6a.db")
    m = _commit_worldview(db)
    proj = m.accessor.project()
    assert "worldview" in proj
    wv_node = proj["worldview"]
    assert wv_node["__type"] == "WorldView"
    assert "task_execution" in wv_node["judgments"]
    j_node = wv_node["judgments"]["task_execution"]
    assert j_node["stance_type"] == "normative"
    assert j_node["continuity"] == "first"
    assert j_node["claim_id"] == "cl-g1-1"


# ═══════════════════════════════════════════════════════════════════════════════
# T6b — render()/brief() 逐字节不变（worldview 存在与否零差异）
# ═══════════════════════════════════════════════════════════════════════════════


def _base_state(db: str) -> SelfStateManager:
    """boot + 一次 cognitive 变更（与世界观无关的确定性基底）。"""
    m = SelfStateManager(db)
    m.boot(AGENT)
    c = m.build_candidate()
    c.cognitive_state.active_focus = "focus-x"
    m.commit_change(
        c,
        SelfUpdateContract(
            source=SelfUpdateSource.REFLECTION,
            reason="cognitive change",
            tick_id=5,
            fields_changed=("cognitive_state",),
            confidence_impact=0.05,
        ),
    )
    return m


def test_t6b_render_brief_byte_identical_with_worldview(tmp_path):
    db_no = str(tmp_path / "t6b_no.db")
    db_wv = str(tmp_path / "t6b_wv.db")

    # 状态 A：无 worldview（v2）
    m_no = _base_state(db_no)
    r_no = m_no.accessor.render()
    b_no = m_no.accessor.brief()

    # 状态 B：与 A 完全同基底，仅额外提交 worldview（v3），confidence 不受影响
    m_wv = _base_state(db_wv)
    c = m_wv.build_candidate()
    c.worldview = _wv(claim_id="cl-g1-1")
    m_wv.commit_change(c, _wv_contract(impact=0.0))  # impact=0 使置信度与 A 一致
    r_wv = m_wv.accessor.render()
    b_wv = m_wv.accessor.brief()

    # 版本 token 归一化后 render 逐字节一致（唯一差异 = 版本号）
    assert r_wv.replace("v3", "v2", 1) == r_no
    # brief() 不含版本/置信度 → 直接逐字节一致
    assert b_wv == b_no

    # 边界：worldview 文本绝不泄漏进 render/brief（G1 不接线 prompt 槽位）
    assert "WorldView" not in r_wv
    assert "task_execution" not in r_wv
    assert "WorldView" not in b_wv


# ═══════════════════════════════════════════════════════════════════════════════
# T7 — component_consumption("worldview") manifest
# ═══════════════════════════════════════════════════════════════════════════════


def test_t7_consumption_manifest_for_worldview(tmp_path):
    db = str(tmp_path / "t7.db")
    m = _commit_worldview(db, claim_id="cl-g1-7")
    manifest = m.accessor.component_consumption("worldview")

    assert manifest is not None
    assert manifest["claim_id"] == "cl-g1-7"
    assert manifest["delta_id"] == "cl-g1-7"
    assert manifest["evidence_ids"] == ["ev-1"]
    assert manifest["target_component"] == "worldview"
    assert manifest["self_version"] == 2
    assert manifest["content_hash"]


def test_t7_consumption_none_without_claim(tmp_path):
    db = str(tmp_path / "t7b.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    c = m.build_candidate()
    c.worldview = _wv(claim_id="")  # 无 claim_id 的 contract 不算可归因消费
    m.commit_change(c, _wv_contract(claim_id=""))
    assert m.accessor.component_consumption("worldview") is None


# ═══════════════════════════════════════════════════════════════════════════════
# T8 — create/init 行为
# ═══════════════════════════════════════════════════════════════════════════════


def test_t8_create_self_model_worldview_none():
    sm = create_self_model(_Anchor())
    assert sm.worldview is None
    assert not sm.has_worldview
    assert sm.components_loaded == 0


def test_t8_initialize_empty_components_creates_worldview():
    sm = create_self_model(_Anchor())
    sm = initialize_empty_components(sm)
    assert sm.worldview is not None
    assert isinstance(sm.worldview, WorldView)
    assert sm.worldview.count == 0
    assert sm.has_worldview
    # D1 ACCEPT: components_loaded 计入 worldview（6 组件全初始化）
    assert sm.components_loaded == 6


# ═══════════════════════════════════════════════════════════════════════════════
# T8+ — update_worldview 助手（S1-free 更新路径）
# ═══════════════════════════════════════════════════════════════════════════════


def test_t8_update_worldview_helper():
    sm = create_self_model(_Anchor())
    ok = update_worldview(
        sm,
        _wv(),
        SelfUpdateSource.RUNTIME_OBSERVATION,
        "observed world structure",
        10,
    )
    assert ok is True
    assert sm.worldview.count == 1
    # 合同入账 update_history（provenance 可追溯）
    assert sm.update_history[-1].fields_changed == ("worldview",)
