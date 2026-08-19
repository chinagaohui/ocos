"""SQLite 连接管理 — 连接池、WAL 模式、超时配置。"""

from __future__ import annotations

import atexit
import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


# ── 全局连接池（线程级缓存）─────────────────────────────────────────────────
_connections: dict[str, sqlite3.Connection] = {}
_lock = threading.Lock()

DEFAULT_TIMEOUT: float = 10.0
DEFAULT_PRAGMAS: list[str] = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA cache_size=-8000",       # 8 MB
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
    "PRAGMA temp_store=MEMORY",
]


def get_connection(db_path: str, timeout: float = DEFAULT_TIMEOUT) -> sqlite3.Connection:
    """获取或创建一个 SQLite 连接。线程安全，按路径缓存。"""
    abs_path = str(Path(db_path).resolve())
    with _lock:
        if abs_path not in _connections or _connections[abs_path] is None:
            conn = sqlite3.connect(abs_path, timeout=timeout, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _apply_pragmas(conn)
            _connections[abs_path] = conn
        return _connections[abs_path]


def close_all() -> None:
    """关闭所有缓存的连接。"""
    with _lock:
        for path, conn in _connections.items():
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        _connections.clear()


def close(db_path: str) -> None:
    """关闭指定路径的连接。"""
    abs_path = str(Path(db_path).resolve())
    with _lock:
        conn = _connections.pop(abs_path, None)
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """应用 SQLite 性能/安全配置。"""
    for pragma in DEFAULT_PRAGMAS:
        conn.execute(pragma)


@contextmanager
def transaction(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """事务上下文管理器。成功自动 commit，异常自动 rollback。"""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# Phase 23: 进程退出时自动关闭所有连接
atexit.register(close_all)
