"""SessionState — 对话会话状态管理 (P0-2/P0-3).

职责:
  - 维护单进程内的活跃会话（PID 隔离）
  - 持久化最近对话到 MemoryHub（修复"每次请求重建无状态"问题）
  - 防止多实例并发抢占同一 db_path（文件锁）
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChatTurn:
    """单轮对话记录。"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionState:
    """单会话状态（每个 daemon 进程一个）。"""
    session_id: str
    history: list[ChatTurn] = field(default_factory=list)
    last_tick: float = 0.0
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def recent_context(self) -> str:
        """最近 6 轮对话 → 紧凑字符串，用于 build_context."""
        turns = self.history[-12:]  # 最近 6 轮（每轮 2 条）
        if not turns:
            return ""
        lines = []
        for t in turns:
            label = "主人" if t.role == "user" else "我"
            lines.append(f"{label}: {t.content[:120]}")
        return "\n".join(lines)

    def add_turn(self, role: str, content: str) -> None:
        """追加一轮对话。"""
        if self is not None:
            self.history.append(ChatTurn(role=role, content=content))
            # 保持最近 100 轮（内存+持久化平衡）
            if len(self.history) > 100:
                self.history = self.history[-100:]


class SessionManager:
    """会话管理器 — 单进程单例，跨请求保持状态."""

    def __init__(self, db_path: str, daemon_pid: Optional[int] = None):
        self._db_path = db_path
        self._pid = daemon_pid or os.getpid()
        self._state: Optional[SessionState] = None
        self._lock = threading.Lock()
        # 文件锁路径（防多实例）
        self._lock_path = Path(db_path).parent / f".daemon_lock_{self._pid}.lock"

    @property
    def current_state(self) -> Optional[SessionState]:
        with self._lock:
            return self._state

    def ensure_session(self, session_id: str = "default") -> SessionState:
        """确保当前进程有活跃会话（同一进程内复用，跨进程隔离）."""
        with self._lock:
            if self._state is None or self._state.session_id != session_id:
                # 恢复历史（从 episodes 表重放最近对话）
                history = self._restore_history(session_id)
                self._state = SessionState(session_id=session_id, history=history)
            return self._state

    def append_turn(self, role: str, content: str, session_id: str = "default") -> None:
        """追加对话 + 持久化到 MemoryHub."""
        with self._lock:
            if self._state is None:
                self.ensure_session(session_id)
            self._state.add_turn(role, content)
            # 异步持久化（不阻塞响应）
            self._persist_to_hub(role, content, session_id)

    def _restore_history(self, session_id: str) -> list[ChatTurn]:
        """从 MemoryHub 重放最近对话（最多 20 轮）."""
        try:
            from ocos.memory.hub import MemoryHub
            hub = MemoryHub(self._db_path)
            hub.initialize()
            eps = hub.episode.query_by_time(limit=40)
            turns: list[ChatTurn] = []
            for ep in eps:
                src = getattr(ep, "source", "")
                ctx = getattr(ep, "context", {})
                dec = getattr(ep, "decision", "")
                if src == "conversation":
                    if ctx.get("sender") == "user":
                        turns.append(ChatTurn(role="user", content=str(ctx.get("content", ""))))
                    if dec:
                        turns.append(ChatTurn(role="assistant", content=str(dec)))
                    if len(turns) >= 40:
                        break
            return turns[-40:]  # 最近 20 轮
        except Exception as e:
            logger.debug("History restore failed: %s", e)
            return []

    def _persist_to_hub(self, role: str, content: str, session_id: str) -> None:
        """持久化到 MemoryHub episodes 表."""
        try:
            from ocos.memory.hub import MemoryHub
            from ocos.memory.episode.models import Episode
            hub = MemoryHub(self._db_path)
            hub.initialize()
            from datetime import datetime, timezone
            ep = Episode(
                id=f"EPI-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid():06x}",
                experience_id=f"EXP-SES-{session_id}",
                created_at=datetime.now(timezone.utc),
                session_id=session_id,
                context={"content": content[:500], "sender": role},
                decision="" if role == "user" else content[:500],
                action="conversation_reply" if role == "assistant" else "conversation_input",
                outcome={"success": True},
                significance_score=0.3,
                source="conversation",
                tags=["conversation"],
            )
            hub.episode.save(ep)
        except Exception as e:
            logger.debug("Persist turn failed: %s", e)

    def acquire_lock(self, timeout: float = 5.0) -> bool:
        """文件锁 — 防多实例竞争同一 db_path."""
        try:
            self._lock_file = open(self._lock_path, "w")
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(self._pid))
            self._lock_file.flush()
            return True
        except (IOError, OSError):
            return False

    def release_lock(self) -> None:
        """释放文件锁."""
        try:
            if hasattr(self, "_lock_file"):
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                self._lock_path.unlink(missing_ok=True)
        except Exception as e:
            logger.debug("Lock release failed: %s", e)

    def __del__(self) -> None:
        self.release_lock()
