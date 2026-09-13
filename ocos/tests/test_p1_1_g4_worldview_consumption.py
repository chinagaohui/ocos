"""P1-1 G4 — Worldview → Thinking Consumption：读取通道 + 真实消费判据。

职责边界（G4 IMPLEMENTATION GO 授权）：
  - 只证明 W1 → Thinking Input 合法读取通道建立，且读取改变 reasoning context。
  - 不证明智能提升 / 不进入 Decision 行为链 / 不跑 P1-1D（Y≠Z）。

覆盖率 Plan §5 G4-A~H（含 I1 diff 快照 / I2 source trace）：
  G4-A  读取点存在（get_committed_worldview / provider.build 含结构化块）
  G4-B  零影响基线（无 W1 → []；base self 逐字节不变）
  G4-C  只读消费（消费不改变 committed S2；adapter 无写路径）
  G4-D  input changed（结构 W1 → worldview 块 diff ≠ ∅ 且可归因；I1 快照）
  G4-E  output changed（确定性结构化 consumer：W1 存在/不存在 → 输出可区分）
  G4-F  防假消费（CONFIRM 仅置信/证据 → 块不变 → input 不变）
  G4-G  回归（消费后既有 accessor 方法 brief/render/project 仍正常）
  G4-H  Authority Boundary（修改 ThinkingContext 不反向改变 WorldView/Claim/Delta/Govern）

W1 一律经 G3 frozen 链（SelfEvidencePipeline + 真实 Experience resolver）形成，
保证 G4 消费的是"已 Govern 的 committed W1"，而非测试手造对象。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ocos.self.self_evidence import (
    EvidenceObservation,
    S1Evidence,
    SelfEvidencePipeline,
)
from ocos.self.self_state import SelfStateManager
from ocos.self.worldview_read_adapter import (
    ThinkingContextProvider,
    WorldViewContextBlock,
    WorldViewReadAdapter,
)

AGENT = "g4-agent"
REAL_HASH = "hash-real-g4"

# G4-E 结构化 consumer 允许的输出字段（禁止 interpretation 字段：P1-1D 边界）。
_ALLOWED_OUTPUT = {"risk_assessment", "rationale", "worldview_used"}


# ── 注入的真实 Experience 解析器（与 G3 同协议，保证 W1 来自真实链）──────────────


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


def _wv_evidence(data_hash, domain, expected, actual, trigger_episode) -> S1Evidence:
    """只给候选事实（domain/expected/actual/trigger_episode）—— 契约 §3.2。"""
    meta = tuple(sorted({
        "domain": domain,
        "expected": expected,
        "actual": actual,
        "trigger_episode": trigger_episode,
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


def _manager(tmp_path):
    return SelfStateManager(str(tmp_path / "g4.db"))


def _structured_consumer(context: dict) -> dict:
    """G4-E 确定性结构化 reasoning consumer（测试内，非生产决策逻辑）。

    只消费 Thinking Input Context 中的 worldview 块字段，产出结构化判定；
    禁止产出 recommended_action / strategy / decision（P1-1D 边界）。
    """
    blocks = context.get("worldview") or []
    if not blocks:
        return {
            "risk_assessment": "unknown",
            "rationale": "base self only",
            "worldview_used": None,
        }
    b = blocks[0]
    risk = "high" if b["confidence"] >= 0.6 else "moderate"
    return {
        "risk_assessment": risk,
        "rationale": f"worldview.frame({b['frame']}) for {b['domain']}",
        "worldview_used": {
            "domain": b["domain"],
            "claim_id": b["claim_id"],
            "evidence_ids": b["evidence_ids"],
        },
    }


# ───────────────────────────── G4-A 读取点存在 ───────────────────────────────


def test_g4a_read_path_contains_worldview_block(tmp_path):
    """W1 存在 → get_committed_worldview() / provider.build() 含结构化块。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1

    acc = m.accessor
    blocks = acc.get_committed_worldview()
    assert len(blocks) == 1
    block = blocks[0]
    for key in WorldViewContextBlock.FIELDS:
        assert key in block, f"块缺字段 {key}"
    assert block["type"] == "worldview"
    assert block["domain"] == "tool"
    assert block["source"] == "committed_self_projection"
    # I2：溯源锚保留
    assert block["claim_id"]
    assert block["evidence_ids"]

    provider = ThinkingContextProvider(acc)
    ctx = provider.build(base_self_context="base-self")
    assert ctx["worldview"] == blocks
    assert ctx["self"] == "base-self"


# ───────────────────────────── G4-B 零影响基线 ───────────────────────────────


def test_g4b_zero_impact_baseline(tmp_path):
    """无 W1 → []; base self 段逐字节一致（G1 T6b 语义保持）。"""
    m = _manager(tmp_path)
    m.boot(AGENT)

    acc = m.accessor
    assert acc.get_committed_worldview() == []

    provider = ThinkingContextProvider(acc)
    base = "SELF-CONTEXT-v1: capabilities=[shell] focus=[]"
    ctx = provider.build(base_self_context=base)
    assert ctx["worldview"] == []
    assert ctx["self"] == base  # 逐字节一致


# ───────────────────────────── G4-C 只读消费 ─────────────────────────────────


def test_g4c_readonly_consumption(tmp_path):
    """消费不改变 committed S2（version/hash/update_history/worldview 全等）；无写路径。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1

    before = m.current
    before_version = m.version
    before_hash = acc_hash(before)
    before_history = list(before.update_history or [])
    before_wv = dict(before.worldview.judgments)

    adapter = WorldViewReadAdapter(m.accessor)
    provider = ThinkingContextProvider(m.accessor)
    assert len(adapter.consume()) == 1
    assert provider.build(base_self_context="x")["worldview"]

    after = m.current
    assert m.version == before_version
    assert acc_hash(after) == before_hash
    assert list(after.update_history or []) == before_history
    assert dict(after.worldview.judgments) == before_wv

    # 无写路径：只读组件不暴露任何 mutation 方法
    for cls in (WorldViewReadAdapter, ThinkingContextProvider):
        for method in ("update", "declare", "commit", "replace", "apply"):
            assert not hasattr(cls, method), f"{cls.__name__} 不得暴露 {method}"


def acc_hash(s) -> str:
    from ocos.self.self_state import serialize_state

    _, h = serialize_state(s)
    return h


# ───────────────────────────── G4-D input changed（I1 diff 快照）─────────────


def test_g4d_input_changed_with_snapshots(tmp_path):
    """结构 W1（FIRST/REFRAME）→ worldview 块 diff ≠ ∅ 且可归因；保存快照。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([
        _Episode("EP-NOVEL", AGENT, REAL_HASH, 3),
        _Episode("EP-REFRAME", AGENT, REAL_HASH, 3),
    ])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    provider = ThinkingContextProvider(m.accessor)

    # I1: W0 input snapshot（FIRST 前）
    w0_blocks = list(provider.build(base_self_context="base")["worldview"])
    assert w0_blocks == []

    # FIRST 形成 W1（NOVEL_PATTERN：无 prior → 结构变化）
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1
    w1_blocks = provider.build(base_self_context="base")["worldview"]
    assert w1_blocks != w0_blocks  # input diff ≠ ∅
    assert len(w1_blocks) == 1
    key_tuple = _canonical_key(w1_blocks[0])
    assert key_tuple[0] == "tool"

    # 结构 REFRAME（divergence 类别改变 → frame 变化）→ 二次 diff 可归因到 frame
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "file exists", "missing",
                                            "EP-REFRAME"))) == 1
    w2_blocks = provider.build(base_self_context="base")["worldview"]
    assert w2_blocks != w1_blocks
    assert w2_blocks[0]["frame"] != w1_blocks[0]["frame"]  # 归因：frame 变化
    assert w2_blocks[0]["continuity"] == "replaced"

    # I1: canonical diff 快照可审计（关键字段齐全）
    assert _canonical_key(w2_blocks[0])[0] == _canonical_key(w1_blocks[0])[0]  # 同域
    assert len(_canonical_key(w2_blocks[0])) == 7
    # ^ domain+judgment+frame+stance_type+continuity+claim_id+confidence


def _canonical_key(block: dict) -> tuple:
    """I1 canonical diff 键：diff 采集的稳定字段集。"""
    return (
        block["domain"],
        block["judgment"],
        block["frame"],
        block["stance_type"],
        block["continuity"],
        block["claim_id"],
        block["confidence"],
    )


# ───────────────────────────── G4-E output changed ───────────────────────────


def test_g4e_output_changed_attributable(tmp_path):
    """同输入（同 base self）：W1 不存在 vs 存在 → 结构化输出可区分且归因。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    provider = ThinkingContextProvider(m.accessor)

    base = "SELF-v1"
    baseline_ctx = provider.build(base_self_context=base)
    baseline_out = _structured_consumer(baseline_ctx)
    assert baseline_out["risk_assessment"] == "unknown"
    assert baseline_out["worldview_used"] is None

    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1
    wv_ctx = provider.build(base_self_context=base)
    assert wv_ctx["self"] == baseline_ctx["self"]  # 唯一变化 = worldview 块
    wv_out = _structured_consumer(wv_ctx)

    assert wv_out != baseline_out  # output changed
    assert wv_out["worldview_used"] is not None
    block = wv_ctx["worldview"][0]
    assert wv_out["worldview_used"]["claim_id"] == block["claim_id"]  # 归因
    assert wv_out["worldview_used"]["evidence_ids"] == block["evidence_ids"]
    assert wv_out["worldview_used"]["domain"] == "tool"

    # 输出字段白名单：不产出 recommended_action/strategy/decision（P1-1D 边界）
    assert set(wv_out) <= _ALLOWED_OUTPUT


# ───────────────────────────── G4-F 防假消费 ─────────────────────────────────


def test_g4f_confirm_does_not_change_input(tmp_path):
    """CONFIRM（仅置信/证据/tick）→ 块不变 → Thinking input 不变。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([
        _Episode("EP-NOVEL", AGENT, REAL_HASH, 3),
        _Episode("EP-CONFIRM", AGENT, REAL_HASH, 3),
    ])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    provider = ThinkingContextProvider(m.accessor)

    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1
    w1_blocks = provider.build(base_self_context="base")["worldview"]
    v_after_first = m.version

    # CONFIRM：无结构变化 → 不产 W1、不 commit → 块逐字段不变
    assert pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                        "EP-CONFIRM")) == []
    assert m.version == v_after_first
    w2_blocks = provider.build(base_self_context="base")["worldview"]
    assert w2_blocks == w1_blocks  # input 不变


# ───────────────────────────── G4-G 回归（消费点）────────────────────────────


def test_g4g_existing_accessor_methods_intact(tmp_path):
    """消费路径存在时，既有 accessor 方法 brief/render/project 仍正常。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1

    acc = m.accessor
    # 消费
    assert ThinkingContextProvider(acc).build(base_self_context="b")["worldview"]
    # 既有方法不受影响
    assert "SelfState v" in acc.render()
    assert isinstance(acc.brief(), str)
    assert isinstance(acc.project(), dict)
    assert acc.version >= 2


# ───────────────────────────── G4-H Authority Boundary ───────────────────────


def test_g4h_thinking_cannot_mutate_self(tmp_path):
    """修改 ThinkingContext/消费产物不反向改变 WorldView/Claim/Delta/Govern。"""
    m = _manager(tmp_path)
    m.boot(AGENT)
    resolver = _Resolver([_Episode("EP-NOVEL", AGENT, REAL_HASH, 3)])
    pipeline = SelfEvidencePipeline(m, experience_resolver=resolver)
    assert len(pipeline.ingest(_wv_evidence(REAL_HASH, "tool", "exit 0", "exit 127",
                                            "EP-NOVEL"))) == 1

    before_version = m.version
    before_hash = acc_hash(m.current)
    before_history = list(m.current.update_history or [])
    before_wv = dict(m.current.worldview.judgments)

    # 模拟 Thinking 消费并"篡改"消费产物（不应有任何回写能力）
    provider = ThinkingContextProvider(m.accessor)
    ctx = provider.build(base_self_context="base")
    ctx["worldview"] = []          # 篡改 input context
    ctx["worldview"] = [{"domain": "evil", "judgment": "hacked"}]
    try:
        _ = _structured_consumer(ctx)  # 任意消费（可能因缺字段报错，无妨）
    except KeyError:
        pass

    after_version = m.version
    after_hash = acc_hash(m.current)
    after_history = list(m.current.update_history or [])
    after_wv = dict(m.current.worldview.judgments)

    assert after_version == before_version
    assert after_hash == before_hash
    assert after_history == before_history
    assert after_wv == before_wv
    assert m.current.worldview.get("evil") is None  # 没有反向注入
