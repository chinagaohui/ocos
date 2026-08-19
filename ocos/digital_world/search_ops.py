"""Phase 22/29 — 搜索操作: search。

约束:
  - 查询长度限制 SEARCH_QUERY_MAX_LEN (500)
  - dry_run 模式 (OCOS_DW_DRY_RUN=1) 返回模拟结果
  - 真实模式: subprocess grep -rn 搜索文件系统
"""

from __future__ import annotations

import os
import re
import subprocess
import time

from ocos.digital_world.base import DigitalOperation, OperationResult, SEARCH_QUERY_MAX_LEN

# ── dry_run gate ────────────────────────────────────────────────

_DRY_RUN = os.getenv("OCOS_DW_DRY_RUN", "1") == "1"

# 默认搜索目录
_DEFAULT_SEARCH_DIR = "."

# 安全限制
_MAX_RESULTS = 200
_MAX_OUTPUT_BYTES = 50_000
_SEARCH_TIMEOUT_SECONDS = 10


# ── 真实搜索实现 ────────────────────────────────────────────────


def _grep_filesystem(query: str, directory: str, file_pattern: str | None = None) -> tuple[bool, str]:
    """使用 grep -rn 搜索文件系统。

    Args:
        query: 搜索模式（regex）
        directory: 搜索根目录
        file_pattern: 可选的文件匹配模式（如 '*.py'）

    Returns:
        (success, output_or_error)
    """
    cmd = ["grep", "-rn", "--color=never", "-I"]
    if file_pattern:
        cmd.extend(["--include", file_pattern])
    cmd.extend([query, directory])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_SEARCH_TIMEOUT_SECONDS,
        )
        output = result.stdout
        # 截断
        if len(output.encode("utf-8")) > _MAX_OUTPUT_BYTES:
            output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated)"
        # 限制结果行数
        lines = output.strip().split("\n")
        if len(lines) > _MAX_RESULTS:
            output = "\n".join(lines[:_MAX_RESULTS]) + f"\n... ({len(lines) - _MAX_RESULTS} more results)"

        if result.returncode == 1 and not output:
            return True, "no matches found"
        return True, output or "no matches found"
    except subprocess.TimeoutExpired:
        return False, f"search timed out after {_SEARCH_TIMEOUT_SECONDS}s"
    except FileNotFoundError:
        return False, "grep not available"
    except Exception as e:
        return False, f"search failed: {e}"


# ── 安全检查 ─────────────────────────────────────────────────────

# 危险模式：防止注入
_DANGEROUS_FLAGS = re.compile(r"--?[a-z]+\s")


def _sanitize_query(query: str) -> str:
    """基本清理 — 移除 grep 标志注入。"""
    query = query.strip()
    if not query:
        return query
    # 防止以 '-' 开头的 flag injection
    if query.startswith("-"):
        return re.escape(query)
    return query


# ── 公开操作函数 ─────────────────────────────────────────────────


def search(op: DigitalOperation) -> OperationResult:
    """执行搜索。dry_run 时模拟，否则执行真实 grep。

    op.params:
      - query: 搜索模式 (str)
      - directory: 搜索目录 (str, 默认 ".")
      - file_pattern: 文件匹配 (str, 可选, 如 "*.py")
    """
    start = time.monotonic()

    query = op.params.get("query", op.target)
    if not query or len(query) > SEARCH_QUERY_MAX_LEN:
        return OperationResult.rejected(
            op.op_id,
            f"query invalid: {len(query) if query else 0} chars (max {SEARCH_QUERY_MAX_LEN})",
        )

    # 清理注入
    clean_query = _sanitize_query(query)

    # dry_run
    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id,
            f"search '{query[:50]}...' → N results (simulated)",
            duration_ms,
        )

    # 真实搜索
    directory = op.params.get("directory", _DEFAULT_SEARCH_DIR)
    file_pattern = op.params.get("file_pattern")

    ok, output = _grep_filesystem(clean_query, directory, file_pattern)
    duration_ms = int((time.monotonic() - start) * 1000)

    if ok:
        return OperationResult.success(op.op_id, output, duration_ms)
    return OperationResult.failure(op.op_id, output, duration_ms)
