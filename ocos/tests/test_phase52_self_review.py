"""Phase 52: self review 自省采集器测试。

验收:
    R1: 失败判定正确 — 成功 episode ("blocked": False) 不计入失败
    R2: belief 用 scope 分组 (无 domain 列不报错)
    R3: 证据结构完整
    R4: 报告渲染含关键节
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ocos.reflection.self_review import (  # noqa: E402
    ReviewEvidence,
    SelfReviewCollector,
    render_markdown,
    write_report,
)


def _make_db() -> str:
    """构造含成功/失败 episode 的临时 DB。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE episodes (
            id TEXT, experience_id TEXT, session_id TEXT, context TEXT,
            goal TEXT, decision TEXT, action TEXT, outcome TEXT,
            condition TEXT, significance_score REAL, evaluation_trace TEXT,
            source TEXT, status TEXT, tags TEXT, created_at TEXT);
        CREATE TABLE goal (
            goal_id TEXT, level TEXT, description TEXT, parent_id TEXT,
            priority REAL, created_at TEXT, deadline TEXT, status TEXT,
            result_json TEXT, origin_level TEXT, authority TEXT,
            domain TEXT, caller TEXT);
        CREATE TABLE belief (
            id TEXT, statement TEXT, source_knowledge_ids TEXT,
            evidence_ids TEXT, confidence REAL, uncertainty REAL,
            scope TEXT, status TEXT, created_at TEXT, last_updated TEXT);
        CREATE TABLE event_store (
            event_id TEXT, event_type TEXT, payload TEXT, source TEXT,
            created_at TEXT, sequence INTEGER);
        CREATE TABLE working_memory (
            key TEXT, value TEXT, created_at TEXT, expires_at TEXT,
            ttl_seconds INTEGER);
    """)
    # 成功 episode: outcome 含 "blocked": false — 不得误判为失败
    con.execute(
        "INSERT INTO episodes VALUES ('E1','','','{}','查系统','✓ uname ok',"
        "'','{\"ok\": true, \"blocked\": false, \"success\": true}',NULL,0,'','','','','now')")
    # 真失败: 模糊
    con.execute(
        "INSERT INTO episodes VALUES ('E2','','','{}','分析数据',"
        "'{\"status\": \"failed\", \"reason\": \"任务描述过于模糊\"}',"
        "'','{\"success\": false}',NULL,0,'','','','','now')")
    # 真失败: 规划失败
    con.execute(
        "INSERT INTO episodes VALUES ('E3','','','{}','执行命令',"
        "'✗ LLM 规划失败: openai package not installed',"
        "'','{\"success\": false}',NULL,0,'','','','','now')")
    # goal
    con.execute("INSERT INTO goal VALUES ('G1','USER','g1','',3,'now',"
                "'','COMPLETED','','HUMAN','FRAMEWORK','analysis','cli')")
    con.execute("INSERT INTO goal VALUES ('G2','USER','g2','',3,'now',"
                "'','PENDING','','HUMAN','FRAMEWORK','analysis','cli')")
    # beliefs
    con.execute("INSERT INTO belief VALUES ('B1','信念1','','',0.8,0.1,"
                "'self','active','now','now')")
    con.execute("INSERT INTO belief VALUES ('B2','信念2','','',0.9,0.1,"
                "'world','active','now','now')")
    con.execute("INSERT INTO belief VALUES ('B3','信念3','','',0.7,0.2,"
                "'self','active','now','now')")
    # events
    con.execute("INSERT INTO event_store VALUES ('EV1','result',"
                "'{\"status\": \"failed\"}','x','now',1)")
    # wm
    con.execute("INSERT INTO working_memory VALUES ('wm:working',"
                "'{\"items\": [{\"content\": \"a\"}, {\"content\": \"b\"}]}',"
                "'now','now',60)")
    con.commit()
    con.close()
    return path


class TestCollector:
    def test_failure_detection_excludes_success(self):
        ev = SelfReviewCollector(_make_db()).collect()
        # E1 成功 (blocked: False) 不计失败; E2/E3 真失败
        assert ev.episodes_total == 3
        assert ev.episodes_failed == 2, f"失败应=2 (模糊+规划), got {ev.episodes_failed}"

    def test_failure_patterns(self):
        ev = SelfReviewCollector(_make_db()).collect()
        patterns = {p["pattern"]: p["count"] for p in ev.failure_patterns}
        assert patterns.get("模糊") == 1
        assert patterns.get("openai") == 1 or patterns.get("规划失败") == 1

    def test_belief_scope_grouping(self):
        ev = SelfReviewCollector(_make_db()).collect()
        assert ev.beliefs_total == 3
        domains = {d["domain"]: d["count"] for d in ev.beliefs_domains}
        assert domains.get("self") == 2
        assert domains.get("world") == 1

    def test_goals_and_events(self):
        ev = SelfReviewCollector(_make_db()).collect()
        assert ev.goals_by_status.get("COMPLETED") == 1
        assert ev.goals_by_status.get("PENDING") == 1
        assert ev.recent_goal_ok >= 1

    def test_working_memory_count(self):
        ev = SelfReviewCollector(_make_db()).collect()
        assert ev.working_memory_items == 2

    def test_to_dict_jsonable(self):
        ev = SelfReviewCollector(_make_db()).collect()
        json.dumps(ev.to_dict())  # 不应抛


class TestRender:
    def test_markdown_sections(self, tmp_path):
        ev = SelfReviewCollector(_make_db()).collect()
        analysis = {
            "overall_health": "良好",
            "weaknesses": [{"issue": "x", "evidence": "y", "impact": "z"}],
            "upgrades": [{"upgrade": "u", "rationale": "r", "priority": "P0"}],
            "biggest_bottleneck": "b",
        }
        md = render_markdown(ev, analysis)
        for section in ("# OCOS 自省分析报告", "## 运行概览", "## 失败模式",
                        "## 分析结论", "总体健康", "不足", "升级方向"):
            assert section in md

    def test_write_report(self, tmp_path):
        ev = ReviewEvidence()
        path = write_report("# t", out_dir=str(tmp_path))
        assert Path(path).exists()
        assert path.endswith(".md")
