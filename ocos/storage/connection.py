"""SQLite 连接管理 — 连接池、WAL 模式、超时配置。"""

from __future__ import annotations

import atexit
import logging
import os
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
    """获取或创建一个 SQLite 连接。线程安全，按路径缓存。

    :memory: 特判: 内存库不共享/不缓存, 每次返回独立连接（隔离语义）。
    file: URI 特判 (O-2): shared-cache 内存库按原样连接 (uri=True),
    不做路径解析, 以完整 URI 字符串为缓存键。
    文件路径: 连接池缓存; 若缓存连接已被外部 close, 自动重建。
    """
    # 兼容 Path 输入（2026-09-07: O-2 的 startswith 特判在 PosixPath 上炸）
    db_path = os.fspath(db_path)
    if db_path.startswith("file:"):
        with _lock:
            cached = _connections.get(db_path)
            if cached is None or not _conn_alive(cached):
                conn = sqlite3.connect(
                    db_path, timeout=timeout, check_same_thread=False, uri=True
                )
                conn.row_factory = sqlite3.Row
                _apply_pragmas(conn)
                _connections[db_path] = conn
            return _connections[db_path]

    if db_path == ":memory:":
        conn = sqlite3.connect(":memory:", timeout=timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _apply_pragmas(conn)
        return conn

    abs_path = str(Path(db_path).resolve())
    with _lock:
        cached = _connections.get(abs_path)
        if cached is None or not _conn_alive(cached):
            conn = sqlite3.connect(abs_path, timeout=timeout, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _apply_pragmas(conn)
            _connections[abs_path] = conn
        return _connections[abs_path]


def _conn_alive(conn: sqlite3.Connection) -> bool:
    """检查连接是否仍可用（未被外部 close）。"""
    try:
        conn.execute("SELECT 1")
        return True
    except sqlite3.Error:
        return False


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
    db_path = os.fspath(db_path)           # 兼容 Path 输入
    if db_path.startswith("file:"):
        key = db_path
    else:
        key = str(Path(db_path).resolve())
    with _lock:
        conn = _connections.pop(key, None)
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
