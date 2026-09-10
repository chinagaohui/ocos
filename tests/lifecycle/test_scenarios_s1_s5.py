"""S1–S5 场景: 隔夜成长 / 失败自愈 / 自主提案 / 好奇心探测 / 主动汇报。

行为级断言（docs 升级方案 §3.2 第二层表），确定性骨架:
  S1 注入经验 → dream 巩固合成技能 → 同型任务复用（时延下降的
     结构性代理: 规划侧直接拿到已验证步骤，无需重新探索）；
  S2 同型失败 ×2 → 第三次执行行为可观测改变（先验矫正程序注入）；
  S3 LEVEL=2 → 自主提案产生、限速生效、全程审计（1h 空跑的
     加速等价: 信号种子 + 真实 scan 管线）；
  S4 低置信信念 → 只读探测候选 + 提案落地；
  S5 自主目标完成 → outbox 推送（UX-J 秒级链路）。
"""

from __future__ import annotations

import threading
from collections import deque

import pytest

from tests.lifecycle.conftest import (
    FakeInbox, insert_goal_result, insert_lesson, learning_marks,
    make_raw_db, seed_episode)


# ── S1 隔夜成长 ──────────────────────────────────────────────────────────

class TestS1OvernightGrowth:
    def test_experiences_consolidate_into_replayable_skill(self, tmp_path):
        """10 条经验（含同型成功 ×2）→ dream 巩固 → 次日同型任务复用。"""
        conn = make_raw_db(tmp_path / "life.db")
        for _ in range(2):
            insert_goal_result(conn, "整理季度销售报告",
                               "✓ 已生成季度销售汇总报表 → done")
        for i in range(8):                      # 其余 8 条杂类经验
            insert_goal_result(conn, f"杂类任务{i}",
                               "✓ 完成" if i % 2 else "✗ 未完成",
                               success=(i % 2 == 0))
        conn.close()

        # dream 巩固（daemon 周期调用同一入口）
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._db_path = str(tmp_path / "life.db")
        # 收敛裁决 P3: 技能合成宿主 = ConsolidationService
        from ocos.daemon.consolidation_service import LearningConsolidationService
        svc = LearningConsolidationService(rt._db_path)
        assert svc._synthesize_skills() == 1

        # 次日同型任务: 规划侧拿到已验证步骤（复用而非重新探索）
        from ocos.execution.bridge import DecisionBridge
        b = DecisionBridge.__new__(DecisionBridge)
        b._db_path = str(tmp_path / "life.db")
        hint = b._skill_replay_hint("请帮我整理季度销售报告")
        assert "技能重放" in hint and "已验证" in hint
        assert "整理季度销售报告" in hint       # 同型任务命中
        marks = learning_marks(tmp_path)
        assert any(m["type"] == "skill_synthesized" and m["count"] == 1
                   for m in marks)
        assert any(m["type"] == "skill_replay" and m["matched"] is True
                   for m in marks)

    def test_irrelevant_task_not_polluted(self, tmp_path):
        """非同型任务不被技能重放污染（诚实沉默）。"""
        conn = make_raw_db(tmp_path / "life.db")
        for _ in range(2):
            insert_goal_result(conn, "整理季度销售报告", "✓ 报表已生成")
        conn.close()
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._db_path = str(tmp_path / "life.db")
        from ocos.daemon.consolidation_service import LearningConsolidationService
        LearningConsolidationService(rt._db_path)._synthesize_skills()
        from ocos.execution.bridge import DecisionBridge
        b = DecisionBridge.__new__(DecisionBridge)
        b._db_path = str(tmp_path / "life.db")
        assert b._skill_replay_hint("修复打印机卡纸") == ""


# ── S2 失败自愈 ──────────────────────────────────────────────────────────

class TestS2FailureSelfHealing:
    def test_behavior_changes_after_repeated_failures(self, tmp_path):
        """同型失败 ×2 → 第三次执行前行为可观测改变（先验注入）。"""
        conn = make_raw_db(tmp_path / "life.db")
        # 第一次: 无失败史 → 无先验（首次行为）
        b = _bridge_with_db(tmp_path)
        assert b._failure_prior_hint("部署生产服务") == ""
        # 两次同型失败
        insert_lesson(conn, "execution_error", goal_pattern="部署生产服务")
        insert_lesson(conn, "execution_error", goal_pattern="部署生产服务")
        # 第三次: 行为改变 — 规划侧注入矫正程序
        hint = b._failure_prior_hint("部署生产服务到新机器")
        assert "执行程序提示" in hint
        # PHASE-LIFE: execution_error 现在有 C 类模板 cause_to_procedure 动态生成
        # 关键词对齐: "先检查前置条件"（动态模板）或 "校验输入"（旧静态 fallback）
        assert ("先检查前置条件" in hint
                or "校验输入" in hint
                or "【" in hint and "程序】" in hint), f"expected procedure hint, got: {hint}"
        marks = [m for m in learning_marks(tmp_path)
                 if m["type"] == "lesson_prior_injected"]
        assert marks and marks[0]["mode"] == "pattern"
        conn.close()

    def test_recurrence_cause_guides_unrelated_task(self, tmp_path):
        """复发 cause 对未匹配任务也有兜底引导（recurrence 通道）。"""
        conn = make_raw_db(tmp_path / "life.db")
        insert_lesson(conn, "timeout", goal_pattern="批量图片转码")
        insert_lesson(conn, "timeout", goal_pattern="批量图片转码")
        conn.close()
        b = _bridge_with_db(tmp_path)
        hint = b._failure_prior_hint("完全无关的任务: 写周报")
        # Phase A0+: bridge 动态调用 cause_to_procedure(cause, goal_pattern)
        # goal_pattern 含"批量"关键词 → 命中批量操作程序模板（含"每批"/"分批"）
        assert "timeout" in hint and ("每批" in hint or "分批" in hint)


def _bridge_with_db(tmp_path):
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge.__new__(DecisionBridge)
    b._db_path = str(tmp_path / "life.db")
    return b


# ── S3 自主提案 ──────────────────────────────────────────────────────────

class TestS3AutonomousProposal:
    def test_level2_produces_audited_rate_limited_proposals(
            self, tmp_path, monkeypatch):
        from ocos.execution.autonomy import set_autonomy_level
        set_autonomy_level(2)                    # 写入 tmp override 文件

        db = tmp_path / "life.db"
        seed_episode(db, source="lesson",
                     decision="[LESSON] timeout 假设",
                     tags=["failure_lesson", "timeout"])
        seed_episode(db, source="lesson",
                     decision="[LESSON] timeout 假设二",
                     tags=["failure_lesson", "timeout"])

        from ocos.execution.pending import PendingStore
        store = PendingStore(str(tmp_path / "pending.db"))
        notified: list[str] = []
        from ocos.daemon.motivation import MotivationHub
        hub = MotivationHub(db_path=str(db), pending_store=store,
                            notify_fn=notified.append)

        stats = hub.scan()
        assert stats["level"] == 2
        assert stats["proposed"] >= 1
        assert stats["pending_enqueued"] >= 1    # 待批落地（非直写）
        # 全程审计: 提案 episode 可溯源
        import sqlite3
        conn = sqlite3.connect(str(db))
        n = conn.execute(
            "SELECT COUNT(*) FROM episodes "
            "WHERE source='autonomous_goal_proposal'").fetchone()[0]
        conn.close()
        assert n == stats["proposed"]
        # outbox 通知（提案即推送待批提示）
        assert notified and "自主目标提案" in notified[0]
        # 待批队列可审批消费
        import json as _json
        pconn = sqlite3.connect(str(tmp_path / "pending.db"))
        rows = pconn.execute(
            "SELECT action_type, status FROM pending_actions").fetchall()
        pconn.close()
        assert any(r[0] == "autonomous_goal" and r[1] == "pending"
                   for r in rows)

        # 限速: 当日已达 cap → capped 且零新增提案
        monkeypatch.setenv("OCOS_AUTONOMY_GOAL_CAP", "1")
        stats2 = hub.scan()
        assert stats2["capped"] is True
        assert stats2["proposed"] == 0

    def test_level0_silence(self, tmp_path):
        """R3 红线场景侧写: LEVEL=0 零自主提案（诚实沉默）。"""
        from ocos.execution.autonomy import set_autonomy_level
        set_autonomy_level(0)
        db = tmp_path / "life.db"
        seed_episode(db, source="lesson", decision="[LESSON] x",
                     tags=["failure_lesson", "timeout"])
        from ocos.daemon.motivation import MotivationHub
        hub = MotivationHub(db_path=str(db))
        stats = hub.scan()
        assert stats["proposed"] == 0 and stats["candidates"] == 0


# ── S4 好奇心探测 ────────────────────────────────────────────────────────

class TestS4CuriosityProbe:
    def test_low_confidence_belief_triggers_readonly_probe(
            self, tmp_path):
        from datetime import datetime, timezone
        from ocos.memory.belief.models import Belief, BeliefStatus
        from ocos.memory.belief.store import BeliefStore
        bstore = BeliefStore(db_path=str(tmp_path / "life.db"))
        bstore.initialize()
        now = datetime.now(timezone.utc)
        bstore.save(Belief(
            id="BEL-PROBE-1",
            statement="容器化部署可降低发布失败率",
            source_knowledge_ids=(), evidence_ids=("EV-SEED-1",),
            confidence=0.45, uncertainty=0.55, scope={},
            status=BeliefStatus.WEAKENED,
            created_at=now, last_updated=now))

        db = tmp_path / "life.db"
        from ocos.execution.pending import PendingStore
        from ocos.daemon.motivation import MotivationHub
        hub = MotivationHub(db_path=str(db),
                            pending_store=PendingStore(
                                str(tmp_path / "pending.db")),
                            belief_store=bstore)
        cands = hub.collect_candidates()
        probes = [c for c in cands if c.kind == "PROBE"]
        assert probes, "低置信边界未产生探测候选"
        p = probes[0]
        assert "只读探测" in p.description
        assert "容器化部署可降低发布失败率" in p.description
        assert "0.45" in p.evidence

        from ocos.execution.autonomy import set_autonomy_level
        set_autonomy_level(2)
        stats = hub.scan()
        assert stats["proposed"] >= 1
        # 提案 payload 标注 PROBE（执行闸可据此限制只读）
        import sqlite3, json as _json
        pconn = sqlite3.connect(str(tmp_path / "pending.db"))
        payload_row = pconn.execute(
            "SELECT payload_json FROM pending_actions WHERE "
            "action_type='autonomous_goal'").fetchone()
        pconn.close()
        assert payload_row is not None
        assert _json.loads(payload_row[0])["kind"] == "PROBE"


# ── S5 主动汇报 ──────────────────────────────────────────────────────────

class TestS5ProactiveReport:
    def test_autonomous_goal_result_pushed_to_outbox(self, tmp_path):
        """自主目标完成 → goal_result episode → outbox 秒级推送（UX-J）。"""
        from ocos.daemon import ResidentRuntime
        from ocos.execution.autonomy import set_autonomy_level
        set_autonomy_level(2)
        db = tmp_path / "life.db"

        inbox = FakeInbox(str(db))
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._user_inbox = inbox
        rt._result_push_lock = threading.Lock()
        rt._result_cursor_init = False
        rt._last_result_rowid = 0
        rt._channel_link = None
        rt._autonomous_inflight = deque(["GOAL-AUTO-test1"])
        rt._motivation = None
        rt._recent_goal_push = {}        # UX-J2: retry 去重（2026-09-10 新增属性）
        rt._goal_retry_counts = {}

        # 历史结果先落库（首次推送只定位游标，历史不重播）
        seed_episode(db, source="goal_result", action="goal_result",
                     decision="✓ 历史结果（不应重播）", tags=["goal_result"])
        rt._push_goal_results()                  # 游标初始化（历史不重播）
        seed_episode(db, source="goal_result", action="goal_result",
                     decision="✓ 完成「容器镜像清理」探测（自主目标）",
                     tags=["goal_result"],
                     outcome={"success": True})
        rt._push_goal_results()                  # 新结果即时推送
        assert any("目标执行完成" in m and "容器镜像清理" in m
                   for m in inbox.outbound)
        assert len(rt._autonomous_inflight) == 0   # FIFO 配对消费

    def test_result_paired_with_motivation_result_loop(self, tmp_path):
        """在途自主目标结果经推送链配对 → MotivationHub 结果闭环。"""
        from ocos.daemon import ResidentRuntime
        db = tmp_path / "life.db"
        inbox = FakeInbox(str(db))

        from ocos.daemon.motivation import MotivationHub
        hub = MotivationHub(db_path=str(db))

        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._user_inbox = inbox
        rt._result_push_lock = threading.Lock()
        rt._result_cursor_init = False
        rt._last_result_rowid = 0
        rt._channel_link = None
        rt._autonomous_inflight = deque(["GOAL-AUTO-x"])
        rt._motivation = hub
        rt._recent_goal_push = {}        # UX-J2: retry 去重（2026-09-10 新增属性）
        rt._goal_retry_counts = {}

        seed_episode(db, source="goal_result", action="goal_result",
                     decision="✓ 历史结果", tags=["goal_result"])
        rt._push_goal_results()
        seed_episode(db, source="goal_result", action="goal_result",
                     decision="✗ 探测任务失败（真实 outcome）",
                     tags=["goal_result"], outcome={"success": False})
        rt._push_goal_results()
        # 连败 1 次（阈值 3 未触发 → 无降级，但计数进入闭环）
        assert hub._consecutive_failures == 1
        assert any("目标执行完成" in m for m in inbox.outbound)
