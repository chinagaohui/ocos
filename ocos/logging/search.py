"""LogSearcher — 从日志文件中搜索结构化 JSON 日志行。

支持按 level、component、时间范围过滤。
"""

from __future__ import annotations

import json
import glob
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class LogSearcher:
    """日志搜索器。"""

    def __init__(self, log_dir: str = "ocos/logs"):
        self.log_dir = log_dir

    def search(
        self,
        query: str,
        *,
        level: Optional[str] = None,
        component: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """搜索日志文件中的 JSON 行。

        Args:
            query: 消息内容关键词。
            level: 过滤级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)。
            component: 过滤组件名。
            after: 起始时间 (ISO 格式)。
            before: 结束时间 (ISO 格式)。
            limit: 最大返回条数。

        Returns:
            匹配的日志条目列表。
        """
        results: list[dict[str, Any]] = []
        log_files = self._get_log_files()

        for filepath in log_files:
            if len(results) >= limit:
                break
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if len(results) >= limit:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # 过滤
                        if not self._matches(entry, query, level, component, after, before):
                            continue
                        results.append(entry)
            except OSError:
                continue

        return results

    def tail(
        self,
        n: int = 20,
        *,
        component: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """获取最新的 n 条日志（按时间降序）。"""
        log_files = self._get_log_files()
        all_entries: list[dict[str, Any]] = []

        # 从最新的文件开始读
        for filepath in reversed(log_files):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if component and entry.get("component") != component:
                            continue
                        all_entries.append(entry)
            except OSError:
                continue
        return all_entries[-n:]

    def stats(
        self,
        since: Optional[str] = None,
    ) -> dict[str, Any]:
        """返回各组件/级别的日志统计。"""
        log_files = self._get_log_files()
        stats: dict[str, Any] = {
            "total_entries": 0,
            "by_level": {},
            "by_component": {},
        }

        for filepath in log_files:
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if since and entry.get("timestamp", "") < since:
                            continue

                        stats["total_entries"] += 1

                        level = entry.get("level", "UNKNOWN")
                        stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

                        component = entry.get("component", "root")
                        stats["by_component"][component] = (
                            stats["by_component"].get(component, 0) + 1
                        )
            except OSError:
                continue

        return stats

    # ── 内部方法 ────────────────────────────────────────────────────────────

    def _get_log_files(self) -> list[str]:
        """获取按修改时间排序的日志文件列表（升序），排除 .gz 文件。"""
        pattern = os.path.join(self.log_dir, "*.log*")
        files = []
        for p in glob.glob(pattern):
            if os.path.isfile(p) and not p.endswith(".gz"):
                files.append(p)
        return sorted(files, key=os.path.getmtime)

    def _matches(
        self,
        entry: dict[str, Any],
        query: str,
        level: Optional[str],
        component: Optional[str],
        after: Optional[str],
        before: Optional[str],
    ) -> bool:
        if level and entry.get("level", "").upper() != level.upper():
            return False
        if component and entry.get("component") != component:
            return False
        if after and entry.get("timestamp", "") < after:
            return False
        if before and entry.get("timestamp", "") > before:
            return False
        if query and query.lower() not in entry.get("message", "").lower():
            return False
        return True
