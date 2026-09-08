"""L7/L8 学习闭环回归（2026-09-07 立项）。

覆盖：
- L7 失败先验注入（bridge._failure_prior_hint）：pattern 定向 / cause
  复发兜底 / 单次无匹配诚实沉默 / learning.jsonl 留痕
- V2 技能重放（bridge._skill_replay_hint + daemon._synthesize_skills）：
  经验→技能写入端 + 匹配读侧 + 命中率打点
- vitals 接线：_learning_metrics / _attribution_metrics /
  _reactivity_metrics + 终验 Gate
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ocos.execution.bridge import DecisionBridge


# ── fixtures ─────────────────────────────────────────────────────────────

def _make_bridge(tmp_path, monkeypatch):
    """最小 bridge：_failure_prior_hint/_skill_replay_hint 只依赖
    _db_path 与 _audit_learning_mark（自包含），__new__ 绕过重装配。"""
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    b = DecisionBridge.__new__(DecisionBridge)
    b._db_path = str(tmp_path / "l7.db")
    return b


def _db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "l7.db"))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id TEXT PRIMARY KEY, experience_id TEXT, created_at TEXT, "
        "session_id TEXT, context TEXT, goal TEXT, decision TEXT, "
        "action TEXT, outcome TEXT, condition TEXT, "
        "significance_score REAL, evaluation_trace TEXT, "
        "source TEXT, status TEXT, tags TEXT)")
    return conn


def _insert_lesson(conn, cause: str, goal_pattern: str = "",
                   created_at: str | None = None,
                   confidence: float = 0.7):
    now = created_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?)",
        (f"EPI-{uuid.uuid4().hex[:10]}", None, now, "tick_1",
         json.dumps({"goal_pattern": goal_pattern}, ensure_ascii=False),
         goal_pattern[:60], f"[LESSON] 失败假设", "failure_lesson",
         json.dumps({"success": False, "cause": cause,
                     "confidence": confidence}),
         f"task failed cause={cause}", 0.55, "{}", "lesson", "ACTIVE",
         json.dumps(["failure_lesson", cause])))
    conn.commit()


def _insert_goal_result(conn, goal: str, decision: str,
                        created_at: str | None = None):
    now = created_at or datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?)",
        (f"EPI-{uuid.uuid4().hex[:10]}", None, now, "tick_1",
         json.dumps({"goal": goal}, ensure_ascii=False), goal[:60],
         decision, "goal_result", json.dumps({"success": True}), "ok",
         0.8, "{}", "goal_result", "ACTIVE", "[]"))
    conn.commit()


def _learning_marks(tmp_path):
    path = tmp_path / "audit" / "learning.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


# ── L7 失败先验 ──────────────────────────────────────────────────────────

class TestFailurePriorHint:

    def test_pattern_match_injects_procedure(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "ambiguous_task",
                       goal_pattern="整理季度销售报告")
        conn.close()
        hint = b._failure_prior_hint("帮我整理季度销售报告数据")
        assert "执行程序提示" in hint
        assert "ambiguous_task" in hint
        assert "澄清目标边界" in hint          # 矫正程序而非失败叙事
        assert "✗" not in hint and "失败" not in hint.split("类任务")[0]
        marks = [m for m in _learning_marks(tmp_path)
                 if m["type"] == "lesson_prior_injected"]
        assert marks and marks[0]["cause"] == "ambiguous_task"
        assert marks[0]["mode"] == "pattern"

    def test_recurrence_fallback_for_unmatched_task(
            self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "execution_error", goal_pattern="部署生产服务")
        _insert_lesson(conn, "execution_error", goal_pattern="部署生产服务")
        conn.close()
        hint = b._failure_prior_hint("完全无关的任务：写一首诗")
        assert "execution_error" in hint       # 复发 cause 级兜底
        marks = [m for m in _learning_marks(tmp_path)
                 if m["type"] == "lesson_prior_injected"]
        assert marks and marks[0]["mode"] == "recurrence"

    def test_single_unmatched_lesson_stays_silent(
            self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "timeout", goal_pattern="批量图片转码")
        conn.close()
        assert b._failure_prior_hint("写一首诗") == ""
        assert not [m for m in _learning_marks(tmp_path)
                    if m["type"] == "lesson_prior_injected"]

    def test_no_lessons_silent(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()
        assert b._failure_prior_hint("任意任务") == ""

    def test_unknown_cause_not_injected(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "unknown")
        _insert_lesson(conn, "unknown")
        conn.close()
        assert b._failure_prior_hint("任意任务") == ""   # UNKNOWN 无程序模板


# ── V2 技能重放 ──────────────────────────────────────────────────────────

class TestSkillReplay:

    def _registry(self, tmp_path):
        from ocos.capability.skill_registry import SkillRegistry
        from ocos.capability.models import Skill, SkillGraph
        reg = SkillRegistry(db_path=str(tmp_path / "capability.db"))
        reg.init_db()
        skill = Skill(id="SK-T1", name="整理季度销售报告",
                      description="按季度汇总销售数据并生成报表",
                      required_capability="decision")
        graph = SkillGraph(id="SG-T1", name="整理季度销售报告",
                           description="按季度汇总销售数据并生成报表",
                           skills=[skill], entry_point=skill.id)
        reg.save_skill(skill)
        reg.save_graph(graph)
        return reg

    def test_empty_registry_silent_and_unmarked(
            self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()                  # capability.db 不创建
        assert b._skill_replay_hint("整理季度销售报告") == ""
        assert not [m for m in _learning_marks(tmp_path)
                    if m["type"] == "skill_replay"]

    def test_match_injects_verified_steps(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()
        self._registry(tmp_path)
        hint = b._skill_replay_hint("帮我做整理季度销售报告这件事")
        assert "技能重放" in hint and "已验证" in hint
        marks = [m for m in _learning_marks(tmp_path)
                 if m["type"] == "skill_replay"]
        assert marks and marks[0]["matched"] is True

    def test_no_match_marks_trigger(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()
        self._registry(tmp_path)
        assert b._skill_replay_hint("完全无关：修复打印机") == ""
        marks = [m for m in _learning_marks(tmp_path)
                 if m["type"] == "skill_replay"]
        assert marks and marks[0]["matched"] is False

    def test_dream_synthesis_creates_replayable_skill(
            self, tmp_path, monkeypatch):
        """经验→技能写入端：同型成功 ≥2 次 → 合成 → 重放命中（S1 链）。"""
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        conn = _db(tmp_path)
        for _ in range(2):
            _insert_goal_result(conn, "整理季度销售报告",
                                "✓ 已生成季度销售汇总报表 → done")
        conn.close()
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._db_path = str(tmp_path / "l7.db")
        created = rt._synthesize_skills()
        assert created == 1
        marks = [m for m in _learning_marks(tmp_path)
                 if m["type"] == "skill_synthesized"]
        assert marks and marks[0]["count"] == 1
        # 幂等：同名图不重复合成
        assert rt._synthesize_skills() == 0
        # 重放读侧命中合成技能
        b = _make_bridge(tmp_path, monkeypatch)
        hint = b._skill_replay_hint("请整理季度销售报告并汇总")
        assert "技能重放" in hint


# ── vitals 接线 ──────────────────────────────────────────────────────────

class TestVitalsLearningMetrics:

    def _vitals(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        from ocos.monitoring.vitals import compute_vitals
        return compute_vitals(str(tmp_path / "l7.db"), window_days=7)

    def test_prior_injection_and_replay_rate(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "ambiguous_task",
                       goal_pattern="整理季度销售报告")
        _insert_lesson(conn, "execution_error",
                       goal_pattern="部署生产服务")
        conn.close()
        b._failure_prior_hint("帮我整理季度销售报告数据")   # pattern 命中
        self._registry(tmp_path) if hasattr(self, "_registry") else None
        from ocos.capability.skill_registry import SkillRegistry
        from ocos.capability.models import Skill, SkillGraph
        reg = SkillRegistry(db_path=str(tmp_path / "capability.db"))
        reg.init_db()
        sk = Skill(id="SK-V", name="数据报表汇总", description="汇总数据",
                   required_capability="decision")
        reg.save_skill(sk)
        reg.save_graph(SkillGraph(id="SG-V", name="数据报表汇总",
                                  description="汇总数据", skills=[sk],
                                  entry_point=sk.id))
        b._skill_replay_hint("做一次数据报表汇总")          # 命中
        b._skill_replay_hint("完全无关任务：浇花")          # 触发未命中
        v = self._vitals(tmp_path, monkeypatch)
        assert v["lesson_priors_available"] == 2
        assert v["lesson_prior_injections_7d"] == 1
        assert v["skill_replay_triggers_7d"] == 2
        assert v["skill_replay_matched_7d"] == 1
        assert v["skill_replay_hit_rate"] == 0.5

    def test_attribution_proxy(self, tmp_path, monkeypatch):
        conn = _db(tmp_path)
        _insert_lesson(conn, "timeout", confidence=0.8)    # 已归因
        _insert_lesson(conn, "unknown", confidence=0.5)    # UNKNOWN 兜底
        conn.close()
        v = self._vitals(tmp_path, monkeypatch)
        # 覆盖率 1/2 × 置信度均值 (0.8+0.5)/2 = 0.325
        assert v["attribution_accuracy"] == pytest.approx(0.325)
        assert v["attribution_sample_total"] == 2
        assert "attribution_accuracy" not in v["not_implemented"]

    def test_reactivity_counts_proposals(self, tmp_path, monkeypatch):
        conn = _db(tmp_path)
        now = datetime.now(timezone.utc).isoformat()
        for _ in range(3):
            conn.execute(
                "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, "
                "?, ?, ?, ?, ?, ?, ?)",
                (f"EPI-{uuid.uuid4().hex[:10]}", None, now, "t", "{}",
                 "探测", "提案", "x", "{}", "c", 0.5, "{}",
                 "autonomous_goal_proposal", "ACTIVE", "[]"))
        conn.commit()
        conn.close()
        v = self._vitals(tmp_path, monkeypatch)
        assert v["autonomous_proposals_7d"] == 3
        assert v["reactivity_actions_per_day"] == pytest.approx(3 / 7)

    def test_final_gate_uses_new_thresholds(self, tmp_path, monkeypatch):
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        _insert_lesson(conn, "timeout", goal_pattern="批量转码", confidence=1.0)
        _insert_lesson(conn, "timeout", goal_pattern="批量转码", confidence=1.0)
        conn.close()
        b._failure_prior_hint("无关任务")      # recurrence 兜底注入
        v = self._vitals(tmp_path, monkeypatch)
        # recurrence=100% > 20% → 终验违规
        from ocos.monitoring.vitals import check_thresholds
        failures = check_thresholds(v, phase="终验")
        assert any("failure_recurrence_rate" in f for f in failures)
        # L4 阶段不判终验项
        assert not any("failure_recurrence_rate" in f
                       for f in check_thresholds(v, phase="L4"))
