"""OCOS CLI parser 不变式测试。

每个顶层命令和子命令结构完整性。
"""

import pytest
import argparse

from ocos.interaction.cli.parser import build_parser


@pytest.fixture
def parser():
    return build_parser()


class TestTopLevelCommands:
    """顶层命令完整覆盖。"""

    def test_parser_builds(self, parser):
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "ocos"

    def test_goal_subcommand(self, parser):
        args = parser.parse_args(["goal", "create", "test"])
        assert args.command == "goal"
        assert args.goal_action == "create"
        assert args.input == "test"

    def test_plan_subcommand(self, parser):
        args = parser.parse_args(["plan", "分析市场趋势"])
        assert args.command == "plan"
        assert args.description == "分析市场趋势"

    def test_memory_query(self, parser):
        args = parser.parse_args(["memory", "query", "科幻"])
        assert args.command == "memory"
        assert args.memory_action == "query"
        assert args.query == "科幻"

    def test_memory_recent(self, parser):
        args = parser.parse_args(["memory", "recent"])
        assert args.memory_action == "recent"

    def test_belief_list(self, parser):
        args = parser.parse_args(["belief", "list"])
        assert args.belief_action == "list"

    def test_belief_summary(self, parser):
        args = parser.parse_args(["belief", "summary"])
        assert args.belief_action == "summary"

    def test_self_status(self, parser):
        args = parser.parse_args(["self", "status"])
        assert args.self_action == "status"

    def test_self_identity(self, parser):
        args = parser.parse_args(["self", "identity"])
        assert args.self_action == "identity"

    def test_trace_show(self, parser):
        args = parser.parse_args(["trace", "show", "TRC-001"])
        assert args.trace_action == "show"
        assert args.trace_id == "TRC-001"

    def test_run_defaults(self, parser):
        args = parser.parse_args(["run"])
        assert args.ticks == 0
        assert args.interval == 5.0
        assert args.agent_id == "ocos-master"

    def test_run_with_ticks(self, parser):
        args = parser.parse_args(["run", "--ticks", "100", "--interval", "1.0"])
        assert args.ticks == 100
        assert args.interval == 1.0

    def test_chat_defaults(self, parser):
        args = parser.parse_args(["chat"])
        assert args.host == "localhost"
        assert args.port == 8900

    def test_chat_resume(self, parser):
        args = parser.parse_args(["chat", "-r", "会话ID"])
        assert args.resume == "会话ID"

    def test_growth_ingest(self, parser):
        args = parser.parse_args([
            "growth", "ingest",
            "--summary", "这是一条关于Python异步编程性能优化的技术信号摘要内容，详细内容涉及asyncio和await关键字的使用技巧，需要达到一定长度才能通过验证",
        ])
        assert args.growth_action == "ingest"
        assert len(args.summary) >= 60

    def test_growth_analyze(self, parser):
        args = parser.parse_args(["growth", "analyze"])
        assert args.growth_action == "analyze"

    def test_growth_status(self, parser):
        args = parser.parse_args(["growth", "status", "--limit", "5"])
        assert args.limit == 5

    def test_no_command_returns_error(self, parser):
        args = parser.parse_args([])
        assert args.command is None


class TestGoalSubcommands:
    def test_goal_create_with_domain(self, parser):
        args = parser.parse_args([
            "goal", "create", "写小说",
            "--domain", "writing", "--priority", "4"
        ])
        assert args.domain == "writing"
        assert args.priority == 4

    def test_goal_create_invalid_domain(self, parser):
        with pytest.raises(SystemExit):
            parser.parse_args(["goal", "create", "x", "--domain", "invalid"])

    def test_goal_status(self, parser):
        args = parser.parse_args(["goal", "status", "GOAL-abc"])
        assert args.goal_id == "GOAL-abc"

    def test_goal_list(self, parser):
        args = parser.parse_args(["goal", "list"])
        assert args.goal_action == "list"


class TestApprovalsSubcommands:
    def test_approvals_list(self, parser):
        args = parser.parse_args(["approvals", "list"])
        assert args.approvals_action == "list"

    def test_approvals_approve(self, parser):
        args = parser.parse_args(["approvals", "approve", "PEND-001"])
        assert args.pending_id == "PEND-001"

    def test_approvals_deny(self, parser):
        args = parser.parse_args(["approvals", "deny", "PEND-002"])
        assert args.pending_id == "PEND-002"


class TestOrganSubcommands:
    def test_organ_generate(self, parser):
        args = parser.parse_args([
            "organ", "generate", "大纲文本",
            "--title", "科幻小说", "--chapters", "10"
        ])
        assert args.content == "大纲文本"
        assert args.title == "科幻小说"
        assert args.chapters == 10

    def test_organ_status(self, parser):
        args = parser.parse_args(["organ", "status"])
        assert args.organ_action == "status"


class TestRegulateFeedback:
    def test_regulate(self, parser):
        args = parser.parse_args(["regulate", "科幻小说", "--max-chapters", "20"])
        assert args.project == "科幻小说"
        assert args.max_chapters == 20

    def test_feedback(self, parser):
        args = parser.parse_args(["feedback", "科幻小说"])
        assert args.project == "科幻小说"
