"""自我认知事实注入回归（2026-09-07 对话审计 D1）。

缺陷史: 执行器 LLM 只见复盘素材，在"AI 与数字生命差距"类任务中
产出"无自我模型、无经验沉淀、完全被动"等关于自身的幻觉结论 —
而事实上 SelfModel 已加载、L7/L8 学习闭环生产运行中。
修复: bridge._self_knowledge_hint 注入实测真值事实块 + 事实约束。
"""

from __future__ import annotations

import sqlite3

import pytest

from ocos.execution.bridge import DecisionBridge


def _make_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    b = DecisionBridge.__new__(DecisionBridge)
    b._db_path = str(tmp_path / "sk.db")
    return b


def _db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "sk.db"))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS episodes ("
        "id TEXT PRIMARY KEY, experience_id TEXT, created_at TEXT, "
        "session_id TEXT, context TEXT, goal TEXT, decision TEXT, "
        "action TEXT, outcome TEXT, condition TEXT, "
        "significance_score REAL, evaluation_trace TEXT, "
        "source TEXT, status TEXT, tags TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS goals ("
        "id TEXT PRIMARY KEY, title TEXT, description TEXT, "
        "domain TEXT, level TEXT, status TEXT, priority INTEGER, "
        "progress REAL, origin_level TEXT, source TEXT, "
        "created_at TEXT, updated_at TEXT, metadata TEXT)")
    return conn


class TestSelfKnowledgeHint:
    def test_self_analysis_task_gets_facts(self, tmp_path, monkeypatch):
        """自省类任务注入: 自我模型 + 记忆统计 + 事实约束。"""
        b = _make_bridge(tmp_path, monkeypatch)
        conn = _db(tmp_path)
        for i in range(5):
            conn.execute(
                "INSERT INTO episodes (id, source) VALUES (?, ?)",
                (f"E{i}", "lesson"))
        conn.commit()
        conn.close()
        hint = b._self_knowledge_hint("分析当前AI系统与真正数字生命之间的能力差距")
        assert "自我能力事实" in hint
        assert "lessons=5" in hint            # 真实统计入块
        assert "事实约束" in hint
        assert "不得声称" in hint              # 幻觉防线指令

    def test_non_self_task_noop(self, tmp_path, monkeypatch):
        """非自省类任务零开销空转。"""
        b = _make_bridge(tmp_path, monkeypatch)
        assert b._self_knowledge_hint("查看根分区磁盘使用率") == ""

    def test_empty_db_still_constrains(self, tmp_path, monkeypatch):
        """空库也注入事实约束（诚实零值 + 指令仍在）。"""
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()
        hint = b._self_knowledge_hint("复盘今天的执行情况")
        assert "episodes=0" in hint
        assert "事实约束" in hint

    def test_learning_marks_counted(self, tmp_path, monkeypatch):
        """lesson 先验注入计数来自 learning.jsonl 真值。"""
        b = _make_bridge(tmp_path, monkeypatch)
        _db(tmp_path).close()
        audit = tmp_path / "audit" / "learning.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("w", encoding="utf-8") as f:
            for i in range(3):
                f.write('{"ts": "t", "type": "lesson_prior_injected"}\n')
            f.write('{"ts": "t", "type": "external_agent_call"}\n')
        hint = b._self_knowledge_hint("总结自己的成长")
        assert "先验注入（累计）=3" in hint
