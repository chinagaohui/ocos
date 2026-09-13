"""P1-1 G3 — Worldview Experience → Recognition → Delta → Govern → W1 pipeline。

职责边界（G3 IMPLEMENTATION GO 授权）：
  - 只证明 OCOS 能因真实经历形成自己的 Worldview Delta（X→R→W1 可审计）。
  - 不证明行为改变（Y≠Z）、不进入 G4（Thinking 消费）、不跑 P1-1D。

覆盖率 Plan §5 V0–V8（含四项反伪造：V-pg provenance 门 / V-oc occurrences 推导
/ V-sg 语义结构门 / V-dk divergence 结构化）。

围绕 Human Gate 三条实现红线：
  H1  resolver 返回真实已有 Experience/Episode（identity ownership + evidence provenance）。
  H2  occurrences 数据流上完全无权威字段（篡改 occurrences_candidate 不改变 Recognition）。
  H3  G3 的 PASS 必须出现至少一次真正的结构性 W1（judgment/frame/stance 任一变化）。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ocos.self import self_evidence as _ev
from ocos.self.self_evidence import (
    ClaimKind,
    EvidenceObservation,
    S1Evidence,
    SelfDelta,
    SelfEvidenceError,
    SelfEvidencePipeline,
    SelfUpdateSource,
)
from ocos.self.self_state import SelfStateManager, SelfStateRejected
from ocos.self.self_types import (
    ContinuityKind,
    RecognitionType,
    SelfUpdateContract,
    StanceType,
    WorldViewJudgment,
)
from ocos.self.worldview import WorldView

AGENT = "g3-agent"
REAL_HASH = "hash-real-g3"


# ── 注入的真实 Experience 解析器（复用既有层协议，不新建存储）─────────────────
# H1：resolver 返回的是"已有真实 Episode"，非 caller 按 ID 构造的包装。
class _Episode:
    def __init__(self, eid, identity_ref, data_hash, n_obs):
        self.eid = eid
        self.identity_ref = identity_ref
        self.data_hash = data_hash
        self.associated_observations = list(range(n_obs))


class _Resolver:
    def __init__(self, episodes):
        self._eps = {e.eid: e for e in episodes}

    def resolve(self, episode_id):
        return self._eps.get(episode_id)


def _wv_evidence(data_hash, domain, expected, actual, trigger_episode,
                 occurrences_candidate=0) -> S1Evidence:
    """只给候选事实（domain/expected/actual/trigger_episode）—— 按契约 §3.2。"""
    meta = tuple(sorted({
        "domain": domain,
        "expected": expected,
        "actual": actual,
        "trigger_episode": trigger_episode,
        "occurrences_candidate": occurrences_candidate,
    }.items()))
    obs = EvidenceObservation(key="wv.experience", value=f"ep:{trigger_episode}", meta=meta)
    return S1Evidence(
        evidence_id=f"E-{uuid.uuid4().hex[:8]}",
        source="runtime",
        observed_at=datetime.now(timezone.utc),
        s1_version=1,
        s1_content_hash="sh",
        data_hash=data_hash,
        observations=(obs,),
    )


def _manager(tmp_path, db="g3.db"):
    return SelfStateManager(str(tmp_path / db))


def _wview_with_note(divergence_kind: str) -> WorldView:
    """构造一个仅含单域、note 标注 divergence 的既有世界观（类别改变检测用）。"""
    wv = WorldView()
    j = WorldViewJudgment(
        domain="rate", judgment="j", stance_type=StanceType.INTERPRETIVE,
        frame="f", confidence=0.7, note=f"divergence:{divergence_kind}",
        continuity=ContinuityKind.FIRST,
    )
    wv.declare(j)
    return wv


# ───────────────────────────── V0 反预制 Judgment ────────────────────────────


def test_v0_rejects_prefabricated_judgment():
    """输入携带 judgment/frame/stance_type/recognition_type/divergence(bool) → 守护 throw。"""
    for bad_field, value in [
        ("judgment", "x"), ("frame", "y"), ("stance_type", "normative"),
        ("recognition_type", "conflict"), ("divergence", True),
    ]:
        meta_items = {
            "domain": "tool", "expected": "exit 0", "actual": "exit 127",
            "trigger_episode": "EP-NOVEL", bad_field: value,
        }
        obs = EvidenceObservation(
            key="wv.experience", value="ep", meta=tuple(sorted(meta_items.items())))
        ev = S1Evidence(
            evidence_id="E-v0", source="runtime", observed_at=datetime.now(timezone.utc),
            s1_version=1, s1_content_hash="sh", data_hash=REAL_HASH, observations=(obs,))
        with pytest.raises(SelfEvidenceError):
            _ev.recognize(ev)


# ───────────────────────────── V-pg trigger provenance 门（C）─────────────────


def test_vpg_provenance_gate_fails_closed(tmp_path):
    """FAKE trigger / 归属不符 / 证据哈希不符 → fail-closed；真实记录 → 通过。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])

    # 1) 不存在（FAKE-001）→ 无 claim
    ev = _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "FAKE-001")
    assert _ev.recognize(ev, current=m.current, experience_resolver=resolver) == []
    with pytest.raises(_ev.UnrecognizableEvidence):
        SelfEvidencePipeline(m, experience_resolver=resolver).ingest(ev)

    # 2) 存在但归属不符（other-agent）→ fail-closed
    own = _Resolver([_Episode("EP-X", "other-agent", REAL_HASH, 3)])
    assert _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-X"),
                         current=m.current, experience_resolver=own) == []

    # 3) 存在且归属对但证据哈希不符 → fail-closed
    hashbad = _Resolver([_Episode("EP-Y", AGENT, "other-hash", 3)])
    assert _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-Y"),
                         current=m.current, experience_resolver=hashbad) == []

    # 4) 真实记录（≥3 观测）→ 凝结
    claims = _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"),
                           current=m.current, experience_resolver=resolver)
    assert len(claims) == 1 and claims[0].kind is ClaimKind.WORLDVIEW_JUDGMENT


# ───────────────────────────── V-oc occurrences 推导（B）─────────────────────


def test_voc_occurrences_derived_not_trusted(tmp_path):
    """occurrences_candidate 完全无权威：篡改它不改变 Recognition。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    low = _Resolver([_Episode("EP-LOW", AGENT, REAL_HASH, 2)])
    full = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])

    # 真实经过 =2（<3），candidate=100 → 仍不凝结
    assert _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-LOW", 100),
                         current=m.current, experience_resolver=low) == []

    # 真实经过 =3，无论 candidate 取 100 / 0 / 3 → 行为一致，occurrences=3（derived）
    for cand in (100, 0, 3):
        claims = _ev.recognize(
            _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL", cand),
            current=m.current, experience_resolver=full)
        assert len(claims) == 1, f"candidate={cand} 不得改变 Recognition"
        assert claims[0].meta["occurrences"] == 3       # 真实经历派生
        assert "occurrences_candidate" not in claims[0].meta  # 候选非数据流权威

    # 真实经过 =2，candidate=100 → 仍不凝结（fail-closed）
    assert _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-LOW", 100),
                         current=m.current, experience_resolver=low) == []


# ───────────────────────────── V-sg 语义结构门（A）───────────────────────────


def test_vsg_semantic_structure_gate(tmp_path):
    """W1≠W0 = 结构变化；CONFIRM 仅置信/证据/tick 变化 → 不产 W1 delta。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([
        _Episode("EP-NOVEL", AGENT, REAL_HASH, 3),
        _Episode("EP-CONFIRM", AGENT, REAL_HASH, 3),
        _Episode("EP-REFRAME", AGENT, REAL_HASH, 3),
    ])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)

    # 1) FIRST 形成 W0（NOVEL_PATTERN → 结构门 old=None 视为 True）
    first = _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL")
    assert len(pipeline.ingest(first)) == 1
    w0 = m.current.worldview.get("tool")
    assert w0 is not None and w0.continuity is ContinuityKind.FIRST
    v_after_first = m.version

    # 2) CONFIRM：judgment/frame/stance 未变（仅置信/证据/tick）→ 不产 W1、无 commit
    confirm = _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-CONFIRM")
    assert pipeline.ingest(confirm) == []
    assert m.version == v_after_first
    w1 = m.current.worldview.get("tool")
    assert w1.judgment == w0.judgment and w1.frame == w0.frame and w1.stance_type == w0.stance_type

    # 3) 结构变化（REFRAME，divergence 类别改变）→ 产 W1
    reframe = _wv_evidence(REAL_HASH, "tool", "file exists", "missing", "EP-REFRAME")
    assert len(pipeline.ingest(reframe)) == 1
    w2 = m.current.worldview.get("tool")
    assert w2.continuity is ContinuityKind.REPLACED
    assert (w2.judgment, w2.frame, w2.stance_type) != (w1.judgment, w1.frame, w1.stance_type)


# ───────────────────────────── V-dk divergence 结构化（D）────────────────────


def test_vdk_divergence_classifier_and_reframe_gate():
    """expected+actual → 确定性 divergence_kind；REFRAME 仅类别改变触发。"""
    assert _ev._classify_divergence("exit 0", "exit 127") == "unexpected_value"
    assert _ev._classify_divergence("file exists", "missing") == "missing"
    assert _ev._classify_divergence("exit 0", "exit 0") == "none"
    assert _ev._classify_divergence("100", "120") == "exceeds_bound"
    assert _ev._classify_divergence("7", "5") == "falls_short"

    rule = _ev.WorldViewRecognitionRule(_ev.WorldViewExperienceGate(_Resolver([])))
    prior = _wview_with_note("exceeds_bound").get("rate")
    # 类别改变（rating → existence）→ REFRAME
    assert rule._derive_recognition_type(prior, "missing") is RecognitionType.REFRAME
    # 同维反方向（exceeds_bound ↔ falls_short）→ CONFLICT
    assert rule._derive_recognition_type(prior, "falls_short") is RecognitionType.CONFLICT
    # 同类别同向 → CONFIRM
    assert rule._derive_recognition_type(prior, "exceeds_bound") is RecognitionType.CONFIRM
    # 无 prior → NOVEL_PATTERN
    assert rule._derive_recognition_type(None, "missing") is RecognitionType.NOVEL_PATTERN
    # 无差异但有 prior → CONFIRM
    assert rule._derive_recognition_type(prior, "none") is RecognitionType.CONFIRM


# ───────────────────────────── V1 / V2 Recognition 形成与规则推导 ─────────────


def test_v1_v2_recognition_formation_and_rule_derived(tmp_path):
    """真实解析经历(≥3) → claim；judgment/frame/stance/recognition 均来自规则。"""
    m = _manager(tmp_path, "v12.db")
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    ev = _wv_evidence(
        REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL", occurrences_candidate=999)

    claims = _ev.recognize(ev, current=m.current, experience_resolver=resolver)
    assert len(claims) == 1
    c = claims[0]
    assert c.kind is ClaimKind.WORLDVIEW_JUDGMENT
    assert c.target_component == "worldview" and c.key == "tool"
    assert c.evidence.evidence_id == ev.evidence_id

    # V2：这些字段必须来自规则，而非输入 meta
    assert "judgment" not in dict(ev.observations[0].meta)
    assert c.meta["recognition_type"] is RecognitionType.NOVEL_PATTERN
    assert c.meta["stance_type"] == "interpretive"
    assert c.meta["divergence_kind"] == "unexpected_value"
    assert c.meta["frame"] == "在这类 tool 场景，观测可能出现 unexpected_value 差异"
    assert c.statement == "对于 tool，同类情形可能出现 unexpected_value 偏离"
    assert c.meta["occurrences"] == 3
    assert "occurrences_candidate" not in c.meta


# ───────────────────────────── V3 Delta A→B ──────────────────────────────────


def test_v3_delta_a_to_b(tmp_path):
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    claims = _ev.recognize(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"),
                           current=m.current, experience_resolver=resolver)
    delta = _ev.delta_from_claim(m.current, claims[0])
    assert isinstance(delta, SelfDelta)
    assert delta.old_value is None                          # A
    assert isinstance(delta.new_value, WorldViewJudgment)   # B（结构化，非字符串）
    assert delta.target_component == "worldview" and delta.key == "tool"
    # apply 无异常并把 B 落入 candidate
    cand = m.build_candidate()
    _ev.apply_delta(cand, delta)
    assert cand.worldview.get("tool") is delta.new_value


# ───────────────────────────── V4 continuity 映射 ────────────────────────────


def test_v4_continuity_mapping():
    assert _ev._continuity_for(None, RecognitionType.NOVEL_PATTERN) is ContinuityKind.FIRST
    assert _ev._continuity_for("old", RecognitionType.NOVEL_PATTERN) is ContinuityKind.FIRST
    assert _ev._continuity_for("old", RecognitionType.CONFIRM) is ContinuityKind.DERIVED
    assert _ev._continuity_for("old", RecognitionType.CONFLICT) is ContinuityKind.REVISED
    assert _ev._continuity_for("old", RecognitionType.REFRAME) is ContinuityKind.REPLACED


# ───────────────────────────── V5 治理门 ─────────────────────────────────────


def test_v5_governance(tmp_path):
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    committed = pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"),
                                tick_id=3)
    assert len(committed) == 1
    last = m.current.update_history[-1]
    assert last.source is SelfUpdateSource.RUNTIME_OBSERVATION
    assert last.evidence_ids and last.claim_id

    v0 = m.version
    bad = SelfUpdateContract(source=SelfUpdateSource.EXTERNAL_AGENT, reason="x", tick_id=3,
                             fields_changed=("worldview",))
    with pytest.raises(SelfStateRejected):
        m.commit_change(m.build_candidate(), bad)
    assert m.version == v0


# ───────────────────────────── V6 W1 落地 + round-trip ───────────────────────


def test_v6_w1_lands_and_round_trip(tmp_path):
    db = str(tmp_path / "v6.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    SelfEvidencePipeline(m, experience_resolver=resolver).ingest(
        _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"))
    leaf = m.current.worldview.get("tool")
    assert isinstance(leaf, WorldViewJudgment)

    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    leaf2 = m2.current.worldview.get("tool")
    assert leaf2 is not None
    assert leaf2.judgment == leaf.judgment
    assert leaf2.evidence_ids == leaf.evidence_ids
    assert leaf2.continuity is ContinuityKind.FIRST


# ───────────────────────────── V7 因果链持久恢复 ─────────────────────────────


def test_v7_causal_chain_persist(tmp_path):
    db = str(tmp_path / "v7.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    SelfEvidencePipeline(m, experience_resolver=resolver).ingest(
        _wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127", "EP-NOVEL"))

    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    last = m2.current.update_history[-1]
    # 恢复 "X → R → Claim/Evidence → W1"
    assert last.trigger_experience_id == "EP-NOVEL"          # X（真实经历锚，非 FAKE）
    assert last.recognition_type == "novel_pattern"          # R
    assert last.evidence_ids and last.claim_id               # Evidence → Claim/Delta
    leaf = m2.current.worldview.get("tool")                   # W1
    assert leaf.continuity is ContinuityKind.FIRST
    assert leaf.evidence_ids
    assert leaf.claim_id
    # provenance 链每一环都有值（X→R→W1 可审计、可恢复）
    assert last.reason and leaf.note


# ───────────────────────────── V8 零影响回归 / 向后兼容 ──────────────────────


def test_v8_zero_impact_and_backward_compat(tmp_path):
    # (a) 非 worldview 路径不受影响：contract 不留 worldview 锚
    m = _manager(tmp_path)
    m.boot(AGENT)
    ev = _ev.capture_s1_snapshot({
        "version": 5, "content_hash": "h",
        "capabilities": [{"name": "shell", "attempts": 5, "success_rate": 0.8}],
        "failure_modes": []})
    SelfEvidencePipeline(m).ingest(ev)
    last = m.current.update_history[-1]
    assert last.recognition_type == "" and last.trigger_experience_id == ""

    # (b) SelfUpdateContract 新字段缺省向后兼容
    c = SelfUpdateContract(source=SelfUpdateSource.EXPERIENCE, reason="r", tick_id=1,
                           fields_changed=("knowledge_boundary",))
    assert c.recognition_type == "" and c.trigger_experience_id == ""
    # (c) 未形成 worldview 判断的 manager 可正常投影（序列化向后兼容）
    m2 = SelfStateManager(str(tmp_path / "v8b.db"))
    m2.boot(AGENT)
    proj = m2.accessor.project()
    assert isinstance(proj, (dict, str))
    assert m2.current.worldview is None
