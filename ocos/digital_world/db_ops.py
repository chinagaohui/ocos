"""Phase 29 — 数据库操作: db_query / db_write。

⚠️ S4.3 / 占位模块：本文件为模拟实现（返回 "simulated" 假结果，无真实
    数据库读写），v1.2 删除候选。真实数据访问走 storage/ 持久层。
    被 tests/digital_world/test_dw_db_ops.py 引用（仅测试），新代码禁止
    在生产路径调用。

约束:
  - db_query 只读（默认）
  - db_write 需审批
"""

from __future__ import annotations

import time

from ocos.digital_world.base import DigitalOperation, OperationResult


def db_query(op: DigitalOperation) -> OperationResult:
    """只读数据库查询。"""
    start = time.monotonic()

    # 模拟只读查询
    duration_ms = int((time.monotonic() - start) * 1000)
    return OperationResult.success(
        op.op_id, "query results (simulated)", duration_ms,
    )


def db_write(op: DigitalOperation) -> OperationResult:
    """数据库写入（需审批）。"""
    start = time.monotonic()

    duration_ms = int((time.monotonic() - start) * 1000)
    return OperationResult.success(
        op.op_id, "write committed (simulated)", duration_ms,
    )
