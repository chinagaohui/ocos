"""Transaction 测试。"""
from __future__ import annotations

import pytest

from ocos.stability.transaction import Transaction, TransactionManager, TransactionError


class TestTransaction:
    def test_create(self):
        """创建事务。"""
        tx = Transaction()
        assert tx.tx_id is not None
        assert not tx.committed
        assert not tx.rolled_back

    def test_add_operation(self):
        """添加操作日志。"""
        tx = Transaction()
        tx.add_operation({"type": "write", "key": "foo"})
        assert len(tx.operations) == 1

    def test_commit(self):
        """提交事务。"""
        called = []
        tx = Transaction()
        tx.on_commit(lambda: called.append("committed"))
        tx.commit()
        assert tx.committed
        assert called == ["committed"]

    def test_rollback(self):
        """回滚事务。"""
        called = []
        tx = Transaction()
        tx.on_rollback(lambda: called.append("rolled_back"))
        tx.rollback()
        assert tx.rolled_back
        assert called == ["rolled_back"]

    def test_cannot_commit_after_rollback(self):
        """回滚后不能提交。"""
        tx = Transaction()
        tx.rollback()
        with pytest.raises(TransactionError):
            tx.commit()

    def test_cannot_rollback_after_commit(self):
        """提交后不能回滚。"""
        tx = Transaction()
        tx.commit()
        with pytest.raises(TransactionError):
            tx.rollback()


class TestTransactionManager:
    def test_begin_and_current(self):
        """begin 创建当前事务。"""
        mgr = TransactionManager()
        tx = mgr.begin()
        assert mgr.current is tx
        assert mgr.depth == 1

    def test_commit_current(self):
        """commit 提交并弹出当前事务。"""
        mgr = TransactionManager()
        mgr.begin()
        mgr.commit()
        assert mgr.current is None
        assert mgr.depth == 0

    def test_rollback_current(self):
        """rollback 回滚并弹出当前事务。"""
        mgr = TransactionManager()
        mgr.begin()
        mgr.rollback()
        assert mgr.current is None

    def test_nested_transactions(self):
        """嵌套事务支持。"""
        mgr = TransactionManager()
        tx1 = mgr.begin()
        assert mgr.depth == 1
        tx2 = mgr.begin()
        assert mgr.depth == 2
        assert mgr.current is tx2
        mgr.commit()  # tx2
        assert mgr.depth == 1
        assert mgr.current is tx1
        mgr.commit()  # tx1
        assert mgr.depth == 0

    def test_commit_no_active(self):
        """没有活跃事务时 commit 报错。"""
        mgr = TransactionManager()
        with pytest.raises(TransactionError):
            mgr.commit()

    def test_rollback_no_active(self):
        """没有活跃事务时 rollback 报错。"""
        mgr = TransactionManager()
        with pytest.raises(TransactionError):
            mgr.rollback()
