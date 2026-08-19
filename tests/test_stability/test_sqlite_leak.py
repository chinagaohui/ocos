"""Phase 23-B: SQLite 连接泄漏检测测试 (23b3)。

验证:
  - IdentityStore 关闭后不持有连接
  - 多次创建/关闭不泄漏 FD
  - storage.connection 池正确回收
"""
import gc
import os
import tempfile
from pathlib import Path

import pytest

from ocos.auth.identity_store import IdentityStore, AgentIdentityRecord
from ocos.storage.connection import get_connection, close, close_all


def _count_open_fds() -> int:
    """近似计数当前进程的打开 FD 数。"""
    try:
        return len(os.listdir(f"/proc/{os.getpid()}/fd"))
    except Exception:
        return -1


class TestSQLiteConnectionLeak:
    """连接泄漏检测。"""

    def test_identity_store_context_manager_closes(self):
        """Context Manager 退出后连接应不可用。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with IdentityStore(db_path) as store:
                assert store.verify_identity("test") is False
            # 退出 context manager 后
            assert store._conn is None
        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_multiple_open_close_no_fd_growth(self):
        """多次创建/关闭 IdentityStore 不导致 FD 增长（池化连接复用）。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            initial_fds = _count_open_fds()

            for i in range(20):
                store = IdentityStore(db_path)
                store.save(AgentIdentityRecord(agent_id=f"agent_{i}", name=f"Agent{i}"))
                store.close()

                if i == 0 or i == 19:
                    gc.collect()

            gc.collect()
            final_fds = _count_open_fds()

            if initial_fds > 0 and final_fds > 0:
                growth = final_fds - initial_fds
                # 允许小幅增长（池化连接复用，不应指数增长）
                assert growth < 50, f"FD growth too high: {initial_fds} → {final_fds} (Δ={growth})"
        finally:
            close(db_path)
            Path(db_path).unlink(missing_ok=True)

    def test_connection_pool_reuse(self):
        """get_connection 对同一路径返回同一连接。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn1 = get_connection(db_path)
            conn2 = get_connection(db_path)
            assert conn1 is conn2
        finally:
            close(db_path)
            Path(db_path).unlink(missing_ok=True)

    def test_close_all_cleans_up(self):
        """close_all 清空所有缓存连接。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = get_connection(db_path)
            assert conn is not None
            close_all()
            # 之后 get_connection 应返回新连接
            conn2 = get_connection(db_path)
            assert conn2 is not conn  # 旧的已关闭
        finally:
            close(db_path)
            Path(db_path).unlink(missing_ok=True)
