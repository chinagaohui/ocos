"""P0-1 Step 1 forensic tests — S2 SelfState Persistence / Ownership / Reload。

对应 OCD 完成判据：
    S2 可在不依赖 S1 实时值、不依赖 Prompt、不依赖 LLM 重建的情况下，
    从持久化介质恢复为同一个权威 SelfState，保持 identity_ref / version / hash /
    组件域状态 / continuity 信息一致。

覆盖：
    T1 单实例
    T2 持久化（self_state 表，非 agent_self_model）
    T3 reload（跨"重启"恢复最后一个 committed 态）
    T4 version 单调递增（拒绝路径不改版本）
    T5 hash 一致（提交态 hash == 再加载 hash；篡改被检测）
    T6 atomic failure 不产生半状态
    T7 identity_ref 不被复制/篡改
    T8 S1 变化 ≠ S2 自动变化（边界红线）
"""

from __future__ import annotations

import pytest

from ocos.self.self_state import (
    SelfStateIntegrityError,
    SelfStateManager,
    SelfStateRejected,
    SelfStateStore,
    SelfStateVersionConflict,
    deserialize_state,
    serialize_state,
)
from ocos.self.self_types import SelfUpdateContract, SelfUpdateSource, SelfModel
from ocos.storage.connection import get_connection
from ocos.storage.schema import TABLE_SELF_STATE

AGENT = "test-agent-01"


def _contract(reason: str = "forensic change", src: SelfUpdateSource = SelfUpdateSource.REFLECTION):
    return SelfUpdateContract(source=src, reason=reason, tick_id=1, fields_changed=("cognitive_state",))


def _apply_cognitive(manager: SelfStateManager) -> SelfModel:
    """标准 helper：改 cognitive_state 并提交，返回新 committed state。"""
    candidate = manager.build_candidate()
    candidate.cognitive_state.active_focus = f"focus-{candidate.version + 1}"
    return manager.commit_change(candidate, _contract())


# ── T1 单实例 ───────────────────────────────────────────────────────────────


def test_t1_single_instance(tmp_path):
    db = str(tmp_path / "t1.db")
    m1 = SelfStateManager(db)
    m1.boot(AGENT)
    assert m1.version == 1

    # 第二个 manager（同进程/同库）再次 boot：应加载同一 v1，不产生第二行
    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    assert m2.version == 1
    assert m2.identity_ref == AGENT

    conn = get_connection(db)
    cnt = conn.execute(
        f"SELECT COUNT(*) AS c FROM {TABLE_SELF_STATE} WHERE identity_ref = ?", (AGENT,)
    ).fetchone()["c"]
    assert cnt == 1, "FROZEN §STEP0#1: 每个 identity 只有一行 S2"


# ── T2 持久化（专属 self_state 表）─────────────────────────────────────────


def test_t2_persisted_in_self_state_table_not_agent_self_model(tmp_path):
    db = str(tmp_path / "t2.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    state = _apply_cognitive(m)
    assert state.version == 2

    # 落库载体必须是 self_state，而非 agent_self_model(S1)
    conn = get_connection(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert TABLE_SELF_STATE in tables
    row = conn.execute(
        f"SELECT version, content_hash FROM {TABLE_SELF_STATE} WHERE identity_ref = ?", (AGENT,)
    ).fetchone()
    assert row is not None
    assert row["version"] == 2
    assert row["content_hash"]

    # S2 恢复出的内容不含 S1 的狗/标签（T2 只验真身独立，S1 表存在与否不影响）
    restored = SelfStateStore(db).load(AGENT)
    assert restored.cognitive_state.active_focus == "focus-2"


# ── T3 reload 恢复最后一个 committed 态 ─────────────────────────────────────


def test_t3_reload_recovers_last_committed(tmp_path):
    db = str(tmp_path / "t3.db")
    m1 = SelfStateManager(db)
    m1.boot(AGENT)
    for _ in range(3):
        _apply_cognitive(m1)  # v2 -> v3 -> v4
    _, h1 = serialize_state(m1.current)
    assert m1.version == 4

    constructed = m1.build_candidate()  # 提交后当前态
    # 新 manager = 模拟进程重启
    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    assert m2.version == 4
    assert m2.current.identity_ref == AGENT
    _, h2 = serialize_state(m2.current)
    assert h1 == h2, "reload 必须恢复同一提交态（hash 一致）"
    assert m2.current.cognitive_state.active_focus == constructed.cognitive_state.active_focus


# ── T4 version 单调递增 ─────────────────────────────────────────────────────


def test_t4_version_monotonic_and_rejected_keeps_version(tmp_path):
    db = str(tmp_path / "t4.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    versions = [m.version]
    for _ in range(3):
        versions.append(_apply_cognitive(m).version)
    assert versions == [1, 2, 3, 4]
    assert len(set(versions)) == len(versions), "版本必须严格递增"

    # 拒绝路径：非法 contract（空来源/无字段）→ 治理门拒绝，版本不变
    bad = SelfUpdateContract(source=SelfUpdateSource.EXTERNAL_AGENT, reason="x", tick_id=1, fields_changed=("cognitive_state",))
    before = m.version
    with pytest.raises(SelfStateRejected):
        m.commit_change(m.build_candidate(), bad)
    assert m.version == before

    # version 冲突路径：candidate 版本被改坏 → 拒绝，当前态不变
    cand = m.build_candidate()
    cand.version = 99
    with pytest.raises(SelfStateVersionConflict):
        m.commit_change(cand, _contract())
    assert m.version == before


# ── T5 hash 一致（提交态 hash == 再加载 hash；篡改被检测）─────────────────


def test_t5_hash_consistent_and_tamper_detected(tmp_path):
    db = str(tmp_path / "t5.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    _apply_cognitive(m)  # v2
    committed_json, committed_hash = serialize_state(m.current)

    conn = get_connection(db)
    row = conn.execute(
        f"SELECT state_json, content_hash FROM {TABLE_SELF_STATE} WHERE identity_ref = ?", (AGENT,)
    ).fetchone()
    assert committed_hash == row["content_hash"] == m.accessor.content_hash, (
        "commit 时写下的 hash == 提交态 hash == accessor 投影 hash"
    )

    # 篡改 state_json → load 必须抛完整性错误（不返回脏状态）
    tampered = row["state_json"].replace("focus-2", "focus-HACKED", 1)
    with pytest.raises(SelfStateIntegrityError):
        deserialize_state(tampered, row["content_hash"])
    # 直接改库后 load 同样被拦
    conn.execute(
        f"UPDATE {TABLE_SELF_STATE} SET state_json = ? WHERE identity_ref = ?", (tampered, AGENT)
    )
    with pytest.raises(SelfStateIntegrityError):
        SelfStateManager(db).boot(AGENT)


# ── T6 atomic failure 不产生半状态 ──────────────────────────────────────────


def test_t6_atomic_failure_no_half_state(tmp_path):
    db = str(tmp_path / "t6.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    before_history = len(m.current.update_history)

    # 治理门拒绝：不落任何库
    bad = SelfUpdateContract(source=SelfUpdateSource.EXTERNAL_AGENT, reason="x", tick_id=1, fields_changed=("cognitive_state",))
    with pytest.raises(SelfStateRejected):
        m.commit_change(m.build_candidate(), bad)
    reloaded = SelfStateManager(db).boot(AGENT)
    assert reloaded.version == 1 and len(reloaded.update_history) == before_history
    _, h_after = serialize_state(reloaded)
    assert h_after == serialize_state(SelfStateStore(db).load(AGENT))[1]

    # 版本冲突写入失败：仍是 v1，无残缺行
    store = SelfStateStore(db)
    with pytest.raises(SelfStateVersionConflict):
        # 构造一个版本不合法但内容已"改好"的候选 → store 层必须整体回滚
        bad_state = SelfModel(identity_ref=AGENT, version=99, self_confidence=0.9)
        store.commit(bad_state)
    final = store.load(AGENT)
    assert final.version == 1, "提交失败后仍是旧 committed 态（无半状态）"


# ── T7 identity_ref 不被复制/篡改 ───────────────────────────────────────────


def test_t7_identity_immutable(tmp_path):
    db = str(tmp_path / "t7.db")
    m = SelfStateManager(db)
    m.boot(AGENT)

    cand = m.build_candidate()
    cand.identity_ref = "OTHER-AGENT"  # 尝试改身份
    with pytest.raises(SelfStateRejected):
        m.commit_change(cand, _contract())

    # 篡改库中 identity_ref → load 必须抛完整性错误
    store = SelfStateStore(db)
    conn = get_connection(db)
    conn.execute(
        f"UPDATE {TABLE_SELF_STATE} SET identity_ref='EVIL' WHERE identity_ref=?", (AGENT,)
    )
    # 篡改后，用被篡改后的 key 才能查到该行 → identity_ref 与查询键不符 → 拦截
    with pytest.raises(SelfStateIntegrityError):
        store.load("EVIL")


# ── T8 S1 变化 ≠ S2 自动变化（核心边界红线）─────────────────────────────────


def test_t8_s1_change_does_not_change_s2(tmp_path):
    """S1(t2)=C 变化、且未执行 S2 update —— reload S2 仍得到 B。"""
    db = str(tmp_path / "t8.db")
    m = SelfStateManager(db)
    m.boot(AGENT)
    _apply_cognitive(m)  # committed v2 = B
    _, h_b = serialize_state(m.current)
    snapshot_b = serialize_state(m.current)[0]

    # 制造 S1 变化：向 agent_self_model 写入不同的"我是谁"画像（真实 S1 校准）
    from ocos.self.agent_self_model import AgentSelfModel
    s1 = AgentSelfModel(db)
    s1.calibrate(capability_names=["shell", "filesystem", "code_executor"])
    conn = get_connection(db)
    s1_row = conn.execute(
        "SELECT COUNT(*) AS c FROM agent_self_model WHERE id=1"
    ).fetchone()["c"]
    assert s1_row == 1, "S1 画像已发生变化"

    # 未执行任何 S2 update —— reload 仍恢复 B
    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    _, h_b2 = serialize_state(m2.current)
    assert h_b == h_b2, "S1 变化绝不自动传导到 S2"
    assert m2.version == 2
    assert serialize_state(m2.current)[0] == snapshot_b

    # S2 投影不含 S1 的实时画像内容（S2 不从 S1 派生）
    proj = m2.accessor.render()
    assert "shell" not in proj, "S2 投影不含 S1 能力画像/标签"
    assert m2.accessor.identity_ref == AGENT