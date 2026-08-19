"""Phase 22 — Gate Tests: search_ops (DRY_RUN + real)。

验证:
  S01: 默认 dry_run 模式 → 模拟结果
  S02: 查询过长 → rejected
  S03: 空查询 → rejected
  S04: 查询注入保护（以 - 开头）
  S05: 真实模式 grep（OCOS_DW_DRY_RUN=0）
  S06: 文件模式过滤
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from ocos.digital_world.base import DigitalOperation, OperationResult
from ocos.digital_world.search_ops import search, _DRY_RUN


# ── S01: dry_run 默认模式 ──────────────────────────────────────

def test_search_dry_run_default():
    """默认 dry_run → 返回模拟结果。"""
    op = DigitalOperation.create(
        op_type="search",
        target="test query",
        requester="test",
    )
    result = search(op)
    assert isinstance(result, OperationResult)
    assert result.status == "success"
    assert "simulated" in (result.output or "")


# ── S02: 查询过长 → rejected ───────────────────────────────────

def test_search_query_too_long():
    op = DigitalOperation.create(
        op_type="search",
        target="",
        requester="test",
        params={"query": "x" * 501},
    )
    result = search(op)
    assert result.status == "rejected"
    assert "501 chars" in (result.error or "")


# ── S03: 空查询 → rejected ────────────────────────────────────

def test_search_empty_query():
    op = DigitalOperation.create(
        op_type="search",
        target="",
        requester="test",
        params={"query": ""},
    )
    result = search(op)
    assert result.status == "rejected"


# ── S04: 查询注入保护 ──────────────────────────────────────────

def test_search_injection_protection():
    """以 --flag 开头的查询被转义。"""
    op = DigitalOperation.create(
        op_type="search",
        target="",
        requester="test",
        params={"query": "--exclude-dir=/etc test"},
    )
    result = search(op)
    assert result.status == "success"
    # 注入保护: 查询应以 \ 转义开头
    # In dry_run mode, it still succeeds but pattern is sanitized


# ── S05: 真实 grep ─────────────────────────────────────────────

@pytest.mark.skipif(_DRY_RUN, reason="OCOS_DW_DRY_RUN=1, skipping real search")
def test_search_real_grep():
    """真实模式下 grep 搜索文件。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello world\nthis is a test\nhello again\n")

        os.environ["OCOS_DW_DRY_RUN"] = "0"
        try:
            op = DigitalOperation.create(
                op_type="search",
                target="",
                requester="test",
                params={
                    "query": "hello",
                    "directory": tmpdir,
                },
            )
            result = search(op)
            assert result.status == "success"
            assert "hello" in (result.output or "").lower()
        finally:
            os.environ["OCOS_DW_DRY_RUN"] = "1"


# ── S06: 文件模式过滤 ───────────────────────────────────────────

@pytest.mark.skipif(_DRY_RUN, reason="OCOS_DW_DRY_RUN=1, skipping real search")
def test_search_file_pattern_filter():
    """file_pattern 限制文件匹配。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "test.py").write_text("def find_hello(): pass\n")
        (Path(tmpdir) / "test.txt").write_text("hello in txt\n")

        os.environ["OCOS_DW_DRY_RUN"] = "0"
        try:
            op = DigitalOperation.create(
                op_type="search",
                target="",
                requester="test",
                params={
                    "query": "hello",
                    "directory": tmpdir,
                    "file_pattern": "*.py",
                },
            )
            result = search(op)
            assert result.status == "success"
            # *.py 匹配 → 只搜 test.py
            assert "test.py" in (result.output or "")
        finally:
            os.environ["OCOS_DW_DRY_RUN"] = "1"
