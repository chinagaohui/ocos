"""Phase 29 — 文件操作: file_read / file_write / file_delete。

约束:
  - 文件大小限制 10MB
  - 大内容截断 <4000 字符
  - 写入/删除需审批
  - 路径安全（不删关键文件）
"""

from __future__ import annotations

import os

from ocos.digital_world.base import (
    DigitalOperation, OperationResult, MAX_FILE_SIZE_BYTES, MAX_FILE_CONTENT_CHARS,
)

# 关键文件保护列表
PROTECTED_PATHS: tuple[str, ...] = (
    "/etc/passwd",
    "/etc/shadow",
    "/boot",
    "~/.ssh",
    "~/.hermes",
)


def _is_protected(path: str) -> bool:
    abs_path = os.path.abspath(os.path.expanduser(path))
    for p in PROTECTED_PATHS:
        protected_abs = os.path.abspath(os.path.expanduser(p))
        if abs_path.startswith(protected_abs):
            return True
    return False


def file_read(op: DigitalOperation) -> OperationResult:
    """读取文件。"""
    import time
    start = time.monotonic()

    path = os.path.expanduser(op.target)

    try:
        size = os.path.getsize(path)
    except OSError as e:
        return OperationResult.failure(op.op_id, str(e))

    if size > MAX_FILE_SIZE_BYTES:
        return OperationResult.rejected(
            op.op_id,
            f"file too large: {size} bytes (max {MAX_FILE_SIZE_BYTES})",
        )

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_FILE_CONTENT_CHARS + 1)
    except OSError as e:
        return OperationResult.failure(op.op_id, str(e))

    truncated = len(content) > MAX_FILE_CONTENT_CHARS
    if truncated:
        content = content[:MAX_FILE_CONTENT_CHARS]

    duration_ms = int((time.monotonic() - start) * 1000)
    suffix = "\n[TRUNCATED]" if truncated else ""
    return OperationResult.success(op.op_id, content + suffix, duration_ms)


def file_write(op: DigitalOperation) -> OperationResult:
    """写入文件（需审批）。"""
    import time
    start = time.monotonic()

    if _is_protected(op.target):
        return OperationResult.rejected(op.op_id, "protected path denied")

    content = op.params.get("content", "")
    mode = op.params.get("mode", "w")

    if not isinstance(content, str):
        return OperationResult.failure(op.op_id, "content must be str")

    try:
        path = os.path.expanduser(op.target)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
    except OSError as e:
        return OperationResult.failure(op.op_id, str(e))

    duration_ms = int((time.monotonic() - start) * 1000)
    return OperationResult.success(op.op_id, f"wrote {len(content)} bytes", duration_ms)


def file_delete(op: DigitalOperation) -> OperationResult:
    """删除文件（需审批，不删关键文件）。"""
    import time
    start = time.monotonic()

    if _is_protected(op.target):
        return OperationResult.rejected(op.op_id, "protected path denied")

    try:
        path = os.path.expanduser(op.target)
        os.remove(path)
    except OSError as e:
        return OperationResult.failure(op.op_id, str(e))

    duration_ms = int((time.monotonic() - start) * 1000)
    return OperationResult.success(op.op_id, f"deleted {op.target}", duration_ms)
