"""P1 Production SelfState Restore（2026-09-14）— S1→S2 生产供数线行为验收。

背景：57 个平台提交把 S2 结构与三个生产读口上线，但生产无 S2 写入方，
S2 停在空骨架 v1、RecallRouter self 槽由 Phase 2 的「有数据」退化为 0。
本文件验收恢复性迁移（金丝雀端到端见 tests/test_self_model_cogv2.py）：

  旧 S1（历史经验性能力证据）
    → bootstrap（一次性，S2 boot 后读 S1 已持久化画像）
    → feed（calibrate 成功即发射：goal_result 闭合 + daemon 50-tick 两处收口）
    → SelfEvidencePipeline（recognition 门 + 治理门 + 语义 noop 门）
    → committed S2 → converse/bridge/recall_router 唯一消费

硬验收（对应用户裁决）：
  - 事故现场（S1 有货、S2 空骨架）bootstrap 后，S2 与 S1 实测证据对账一致
  - 同一 S1 内容重复喂（重启补偿/内容未变 tick）→ 0 新版本（防灌水）
  - 只有真实变化（可用性翻转/失败计数增长）才产新版本
  - RecallRouter self 槽：供数前 0 条，供数后 1 条且 ≤120 字、type=self
  - 注册 accessor（生产读路径）在供数后立即读到新 committed 态（同一 manager 实例）
  - 供数失败/畸形输入绝不抛进主链
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pytest

from ocos.memory.recall_router import RecallRouter
from ocos.self.agent_self_model import AgentSelfModel
from ocos.self.s2_feeder import bootstrap_from_s1, feed_s1_snapshot
from ocos.self.self_state import (
    SelfStateManager,
    _S2_ACCESSOR_REGISTRY,
    register_self_projection,
)
from ocos.storage.connection import get_connection
from ocos.storage.migrations import ensure_schema

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENT = "ocos-master"

_EP_COLS = (
    "id, experience_id, session_id, context, goal, decision, action, "
    "outcome, condition, significance_score, evaluation_trace, source, "
    "status, tags, created_at"
)


def _make_db(tmp_path, name="prod_feed.db") -> str:
    """生产同构库：全量迁移 + identity 锚（S2 boot/get_self_projection 的身份源）。"""
    db = str(tmp_path / name)
    ensure_schema(db)
    conn = get_connection(db)
    conn.execute(
        "INSERT INTO identity (agent_id, born_at, name) VALUES (?, ?, ?)",
        (AGENT, datetime.now(timezone.utc).isoformat(), "OCOS Agent"),
    )
    conn.commit()
    conn.close()
    return db


def _insert_episode(conn, eid, action, context, outcome, tags=None,
                    source="goal_result"):
    conn.execute(
        f"INSERT INTO episodes ({_EP_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            f"EPI-{eid}", f"EXP-{eid}", "test",
            json.dumps(context, ensure_ascii=False), "g", "", action,
            json.dumps(outcome, ensure_ascii=False), "", 0.7, "{}",
            source, "active", json.dumps(tags or [], ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def _seed_episodes(db: str) -> None:
    """与生产同构的 S1 证据：writer/shell 5 次全成，researcher 3 次全败，
    execution_error 反复失败 3 次。"""
    conn = get_connection(db)
    for i in range(5):
        _insert_episode(
            conn, f"ok{i}", "goal_result",
            {"agent": "writer", "capabilities": [{"name": "shell", "success": True}]},
            {"success": True},
        )
    for i in range(3):
        _insert_episode(
            conn, f"bad{i}", "goal_result",
            {"agent": "researcher", "capabilities": []},
            {"success": False},
        )
    for i in range(3):
        _insert_episode(
            conn, f"fm{i}", "failure_lesson", {}, {},
            tags=["execution_error"], source="failure_lesson",
        )
    conn.commit()
    conn.close()


def _legacy_db_with_s1(tmp_path):
    """复刻平台迁移后的生产事故现场：S1 有已校准画像，S2 行被清空（空骨架）。

    calibrate 落 S1 的同时会经新供数线惰性写 S2 —— 显式清掉注册表与
    self_state 行，精确复现「S1 有货 / S2 无行」的升级瞬间。
    """
    db = _make_db(tmp_path)
    _seed_episodes(db)
    snap = AgentSelfModel(db).calibrate()
    _S2_ACCESSOR_REGISTRY.pop(db, None)
    conn = get_connection(db)
    conn.execute("DELETE FROM self_state")
    conn.commit()
    conn.close()
    return db, snap


@pytest.fixture(autouse=True)
def _clean_registry(tmp_path):
    """按 tmp_path 清理进程级 S2 accessor 注册表，防跨用例串库。"""
    yield
    for k in [k for k in _S2_ACCESSOR_REGISTRY if str(tmp_path) in str(k)]:
        _S2_ACCESSOR_REGISTRY.pop(k, None)


def _boot_s2(db: str) -> SelfStateManager:
    m = SelfStateManager(db)
    m.boot(AGENT)
    register_self_projection(db, m.accessor)
    return m


# ── 1. 边界：空输入不抛、0 版本 ─────────────────────────────────────────────


def test_feed_none_inputs_returns_zero(tmp_path):
    db = _make_db(tmp_path, "edge.db")
    m = _boot_s2(db)
    assert feed_s1_snapshot(None, None) == 0
    assert feed_s1_snapshot(m, None) == 0
    assert feed_s1_snapshot(m, {}) == 0
    # 有观测但全部小样本（attempts<3）→ recognition 门挡光 → 0
    snap = {"version": 1, "content_hash": "h",
            "capabilities": [{"name": "curl", "attempts": 2, "success_rate": 1.0}],
            "failure_modes": []}
    assert feed_s1_snapshot(m, snap) == 0
    assert m.version == 1


def test_feed_malformed_snapshot_never_raises(tmp_path):
    db = _make_db(tmp_path, "malformed.db")
    m = _boot_s2(db)
    # 畸形值不得抛进主链（calibrate/goal_result 闭合点无逐字段保护）
    assert feed_s1_snapshot(m, {"capabilities": [{"name": "x", "attempts": "NaN"}]}) == 0
    assert m.version == 1


def test_bootstrap_without_s1_history_is_noop(tmp_path):
    db = _make_db(tmp_path, "fresh.db")
    m = _boot_s2(db)
    # 全新库 S1 从未校准 → bootstrap 0，等待首个 calibrate 周期供数
    assert bootstrap_from_s1(m, AgentSelfModel(db)) == 0
    assert m.version == 1 and not m.accessor.brief()


# ── 2. bootstrap：事故现场 S1 实测证据 → committed S2，对账一致 ───────────────


def test_bootstrap_migrates_s1_evidence_to_committed_s2(tmp_path):
    db, snap = _legacy_db_with_s1(tmp_path)
    # S1 侧事实
    s1_caps = {c["name"]: c for c in snap["capabilities"]}
    assert s1_caps["shell"]["attempts"] == 5
    assert s1_caps["shell"]["success_rate"] == 1.0
    assert s1_caps["researcher"]["success_rate"] == 0.0
    assert any(fm["cause"] == "execution_error" for fm in snap["failure_modes"])

    m = _boot_s2(db)
    assert m.version == 1 and not m.accessor.brief(), "供数前 S2 必须是空骨架"

    n = bootstrap_from_s1(m, AgentSelfModel(db))
    assert n >= 3, "shell/writer 能力 + execution_error 失败模式至少 3 个 governed 版本"
    assert m.version == 1 + n

    ca = m.current.capability_awareness
    # 高实测成功 → available=True 入 known
    assert ca.get("shell").available is True
    assert ca.get("writer").available is True
    # 0 成功（sr<0.6）→ available=False（uncertain，不敢自称可用）
    researcher = ca.get("researcher")
    assert researcher is not None and researcher.available is False
    # 反复失败 → knowledge_boundary.needs_verification
    kb = m.current.knowledge_boundary
    assert "execution_error" in kb.needs_verification

    brief = m.accessor.brief()
    assert brief and "shell" in brief and "execution_error" in brief
    assert "researcher" not in brief, "brief 只宣告 known 能力，不确定能力不冒充"


# ── 3. 幂等：同一内容重复喂 → 0 新版本（重启补偿/内容未变 tick）──────────────


def test_feed_idempotent_same_snapshot_no_version_bump(tmp_path):
    db, snap = _legacy_db_with_s1(tmp_path)
    m = _boot_s2(db)

    first = bootstrap_from_s1(m, AgentSelfModel(db))
    assert first > 0
    v0 = m.version

    # 进程内重复闭合 tick（calibrate 产出内容相同的快照）
    assert feed_s1_snapshot(m, snap) == 0
    assert m.version == v0

    # 模拟重启：新 manager reload 已提交态后 bootstrap 再来一次
    m2 = SelfStateManager(db)
    m2.boot(AGENT)
    assert bootstrap_from_s1(m2, AgentSelfModel(db)) == 0
    assert m2.version == v0


# ── 4. 真实变化才提交：可用性翻转 / 失败计数增长 ─────────────────────────────


def test_feed_commits_only_real_semantic_change(tmp_path):
    db, snap = _legacy_db_with_s1(tmp_path)
    m = _boot_s2(db)
    bootstrap_from_s1(m, AgentSelfModel(db))
    v0 = m.version

    # shell 成功率 1.0 → 0.2（跨 0.6 线）→ 可用性翻转，必须产生新版本
    flipped = json.loads(json.dumps(snap))
    for c in flipped["capabilities"]:
        if c["name"] == "shell":
            c["success_rate"] = 0.2
    n = feed_s1_snapshot(m, flipped)
    assert n >= 1 and m.version == v0 + n
    assert m.current.capability_awareness.get("shell").available is False

    # 失败计数 3 → 6（反复失败在强化）→ knowledge_boundary 产生新版本
    v1 = m.version
    grown = json.loads(json.dumps(flipped))
    for fm in grown["failure_modes"]:
        if fm["cause"] == "execution_error":
            fm["count"] = 6
    n2 = feed_s1_snapshot(m, grown)
    assert n2 >= 1 and m.version == v1 + n2
    assert (m.current.knowledge_boundary
            .needs_verification["execution_error"].evidence_count == 6)


# ── 5. RecallRouter self 槽：供数前后对照（Phase2 退化回归门）────────────────


def test_recall_router_self_slot_gated_on_feeding(tmp_path):
    db, _ = _legacy_db_with_s1(tmp_path)
    m = _boot_s2(db)

    def _self_items():
        items = RecallRouter(db).recall("调研文献检索方法与失败模式")
        return [i for i in items if i["subsystem"] == "self"]

    # 供数前：self 槽 0 条（本次生产事故的金丝雀断言）
    assert _self_items() == []

    bootstrap_from_s1(m, AgentSelfModel(db))

    selfs = _self_items()
    assert len(selfs) == 1, "供数后 MEM_CTX self 槽必须恢复"
    assert selfs[0]["type"] == "self"
    assert len(selfs[0]["text"]) <= 120
    assert "shell" in selfs[0]["text"]


# ── 6. 同一 manager 实例：注册 accessor 在供数后立即读到 ────────────────────


def test_registered_accessor_sees_feed_immediately(tmp_path):
    db, _ = _legacy_db_with_s1(tmp_path)
    m = _boot_s2(db)
    acc = m.accessor  # 生产读路径持有的 accessor（绑定该 manager 实例）
    assert not acc.brief()

    n = bootstrap_from_s1(m, AgentSelfModel(db))
    assert n > 0
    assert acc.brief(), "feeder 必须喂 runtime boot 的同一实例；另建 manager 则此处读不到"
    assert acc.version == m.version


# ── 7. 生产接线源码契约 ──────────────────────────────────────────────────────


def test_production_wiring_contract():
    # 7a. S2 boot 路径必须挂一次性 S1→S2 恢复性迁移
    rt = (REPO_ROOT / "ocos/agent/agent_runtime.py").read_text(encoding="utf-8")
    assert "bootstrap_from_s1" in rt, "S2 boot 后缺 S1→S2 恢复性迁移接线"
    # goal_result 闭合点仍调 calibrate（供数已收口进 calibrate，不另接双路径）
    goal_block = rt[rt.index("Goal result episode saved"):][:1200]
    assert ".calibrate(" in goal_block

    # 7b. calibrate 是 S2 供数的唯一生产发射点（goal_result + 50-tick 两处收口）
    sm = (REPO_ROOT / "ocos/self/agent_self_model.py").read_text(encoding="utf-8")
    cal = sm[sm.index("def calibrate"):sm.index("def _stat_capabilities")]
    assert "get_or_boot_self_manager" in cal, "calibrate 必须复用进程唯一 S2 manager"
    assert "feed_s1_snapshot" in cal, "calibrate 落库后必须确定性喂 S2"

    # 7c. S2 store 只自建专属表，不跑全量迁移链（异构最小库可 boot）
    ss = (REPO_ROOT / "ocos/self/self_state.py").read_text(encoding="utf-8")
    assert "CREATE_SELF_STATE" in ss
    assert "ensure_schema(self._db_path)" not in ss, \
        "S2 initialize 不得跑全量迁移（简化 episodes 库会因缺列失败）"


def test_store_initialize_does_not_close_pooled_connection(tmp_path):
    """连接纪律回归：S2 boot 不得关闭 get_connection 的进程池共享连接。

    生产事故复现：initialize 末尾 close 共享连接后，启动期并发持有同一
    连接引用的 goal/event-loop 线程刷 "Cannot operate on a closed database"。
    """
    from ocos.storage.connection import get_connection
    db = _make_db(tmp_path, "pool.db")
    pooled = get_connection(db)
    pooled.execute("SELECT 1")  # 预热入池
    SelfStateManager(db).boot(AGENT)
    # 池里同一引用必须仍可用（自愈重建会是新对象，故直接验证 execute 不抛）
    pooled.execute("SELECT 1")
    again = get_connection(db)
    again.execute("SELECT count(*) FROM self_state")
    assert again is pooled, "initialize 不得关闭/替换池化连接（竞态源）"
