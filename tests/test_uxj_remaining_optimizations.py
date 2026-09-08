"""UX-J+ 剩余优化项测试: 按行截断 / 域推断 / 复盘素材注入。"""
import sqlite3

import pytest

from ocos.agent.agent_runtime import _truncate_text
from ocos.execution.bridge import DecisionBridge
from ocos.interaction.cli.commands.goal import infer_domain


class TestTruncateOnLineBoundary:
    def test_short_text_untouched(self):
        assert _truncate_text("abc", 100) == "abc"

    def test_cut_falls_back_to_line_boundary(self):
        lines = "\n".join(f"line-{i} " + "x" * 50 for i in range(40))
        out = _truncate_text(lines, 300)
        assert len(out) < 400
        assert out.endswith("…（已截断，原文 {} 字符）".format(len(lines)))
        # 截断点之前的所有行必须完整（无半行）
        body = out.rsplit("\n…（已截断", 1)[0]
        for ln in body.split("\n"):
            assert ln.startswith("line-")
            assert ln.endswith("x" * 50) or ln.startswith("line-")

    def test_no_newline_falls_back_hard_cut(self):
        out = _truncate_text("y" * 500, 100)
        assert out.startswith("y" * 100)
        assert "已截断" in out


class TestInferDomain:
    def test_analysis_keywords(self):
        assert infer_domain("探索宿主机现状：操作系统/内存/磁盘").value == "analysis"
        assert infer_domain("统计本机 CPU 负载").value == "analysis"

    def test_writing_keywords(self):
        assert infer_domain("帮我写一本科幻小说").value == "writing"

    def test_research_keywords(self):
        assert infer_domain("调研科幻小说市场趋势").value == "research"

    def test_default_development(self):
        assert infer_domain("修复登录页面的空指针异常").value == "development"

    def test_writing_beats_analysis_when_both(self):
        # "写分析报告" → 写作优先（产出物是文档）
        assert infer_domain("写一份系统健康分析报告").value == "writing"


@pytest.fixture
def bridge_with_db(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE episodes (id INTEGER PRIMARY KEY, decision TEXT, "
        "tags TEXT, created_at TEXT)")
    conn.execute(
        "INSERT INTO episodes (decision, tags, created_at) VALUES (?, ?, ?)",
        ("【结论摘要】磁盘 61%。\n【原始输出】Filesystem ...",
         "goal_result", "2026-09-06T05:38:00"))
    conn.commit()
    conn.close()
    return DecisionBridge(db_path=str(db))


class TestRetrospectHint:
    def test_retrospect_task_injects_results(self, bridge_with_db):
        hint = bridge_with_db._retrospect_hint("学习总结：复盘本轮四个目标")
        assert "【近期目标执行结果（复盘素材，真实记录）】" in hint
        assert "磁盘 61%" in hint
        assert "禁止扫描文件系统" in hint
        assert "uname/df/free" in hint

    def test_non_retrospect_task_no_inject(self, bridge_with_db):
        assert bridge_with_db._retrospect_hint("分析宿主机状态") == ""

    def test_no_goal_results_empty(self, tmp_path):
        db = tmp_path / "empty.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE episodes (decision TEXT, tags TEXT, "
                     "created_at TEXT)")
        conn.commit()
        conn.close()
        b = DecisionBridge(db_path=str(db))
        assert b._retrospect_hint("复盘本轮目标") == ""
