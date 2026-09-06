"""Phase FIX-17: 主动输出能力验证。

验证 proactive_output_callback 注入 factory，消息能写入 UserInbox。
"""

import pytest


class TestProactiveOutputCallback:
    """FIX-17: 主动输出链路 — 回调注入 + 消息落 Inbox。"""

    def _get_callback(self, agent):
        """获取代理的 proactive_output_callback（私有属性）。"""
        return getattr(agent, '_proactive_output_callback', None)

    def _build(self, *args, **kwargs):
        """P4.1: build_master_agent 返回 (agent, skill_registry) 元组。"""
        from ocos.daemon.factory import build_master_agent
        agent, _registry = build_master_agent(*args, **kwargs)
        return agent

    def test_callback_injected_in_production(self, tmp_path):
        """build_master_agent 接受 db_path，注入非 None 回调。"""
        db = str(tmp_path / "test.db")
        agent = self._build("ocos-test", db_path=db)
        assert self._get_callback(agent) is not None

    def test_callback_posts_to_inbox(self, tmp_path):
        """回调调用 → post_outbound 写入 inbox（outbound 状态）。"""
        from ocos.interaction.inbox import UserInbox

        db = str(tmp_path / "test.db")
        # 先初始化 UserInbox 创建表
        inbox = UserInbox(db_path=db)
        agent = self._build("ocos-test", db_path=db)
        callback = self._get_callback(agent)
        assert callback is not None

        before_rid = inbox.max_rowid()
        callback("主动输出消息测试")
        after_rid = inbox.max_rowid()

        assert after_rid == before_rid + 1

    def test_callback_none_without_db(self, tmp_path):
        """db_path=None 时，proactive_output_callback 为 None。"""
        agent = self._build("ocos-test", db_path=None)
        assert self._get_callback(agent) is None

    def test_memory_db_callback_none(self, tmp_path):
        """db_path=':memory:' 时，proactive_output_callback 为 None。"""
        agent = self._build("ocos-test", db_path=":memory:")
        assert self._get_callback(agent) is None

    def test_say_channel_tests_still_pass(self, tmp_path):
        """test_say_channel.py 12 项测试全通过（回归）。"""
        import subprocess
        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest",
             "ocos/tests/test_say_channel.py", "-q"],
            capture_output=True,
            cwd="/home/laogao/Documents/trae_projects/ocos",
            timeout=30,
        )
        assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()
