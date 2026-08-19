"""Transaction — 事务管理器。

支持事务的 begin / commit / rollback。
TransactionManager 维护当前上下文栈。
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


class TransactionError(Exception):
    """事务操作失败。"""


@dataclass
class Transaction:
    """事务上下文。

    一个事务包含多个操作条目（operation log），
    以及 commit / rollback 回调。
    """

    tx_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    operations: list[dict[str, Any]] = field(default_factory=list)
    _on_commit: list[Callable[[], None]] = field(default_factory=list, repr=False)
    _on_rollback: list[Callable[[], None]] = field(default_factory=list, repr=False)
    committed: bool = False
    rolled_back: bool = False

    def add_operation(self, operation: dict[str, Any]) -> None:
        """添加操作日志条目。"""
        if self.committed or self.rolled_back:
            raise TransactionError("Transaction already completed")
        self.operations.append(operation)

    def on_commit(self, callback: Callable[[], None]) -> None:
        """注册提交回调。"""
        self._on_commit.append(callback)

    def on_rollback(self, callback: Callable[[], None]) -> None:
        """注册回滚回调。"""
        self._on_rollback.append(callback)

    def commit(self) -> None:
        """提交事务。"""
        if self.rolled_back:
            raise TransactionError("Cannot commit after rollback")
        if self.committed:
            return
        self.committed = True
        for cb in self._on_commit:
            cb()

    def rollback(self) -> None:
        """回滚事务。"""
        if self.committed:
            raise TransactionError("Cannot rollback after commit")
        if self.rolled_back:
            return
        self.rolled_back = True
        for cb in self._on_rollback:
            cb()


class TransactionManager:
    """事务管理器。

    支持嵌套事务（栈式）。
    """

    def __init__(self):
        self._stack: list[Transaction] = []
        self._lock = threading.Lock()

    @property
    def current(self) -> Optional[Transaction]:
        """当前事务上下文。"""
        with self._lock:
            return self._stack[-1] if self._stack else None

    def begin(self) -> Transaction:
        """开启新事务。"""
        tx = Transaction()
        with self._lock:
            self._stack.append(tx)
        return tx

    def commit(self) -> None:
        """提交当前事务。"""
        with self._lock:
            if not self._stack:
                raise TransactionError("No active transaction to commit")
            tx = self._stack.pop()
        tx.commit()

    def rollback(self) -> None:
        """回滚当前事务。"""
        with self._lock:
            if not self._stack:
                raise TransactionError("No active transaction to rollback")
            tx = self._stack.pop()
        tx.rollback()

    @property
    def depth(self) -> int:
        """当前事务嵌套深度。"""
        return len(self._stack)
