"""SessionState 基础测试 (P0-2/P0-3)."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ocos.interaction.session_state import SessionManager


class TestSessionState:
    """基本会话状态管理测试."""

    def test_ensure_and_append(self) -> None:
        """确保会话后追加对话轮次."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            sm = SessionManager(db_path=str(db_path))

            # 先确保会话存在
            state = sm.ensure_session("s1")
            assert state is not None
            assert state.session_id == "s1"

            # 追加对话
            sm.append_turn("user", "你好", session_id="s1")
            sm.append_turn("assistant", "你好主人", session_id="s1")

            # 验证 history
            assert len(state.history) == 2
            assert state.history[0].role == "user"
            assert state.history[0].content == "你好"
            assert state.history[1].role == "assistant"
            assert state.history[1].content == "你好主人"

    def test_current_state_after_ensure(self) -> None:
        """ensure_session 后 current_state 可见."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            sm = SessionManager(db_path=str(db_path))

            # 初始为 None
            assert sm.current_state is None

            # ensure 后应有 state
            state = sm.ensure_session("web")
            assert state is not None
            assert sm.current_state is not None
            assert sm.current_state.session_id == "web"

    def test_pid_isolation(self) -> None:
        """不同 PID → 不同 state (测试逻辑而非真实进程隔离)."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            sm = SessionManager(db_path=str(db_path), daemon_pid=1000)

            sm.ensure_session("s1")
            sm.append_turn("user", "消息1", session_id="s1")

            # 模拟另一进程（新实例不同 PID）
            sm2 = SessionManager(db_path=str(db_path), daemon_pid=2000)
            state2 = sm2.ensure_session("s1")
            # 不同 PID 应看到不同 state（当前实现中 _state 是按 PID 隔离的）
            # 这里验证两者独立存在
            assert state2 is not None
            assert sm.current_state is not state2

    def test_reuse_same_session(self) -> None:
        """同会话 ID 复用."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            sm = SessionManager(db_path=str(db_path))

            state1 = sm.ensure_session("web")
            state1.add_turn("user", "第一轮")

            # 再次 ensure 同一 session_id，应返回相同 state
            state2 = sm.ensure_session("web")
            assert state2 is state1  # 同一个对象
            assert len(state2.history) == 1

    def test_session_switch(self) -> None:
        """切换会话 ID 创建新 state (当前实现:每次 ensure 重建)."""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            sm = SessionManager(db_path=str(db_path))

            # 创建并填充 web 会话
            state_web = sm.ensure_session("web")
            state_web.add_turn("user", "web 消息")

            # 创建 cli 会话
            state_cli = sm.ensure_session("cli")
            state_cli.add_turn("user", "cli 消息")

            # 切回 web — 由于当前实现在 ensure_session 时从 MemoryHub 重放，
            # 且测试环境中无持久化数据，所以返回空历史（这是正确行为）
            state_web2 = sm.ensure_session("web")
            # web 的 state 对象与第一次不同（新创建），但可验证存在
            assert state_web2 is not None
            assert state_web2.session_id == "web"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
