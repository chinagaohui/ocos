"""P0-1 Step 3 forensic tests — S2 → Thinking 接线（语义迁移，非"接上了"）。

验收核心（FROZEN）：
    T3-1 Source          决策/LLM 的 Self representation 唯一来自 S2 committed projection
    T3-2 No S1 bypass    生产 Prompt 路径不再直接调用 S1.render / render_brief
    T3-3 Committed-state S1 实时变化不影响 Thinking，只有 S2 commit 后才变化
    T3-4 Continuity      restart 后 Thinking 使用持久化恢复的 S2，而非从 S1 重新构造

并验证两个对照必须同时成立：
    Thinking₂'（S1 变了但未 commit）== Thinking₂
    Thinking₃（governed commit 后） 反映 S2(t2)
"""

from __future__ import annotations

import pathlib

import pytest

from ocos.self.self_state import (
    SelfStateManager,
    get_self_projection,
    register_self_projection,
    _S2_ACCESSOR_REGISTRY,
)
from ocos.self.self_evidence import (
    SelfEvidencePipeline,
    capture_s1_snapshot,
)

IDENT = "thinking-agent-003"


def _s1snap(version: int, caps, fm=None) -> dict:
    return {
        "version": version,
        "content_hash": f"s1hash-v{version}",
        "capabilities": caps,
        "failure_modes": [] if fm is None else fm,
        "personality": {"reply_style": "detail"},
        "focus": [],
    }


def _session(db: str):
    """创建并注册唯一 S2 属主（模拟 AgentRuntime boot）。后续 commit 一律走该 manager。"""
    m = SelfStateManager(db)
    m.boot(IDENT)
    register_self_projection(db, m.accessor)  # 唯一 accessor 进进程级注册表
    return m


def _commit_capability(m, cap_name: str, attempts: int, sr: float, s1ver: int):
    """经 S2 治理提交一条能力。返回提交后的 accessor（正是 Thinking 所见）。"""
    snap = _s1snap(s1ver, [{"name": cap_name, "attempts": attempts, "success_rate": sr}])
    ev = capture_s1_snapshot(snap)
    committed = SelfEvidencePipeline(m).ingest(ev)
    assert committed, "一步治理提交应成功"
    return get_self_projection(m._store._db_path, IDENT)


@pytest.fixture(autouse=True)
def _clean_registry(tmp_path):
    yield
    for k in list(_S2_ACCESSOR_REGISTRY):
        if str(tmp_path) in str(k):
            _S2_ACCESSOR_REGISTRY.pop(k, None)


# ── T3-1 Source ― 唯一来自 S2 committed projection ───────────────────────────


def test_t31_source_is_committed_s2(tmp_path):
    db = str(tmp_path / "t31.db")
    m = _session(db)
    acc = _commit_capability(m, "shell", 5, 0.9, s1ver=5)
    assert acc is not None
    assert acc.identity_ref == IDENT
    assert acc.version >= 2, "accessor 反映已提交的 S2（含治理变更）"
    assert "shell" in acc.render()
    assert "capabilities:shell" in acc.brief()


# ── T3-2 No S1 bypass ― 即使 S1 失效，Thinking 依然走 S2 ────────────────────


def test_t32_no_s1_bypass_at_runtime(tmp_path, monkeypatch):
    db = str(tmp_path / "t32.db")
    m = _session(db)
    _commit_capability(m, "t32cap", 5, 0.85, s1ver=6)

    # 让 S1.render / render_brief 直接抛错 → 若 Thinking 碰 S1 必崩
    monkeypatch.setattr(
        "ocos.self.agent_self_model.AgentSelfModel.render",
        lambda s, **k: (_ for _ in ()).throw(RuntimeError("S1 bypass!")),
    )
    monkeypatch.setattr(
        "ocos.self.agent_self_model.AgentSelfModel.render_brief",
        lambda s, **k: (_ for _ in ()).throw(RuntimeError("S1 bypass!")),
    )
    acc = get_self_projection(db, IDENT)
    text = acc.render()
    brief = acc.brief()
    assert "t32cap" in text and "t32cap" in brief


def test_t32_no_s1_call_in_production_sources():
    files = [
        "/workspace/ocos/interaction/converse.py",
        "/workspace/ocos/execution/bridge.py",
        "/workspace/ocos/memory/recall_router.py",
    ]
    for f in files:
        src = pathlib.Path(f).read_text(encoding="utf-8")
        # 权威信号：不再 import S1(render/render_brief 生产者)，杜绝一切 bypass
        assert "from ocos.self.agent_self_model import" not in src, (
            f"生产 Prompt 路径仍 import S1：{f}"
        )
        assert "agent_self_model" not in src, f"生产 Prompt 路径仍引用 S1 模块：{f}"


# ── T3-3 Committed-state 边界（两个对照必须同时成立）────────────────────────


def test_t33_committed_state_boundary_two_controls(tmp_path):
    db = str(tmp_path / "t33.db")
    m = _session(db)

    # S1(t1) → committed S2(t1) → Thinking₂
    acc = _commit_capability(m, "base_cap", 5, 0.9, s1ver=1)   # v2 = B
    thinking_2 = get_self_projection(db, IDENT).render()
    brief_2 = acc.brief()
    hash_2 = acc.content_hash

    # ── 对照 A：S1(t2) 实时变化 + 未 commit ──
    snap_c = _s1snap(3, [{"name": "base_cap", "attempts": 6, "success_rate": 0.5},
                          {"name": "intruder_cap", "attempts": 8, "success_rate": 1.0}])
    ev_c = capture_s1_snapshot(snap_c)
    assert ev_c is not None
    thinking_2p = get_self_projection(db, IDENT).render()
    assert thinking_2p == thinking_2, "S1 变化但未 commit，Thinking 的 Self 表示必须不变"
    assert "intruder_cap" not in thinking_2p
    assert get_self_projection(db, IDENT).content_hash == hash_2

    # ── 对照 B：through same owner → governed commit → S2(t2) → Thinking₃ ──
    committed = SelfEvidencePipeline(m).ingest(ev_c)  # new S1 → claim → delta → governed commit
    assert committed
    brief_3 = get_self_projection(db, IDENT).brief()
    assert "intruder_cap" in brief_3, "只有 commit 后 Thinking 才看到新能力"
    assert "base_cap" not in brief_3                 # base_cap 实测降级 → 离开 known

    # 两个对照必须同时成立
    assert thinking_2p == thinking_2                  # 未 commit：Thinking 不变
    assert brief_3 != brief_2 and "intruder_cap" in brief_3  # commit 后：Thinking 变化


# ── T3-4 Persistence continuity ― restart 用持久化恢复的 S2 ─────────────────


def test_t34_persistence_continuity_after_restart(tmp_path):
    db = str(tmp_path / "t34.db")
    m = _session(db)
    acc = _commit_capability(m, "durable_cap", 5, 0.95, s1ver=2)
    v_before = acc.version
    render_before = acc.render()
    caps_before = {k: (v.available, v.confidence)
                   for k, v in acc.current.capability_awareness.known.items()}

    # "重启"：清空进程内注册 → 强制从持久化介质 reload committed S2
    _S2_ACCESSOR_REGISTRY.pop(db, None)
    acc2 = get_self_projection(db, IDENT)
    assert acc2 is not None
    assert acc2.version == v_before, "restart 后仍为持久化恢复的同一 committed version"
    assert acc2.render() == render_before
    caps2 = {k: (v.available, v.confidence)
             for k, v in acc2.current.capability_awareness.known.items()}
    assert caps2 == caps_before

    # 全新进程经显式身份也能直接从持久化恢复（不重建于 S1）
    _S2_ACCESSOR_REGISTRY.pop(db, None)
    acc3 = get_self_projection(db, IDENT)
    assert acc3 is not None
    assert acc3.render().startswith(f"SelfState v{v_before}")