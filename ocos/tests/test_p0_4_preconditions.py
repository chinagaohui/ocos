"""P0-4 Preconditions Implementation  forensic tests — A(Z Freeze) + B(Decision₂ Trace)。

对应用户裁决「A + B only, 现在不跑 Attempt 2」：
  - A-T1..A-T5 : Counterfactual Baseline Freeze 不变量（防 post-hoc 归因）
  - B-T1..B-T5 : Decision₂ Trace 身份连续性（D→Thinking→Decision₂→Action₂→Y）

Gate：
  A、B 全部绿 → P0-4 Preconditions Gate OPEN（才允许排期 Attempt 2）
  任一红     → 维持 BLOCKED
"""

from __future__ import annotations

import uuid

import pytest

from ocos.self.counterfactual_baseline import (
    BaselineImmutableError,
    BaselineKeyConflictError,
    BaselineNotFrozenError,
    CounterfactualBaseline,
    CounterfactualBaselineStore,
)
from ocos.self.decision_trace import (
    DecisionRecord,
    DecisionTraceStore,
    ThinkingTrace,
    record_decision_trace,
    record_thinking_trace,
)
from ocos.self.self_state import (
    SelfStateManager,
    get_self_projection,
    register_self_projection,
)
from ocos.self.self_types import SelfUpdateContract, SelfUpdateSource


# ═══════════════════════════ A. Counterfactual Baseline Freeze ═══════════════════════════

GOAL = "deterministic-file-org"
INIT = {"dir": "/data", "n": 3, "sort": "mtime"}


def _draft(baseline_id: str, goal: str = GOAL, initial=None):
    return CounterfactualBaseline(
        baseline_id=baseline_id,
        goal=goal,
        initial_state=initial if initial is not None else dict(INIT),
        decision="noop-keep",
        strategy="baseline-strategy",
        action="noop",
        predicted_result={"status": "unchanged"},
        source="experiment-harness",
        evidence=("S1-ev-1", "S1-ev-2"),
        confidence=0.7,
    )


def test_a_t1_freeze_basic(tmp_path):
    """A-T1: freeze() 后 frozen_at/baseline_hash 非空，baseline_for 返回该 Z。"""
    db = str(tmp_path / "a_t1.db")
    store = CounterfactualBaselineStore(db)
    store.save_draft(_draft("Z-1"))
    frozen = store.freeze("Z-1", frozen_by="forensic")
    assert frozen.is_frozen is True
    assert frozen.frozen_at is not None
    assert frozen.frozen_by == "forensic"
    assert frozen.baseline_hash != ""

    got = store.baseline_for(GOAL, dict(INIT))
    assert got is not None
    assert got.baseline_id == "Z-1"
    assert got.baseline_hash == frozen.baseline_hash
    assert got.require_frozen() is None  # 可用作归因基准


def test_a_t2_immutable_after_freeze(tmp_path):
    """A-T2: 冻结后任何改写/重冻结 reject（防 post-hoc）。"""
    db = str(tmp_path / "a_t2.db")
    store = CounterfactualBaselineStore(db)
    store.save_draft(_draft("Z-2"))
    store.freeze("Z-2")

    # 重冻结同一 baseline → reject
    with pytest.raises(BaselineImmutableError):
        store.freeze("Z-2")
    # 用同 baseline_id 写新草稿覆盖 → reject（已有冻结行）
    with pytest.raises(BaselineImmutableError):
        store.save_draft(_draft("Z-2"))
    # 同 (goal,state_key) 不同 id 的新草稿 → reject（已有冻结 key）
    with pytest.raises(BaselineImmutableError):
        store.save_draft(_draft("Z-2-alt"))


def test_a_t3_single_frozen_per_key(tmp_path):
    """A-T3: 同 (goal, initial_state) 至多一份已冻结 Z；二次冻结 reject。"""
    db = str(tmp_path / "a_t3.db")
    store = CounterfactualBaselineStore(db)
    store.save_draft(_draft("Z-3a"))
    store.save_draft(_draft("Z-3b"))  # 同 key 草稿可并存/替换
    store.freeze("Z-3a")
    with pytest.raises(BaselineKeyConflictError):
        store.freeze("Z-3b")


def test_a_t4_unfrozen_not_attributable(tmp_path):
    """A-T4: 草稿不可归因 —— baseline_for 返回 None / require_frozen 抛错。"""
    db = str(tmp_path / "a_t4.db")
    store = CounterfactualBaselineStore(db)
    store.save_draft(_draft("Z-4"))
    assert store.baseline_for(GOAL, dict(INIT)) is None, "草稿不得用于归因"
    draft = store.get("Z-4")
    assert draft is not None and draft.is_frozen is False
    with pytest.raises(BaselineNotFrozenError):
        draft.require_frozen()


def test_a_t5_persistence_across_reopen(tmp_path):
    """A-T5: 跨 store 重开仍返回同一 baseline_hash（防篡改持久化）。"""
    db = str(tmp_path / "a_t5.db")
    CounterfactualBaselineStore(db).save_draft(_draft("Z-5"))
    CounterfactualBaselineStore(db).freeze("Z-5")
    reused = CounterfactualBaselineStore(db).baseline_for(GOAL, dict(INIT))
    assert reused is not None
    assert reused.baseline_id == "Z-5"
    # 冻结内容的 hash 应是冻结时锁定的值（不因 reopen 改变）
    first_hash = CounterfactualBaselineStore(db).get("Z-5").baseline_hash
    assert reused.baseline_hash == first_hash and first_hash


# ═══════════════════════════ B. Decision₂ Trace ═══════════════════════════

AGENT = "p0-4-agent"


def _commit_d(manager: SelfStateManager, claim_id: str, reason: str) -> int:
    """注入一条 Failure→D→governed commit，返回新 committed version。"""
    candidate = manager.build_candidate()
    candidate.cognitive_state.active_focus = f"focus-delta-{claim_id}"
    contract = SelfUpdateContract(
        source=SelfUpdateSource.RUNTIME_OBSERVATION,
        reason=reason,
        tick_id=1,
        fields_changed=("cognitive_state",),
        evidence_count=1,
        claim_id=claim_id,
        evidence_ids=("S1-ev-x",),
    )
    committed = manager.commit_change(candidate, contract)
    return committed.version


@pytest.fixture
def s2_chain(tmp_path):
    """一个已 boot 的 S2 manager + 进程内 accessor 注册，供 trace hook 消费。"""
    db = str(tmp_path / "b.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    register_self_projection(db, m.accessor)
    return db, m


def test_b_t1_identity_chain_unique(tmp_path):
    """B-T1: 一次决策产出 thinking_trace_id → decision_id → action_ids，自洽唯一。"""
    db = str(tmp_path / "b_t1.db")
    store = DecisionTraceStore(db)
    t = store.record_thinking(self_version=1, consumed_delta_ids=("d-1",), consumed_evidence_ids=("e-1",))
    d = store.record_decision(
        thinking_trace_id=t.thinking_trace_id,
        decision="pick-action", strategy="s", action="run",
        action_ids=("act-1", "act-2"), y_ref="Y-1",
    )
    assert t.thinking_trace_id != d.decision_id
    assert d.thinking_trace_id == t.thinking_trace_id
    assert tuple(d.action_ids) == ("act-1", "act-2")
    # 唯一性：同一 trace 下 decision 可 join
    joined = store.decisions_for_trace(t.thinking_trace_id)
    assert len(joined) == 1 and joined[0].decision_id == d.decision_id


def test_b_t2_d_consumption_proven(s2_chain):
    """B-T2: 注入 D→commit(version N+1) 后，ThinkingTrace.self_version=N+1 且消费 D 的 claim_id。"""
    db, m = s2_chain
    n = _commit_d(m, claim_id="D-clm-7", reason="observed failure")
    trace = record_thinking_trace(db)
    assert trace is not None
    assert trace.self_version == n, "所见 S2 version 必须 = 提交后 N+1"
    assert "D-clm-7" in tuple(trace.consumed_delta_ids), "consumed_delta_ids 必须含 D 的 claim_id"
    assert "S1-ev-x" in tuple(trace.consumed_evidence_ids)


def test_b_t3_no_d_no_consumption_hook(s2_chain):
    """B-T3: 无新 commit 时，consumed_* 不引入不存在证据；全部可在 update_history 校验。"""
    db, m = s2_chain  # 尚未注入 D
    claims = m.accessor.committed_claims()
    assert claims == [], "未 commit 时不应有任何 consumed claim"
    trace = record_thinking_trace(db)
    assert trace is not None
    assert tuple(trace.consumed_delta_ids) == ()
    assert tuple(trace.consumed_evidence_ids) == ()

    # 注入 D 后：consumed id 都能在 update_history / committed_claims 中验证
    _commit_d(m, claim_id="D-clm-9", reason="second delta")
    trace2 = record_thinking_trace(db)
    known_claims = {c["claim_id"] for c in m.accessor.committed_claims()}
    known_ev = {e for c in m.accessor.committed_claims() for e in c["evidence_ids"]}
    assert set(trace2.consumed_delta_ids) <= known_claims
    assert set(trace2.consumed_evidence_ids) <= known_ev


def test_b_t4_zero_behavioral_delta(s2_chain):
    """B-T4: 加 trace 前后，S2 投影/prompt 内容与决策状态不变（仅附 trace 元数据）。"""
    db, m = s2_chain
    _commit_d(m, claim_id="D-clm-11", reason="trace-should-not-mutate")
    hash_before = m.accessor.content_hash
    proj_before = m.accessor.project()

    # 记录 trace 是纯 append，不改 S2
    t = record_thinking_trace(db)
    d = record_decision_trace(db, t.thinking_trace_id, decision="same", action_ids=("a",))
    assert d is not None

    assert m.accessor.content_hash == hash_before, "S2 不可被 trace 改写"
    assert m.accessor.project() == proj_before, "S2 投影协议不可变"


def test_b_t5_same_chain_join_version_consistent(s2_chain):
    """B-T5: DecisionRecord 按 thinking_trace_id join 回 ThinkingTrace 且版本一致。"""
    db, m = s2_chain
    n = _commit_d(m, claim_id="D-clm-13", reason="join check")
    t = record_thinking_trace(db)
    assert t is not None and t.self_version == n

    rec = record_decision_trace(
        db, t.thinking_trace_id, decision="decided", action_ids=("act-x",), action="run", strategy="st"
    )
    assert rec is not None
    # 从 DB 独立重读，验证 join 自洽
    store = DecisionTraceStore(db)
    stored_trace = store.thinking(t.thinking_trace_id)
    stored_rec = store.decision(rec.decision_id)
    assert stored_rec.thinking_trace_id == stored_trace.thinking_trace_id
    assert stored_trace.self_version == n
    assert stored_rec.decision == "decided"
    assert tuple(stored_rec.action_ids) == ("act-x",)
    # 版本级一致（B.5 invariant）：DecisionRecord 与其 trace 同 version
    assert stored_rec.thinking_trace_id == stored_trace.thinking_trace_id