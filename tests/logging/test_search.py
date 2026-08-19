"""LogSearcher 测试。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from ocos.logging.search import LogSearcher


@pytest.fixture
def log_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write_log(log_dir: str, filename: str, entries: list[dict]):
    path = os.path.join(log_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TestLogSearcher:
    def test_search_empty_dir(self, log_dir):
        """空目录搜索返回空列表。"""
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("anything")
        assert results == []

    def test_search_basic(self, log_dir):
        """基本关键词搜索。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "2026-01-01T00:00:00.000000", "level": "INFO", "message": "started"},
            {"timestamp": "2026-01-01T00:00:01.000000", "level": "ERROR", "message": "boom"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("boom")
        assert len(results) == 1
        assert results[0]["message"] == "boom"

    def test_search_by_level(self, log_dir):
        """按 level 过滤。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "t1", "level": "INFO", "message": "info msg"},
            {"timestamp": "t2", "level": "WARNING", "message": "warn msg"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("", level="WARNING")
        assert len(results) == 1
        assert results[0]["level"] == "WARNING"

    def test_search_by_component(self, log_dir):
        """按 component 过滤。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "t1", "level": "INFO", "component": "scheduler", "message": "scheduled"},
            {"timestamp": "t2", "level": "INFO", "component": "engine", "message": "running"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("", component="engine")
        assert len(results) == 1
        assert results[0]["component"] == "engine"

    def test_search_time_range(self, log_dir):
        """按时间范围过滤。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "2026-01-01T10:00:00.000000", "message": "early"},
            {"timestamp": "2026-01-01T12:00:00.000000", "message": "noon"},
            {"timestamp": "2026-01-01T14:00:00.000000", "message": "late"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("", after="2026-01-01T11:00:00.000000", before="2026-01-01T13:00:00.000000")
        assert len(results) == 1
        assert results[0]["message"] == "noon"

    def test_search_limit(self, log_dir):
        """搜索限制条数。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": f"t{i}", "message": f"msg{i}"} for i in range(10)
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("msg", limit=3)
        assert len(results) == 3

    def test_tail(self, log_dir):
        """tail 返回最新日志。"""
        entries = [{"timestamp": f"t{i}", "message": f"msg{i}"} for i in range(10)]
        _write_log(log_dir, "app.log", entries)
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.tail(n=3)
        assert len(results) == 3
        assert results[-1]["message"] == "msg9"

    def test_stats(self, log_dir):
        """stats 返回统计信息。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "t1", "level": "INFO", "component": "scheduler", "message": "a"},
            {"timestamp": "t2", "level": "ERROR", "component": "scheduler", "message": "b"},
            {"timestamp": "t3", "level": "INFO", "component": "engine", "message": "c"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        s = searcher.stats()
        assert s["total_entries"] == 3
        assert s["by_level"]["INFO"] == 2
        assert s["by_level"]["ERROR"] == 1
        assert s["by_component"]["scheduler"] == 2
        assert s["by_component"]["engine"] == 1

    def test_search_case_insensitive(self, log_dir):
        """搜索不区分大小写。"""
        _write_log(log_dir, "app.log", [
            {"timestamp": "t1", "message": "Hello World"},
        ])
        searcher = LogSearcher(log_dir=log_dir)
        results = searcher.search("hello")
        assert len(results) == 1
