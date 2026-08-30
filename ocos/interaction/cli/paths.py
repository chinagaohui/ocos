"""CLI 公共路径解析 — 单一来源（AUD-F8, 2026-08-30）。

run/goal/plan/approvals 等命令共用同一 db 路径解析顺序:
    显式参数 > OCOS_DB_PATH > ~/.ocos/ocos.db
避免多处硬编码漂移。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB = str(Path.home() / ".ocos" / "ocos.db")


def resolve_db_path(explicit: str | None = None) -> str:
    """解析 SQLite db 路径（与 daemon/CLI 默认一致）。"""
    return explicit or os.environ.get("OCOS_DB_PATH", DEFAULT_DB)
