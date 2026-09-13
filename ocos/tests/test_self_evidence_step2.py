"""P0-1 Step 2 forensic tests — S1 Evidence → Claim → Delta → governed S2 commit。

验收重点（仅 Step 2 边界，不证明成长发生，只证明链路成立）：
    E1  S1 产生的是 Evidence 而非 SelfState（结构化装箱，不碰 S2）
    E2  Evidence → Claim（含小样本准入门槛，避免自动成长）
    E3  Claim → Delta 显式 A→B
    E4  Delta 经 governed commit：version 增 / hash 变 / provenance+evidence anchor 可追溯
    E5  无 S2 commit 时，S1 变化/新 Evidence 不改变 Thinking 消费的 Self（延伸 T8）
    E6  Thinking 只能看到提交后的 S2 projection
    E7  治理门：绕过/非法来源被拒，版本不变
    E8  provenance 跨 reload 存活（证据锚可追溯）
"""

from __future__ import annotations

import json

import pytest

from ocos.self.self_state import SelfStateManager, SelfStateRejected
from ocos.self.self_evidence import (
    ClaimKind,
    SelfDelta,
    SelfEvidencePipeline,
    SelfUpdateSource,
    apply_delta,
    capture_s1_snapshot,
    delta_from_claim,
    recognize,
)
from ocos.storage.connection import get_connection
from ocos.storage.schema import TABLE_SELF_STATE
from ocos.self.self_types import SelfUpdateContract
from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary

AGENT = "test-agent-02"


def _snapshot(version: int = 3, capabilities=None, failure_modes=None) -> dict:
    return {
        "version": version,
        "content_hash": f"s1hash-v{version}",
        "capabilities": (
            capabilities
            if capabilities is not None
            else [
                {"name": "shell", "attempts": 5, "success_rate": 0.8},
                {"name": "filesystem", "attempts": 2, "success_rate": 1.0},  # 小样本
            ]
        ),
        "failure_modes": (
            failure_modes
            if failure_modes is not None
            else [{"cause": "dependency_missing", "count": 3}]
        ),
        "personality": {"reply_style": "详细"},
        "focus": [],
    }


def _manager(tmp_path):
    m = SelfStateManager(str(tmp_path / "s2.db"))
    m.boot(AGENT)
    return m


# ── E1 S1 产物是 Evidence 而非 SelfState ─────────────────────────────────────


def test_e1_s1_evidence_is_not_selfstate(tmp_path):
    m = _manager(tmp_path)
    # 捕获 S1 快照 → 只得到 Evidence 对象，不触碰 S2 库
    ev = capture_s1_snapshot(_snapshot())
    assert ev is not None
    assert ev.s1_version == 3
    assert ev.s1_content_hash == "s1hash-v3"
    assert ev.data_hash
    assert not ev.is_empty

    # 仅构造 Evidence 不具备任何写 S2 的能力
    assert not hasattr(ev, "commit")
    assert m.version == 1, "仅捕获 Evidence 不会改变 S2"
    rows = get_connection(m._store._db_path).execute(
        f"SELECT version FROM {TABLE_SELF_STATE} WHERE identity_ref=?", (AGENT,)
    ).fetchone()
    assert rows["version"] == 1

    # 小样本能力(attempts=2)在 Evidence 里如实保留为观测，但识别阶段决定是否成 Claim
    caps = [o for o in ev.observations if o.key == "s1.capability"]
    assert any(o.value == "filesystem" for o in caps)


# ── E2 Evidence → Claim（含准入门槛）─────────────────────────────────────────


def test_e2_evidence_to_claim_with_gate(tmp_path):
    m = _manager(tmp_path)
    ev = capture_s1_snapshot(_snapshot(version=4))
    claims = recognize(ev)

    # shell(5次, 0.8) → CAPABILITY_KNOWN；filesystem(2次) 因小样本被门槛挡掉
    kinds = {c.key: c.kind for c in claims}
    assert kinds.get("shell") is ClaimKind.CAPABILITY_KNOWN
    assert "filesystem" not in kinds, "小样本能力不得形成 Claim（未经准入门槛）"
    assert any(c.kind is ClaimKind.FAILURE_PATTERN for c in claims)
    # 每个 Claim 都锚定到 Evidence
    for c in claims:
        assert c.evidence.evidence_id == ev.evidence_id
    # 空快照无可识别观测 → capture 返回 None（无 Evidence，自然无 Claim）
    assert capture_s1_snapshot({"version": 1, "capabilities": [], "failure_modes": []}) is None


# ── E3 Claim → Delta 显式 A→B ────────────────────────────────────────────────


def test_e3_claim_to_delta_a_to_b(tmp_path):
    m = _manager(tmp_path)
    ev = capture_s1_snapshot(_snapshot())
    claim = next(c for c in recognize(ev) if c.kind is ClaimKind.CAPABILITY_KNOWN)
    delta = delta_from_claim(m.current, claim)

    assert isinstance(delta, SelfDelta)
    assert delta.old_value is None          # A：committed S2 本无 shell 认知
    assert delta.new_value is not None      # B：新的 CapabilityStatement
    assert delta.old_value != delta.new_value
    assert delta.new_value.name == "shell"
    assert delta.new_value.available is True
    assert delta.target_component == "capability_awareness"

    # apply 到 candidate 后 B 真实落入，A 被替换
    cand = m.build_candidate()
    apply_delta(cand, delta)
    assert cand.capability_awareness.get("shell") == delta.new_value


# ── E4 governed commit：version/hash/provenance ───────────────────────────────


def test_e4_governed_commit_traceable(tmp_path):
    m = _manager(tmp_path)
    ev = capture_s1_snapshot(_snapshot(version=5))
    pipeline = SelfEvidencePipeline(m)

    v_before, h_before = m.version, m.accessor.content_hash
    committed = pipeline.ingest(ev, tick_id=7)

    assert committed, "至少一个 Claim 被治理通过并提交"
    assert m.version == v_before + len(committed)
    assert m.accessor.content_hash != h_before, "提交后 content_hash 必须改变"
    assert m.current.updated_at >= m.current.created_at

    # Thinking 只看到提交后 projection
    caps = m.current.capability_awareness
    assert caps.get("shell") is not None and caps.get("shell").available

    # update_history 有 provenance / evidence anchor 可追溯
    last = m.current.update_history[-1]
    assert isinstance(last, SelfUpdateContract)
    assert last.evidence_ids == (ev.evidence_id,)
    assert last.claim_id
    assert last.source is SelfUpdateSource.RUNTIME_OBSERVATION


# ── E5 无 commit = S1 变化不改变 Thinking 消费的 Self（延伸 T8）───────────────


def test_e5_no_commit_no_self_change(tmp_path):
    m = _manager(tmp_path)
    # 先有一次 committed v2（B）
    ev_b = capture_s1_snapshot(
        _snapshot(version=5, capabilities=[{"name": "shell", "attempts": 5, "success_rate": 0.8}]))
    SelfEvidencePipeline(m).ingest(ev_b)  # v2 = B
    h_b, v_b = m.accessor.content_hash, m.version

    # S1 后来变化（新快照 version=6，新增能力），但**不执行 ingest** → 仅构造 Evidence
    ev_c = capture_s1_snapshot(
        _snapshot(version=6, capabilities=[
            {"name": "shell", "attempts": 6, "success_rate": 0.9},
            {"name": "code_executor", "attempts": 4, "success_rate": 1.0},
        ], failure_modes=[])
    )
    assert ev_c.s1_version == 6
    # 未 commit → S2 与 Thinking 消费的 projection 完全不变
    assert m.version == v_b
    assert m.accessor.content_hash == h_b
    assert m.current.capability_awareness.get("code_executor") is None, (
        "未 commit 的新证据永远不进入 S2"
    )
    assert "code_executor" not in m.accessor.render()


# ── E6 Thinking 只能看到提交后 S2 projection ──────────────────────────────────


def test_e6_thinking_only_sees_committed(tmp_path):
    m = _manager(tmp_path)
    ev = capture_s1_snapshot(_snapshot(version=5,
        capabilities=[{"name": "shell", "attempts": 5, "success_rate": 0.8}],
        failure_modes=[]))
    pipeline = SelfEvidencePipeline(m)

    accessor_before = m.accessor.project()
    # candidate 构建是深拷贝，不会污染 committed
    cand = m.build_candidate()
    apply_delta(cand, delta_from_claim(m.current, recognize(ev)[0]))
    assert m.accessor.project() == accessor_before, "candidate 未提交不得出现在 projection"

    pipeline.ingest(ev)  # commit 后才可见
    proj = m.accessor.project()
    assert "shell" in json.dumps(proj if not isinstance(proj, str) else proj)
    assert len(recognize(ev)) == 1
    assert m.accessor.version == 2


# ── E7 治理门：非法来源被拒、版本不变 ────────────────────────────────────────


def test_e7_governance_gate(tmp_path):
    m = _manager(tmp_path)
    v0, h0 = m.version, m.accessor.content_hash
    # 绕过 pipeline 直接用非法来源提交 → 治理门拒绝
    bad = SelfUpdateContract(
        source=SelfUpdateSource.EXTERNAL_AGENT, reason="bypass", tick_id=1,
        fields_changed=("cognitive_state",),
    )
    with pytest.raises(SelfStateRejected):
        m.commit_change(m.build_candidate(), bad)
    assert m.version == v0 and m.accessor.content_hash == h0


# ── E8 provenance 跨 reload 存活 ──────────────────────────────────────────────


def test_e8_provenance_survives_reload(tmp_path):
    db = str(tmp_path / "e8.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    ev = capture_s1_snapshot(_snapshot(version=7,
        capabilities=[{"name": "shell", "attempts": 5, "success_rate": 0.8}],
        failure_modes=[]))
    SelfEvidencePipeline(m).ingest(ev)  # v2=B
    assert m.version == 2

    # 模拟重启
    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    assert m2.version == 2
    assert m2.current.capability_awareness.get("shell").available
    last = m2.current.update_history[-1]
    assert last.evidence_ids == (ev.evidence_id,)
    assert last.claim_id
    assert m2.accessor.identity_ref == AGENT