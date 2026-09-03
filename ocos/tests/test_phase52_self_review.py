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

    def test_code_assets_collected(self):
        """R1 双域: 采集真实仓库代码资产。"""
        ev = SelfReviewCollector(_make_db()).collect()
        assert ev.repo_root  # 自动定位仓库
        assert ev.capability_modules  # 非空
        assert "reflection" in ev.capability_modules  # 本模块所在
        assert ev.test_files_total > 0

    def test_self_checks_pass(self):
        """R3 自检: 干净数据 → evidence_consistent=True。"""
        ev = SelfReviewCollector(_make_db()).collect()
        assert ev.evidence_consistent, ev.evidence_note
        ids = {c["id"] for c in ev.evidence_checks}
        assert "C1" in ids and "C3" in ids and "C4" in ids

    def test_self_check_failure_detected(self):
        """R3 自检: success+failed > total → 断言失败标记。"""
        ev = ReviewEvidence()
        ev.episodes_total = 10
        ev.episodes_success = 8
        ev.episodes_failed = 5  # 13 > 10 → 不一致
        ev.repo_root = str(Path(__file__).resolve().parent.parent.parent)
        SelfReviewCollector(_make_db())._run_self_checks(ev)
        assert not ev.evidence_consistent
        assert any(c["id"] == "C1" and not c["pass"] for c in ev.evidence_checks)

    def test_time_window_7d(self):
        """R2 时间窗: created_at 近7天过滤。"""
        path = _make_db()
        con = sqlite3.connect(path)
        # 追加: 7 天前的失败 + 今天的失败
        con.execute(
            "INSERT INTO episodes VALUES ('E4','','','{}','旧任务',"
            "'✗ 旧规划失败', '', '{\"success\": false}', NULL, 0,'','','',"
            "'', datetime('now', '-10 days'))")
        con.execute(
            "INSERT INTO episodes VALUES ('E5','','','{}','新任务',"
            "'✗ LLM 规划失败: proxy', '', '{\"success\": false}', NULL, 0,'','','',"
            "'', datetime('now', '-1 hour'))")
        con.commit()
        con.close()
        ev = SelfReviewCollector(path).collect()
        pat7 = {p["pattern"]: p["count"] for p in ev.failure_patterns_7d}
        # 7d 内: E2(now,模糊) + E3(now,规划失败) + E5(1h前,规划失败)
        # 7d 外: E4(10天前,旧规划失败) 不入窗
        assert pat7.get("规划失败") == 2, f"got {pat7}"
        assert pat7.get("模糊") == 1, f"got {pat7}"
        total_7d = sum(pat7.values())
        assert total_7d == 3, f"7d 应含 3 条 (E2+E3+E5), got {pat7}"


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
