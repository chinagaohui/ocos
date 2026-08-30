"""OCOS CLI — status 命令（UX-2: 一屏总览认知状态）。"""

from __future__ import annotations

import json
import os
import sqlite3

from ocos.interaction.base import InteractionSession
from ocos.interaction.cli.paths import resolve_db_path


def cmd_status(args, session: InteractionSession) -> int:
    """ocos status — 目标/待批/记忆/计划 一屏总览。"""
    db_path = resolve_db_path(getattr(args, "db", None) or None)
    exists = os.path.exists(db_path)
    print("OCOS Status")
    print("=" * 52)
    print(f"  db       : {db_path}{'  (存在)' if exists else '  (不存在 — 先 ocos run 或 goal create)'}")
    if not exists:
        return 0

    conn = sqlite3.connect(db_path)

    # 目标（goals 表 — 用户/系统持久化目标）
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM goals GROUP BY status"
        ).fetchall()
        counts = {r[0]: r[1] for r in rows}
        total = sum(counts.values())
        pending = counts.get("PENDING", 0)
        active = counts.get("ACTIVE", 0)
        print(f"  goals    : {total} 个（PENDING {pending} / ACTIVE {active} / 其他 {total - pending - active}）")
        if pending:
            row = conn.execute(
                "SELECT id, description FROM goals WHERE status='PENDING' "
                "ORDER BY created_at LIMIT 1"
            ).fetchone()
            print(f"             下一个待认领: {row[0]}  {str(row[1])[:44]}")
    except sqlite3.OperationalError:
        print("  goals    : (表未创建)")

    # 认知目标（goal 表 — runtime 运行时目标）
    try:
        n = conn.execute("SELECT COUNT(*) FROM goal WHERE status IN ('ACTIVE','PENDING')").fetchone()[0]
        print(f"  runtime  : {n} 个认知目标在 runtime 队列")
    except sqlite3.OperationalError:
        pass

    # 待批动作（R4-B）
    try:
        n = conn.execute("SELECT COUNT(*) FROM pending_actions WHERE status='pending'").fetchone()[0]
        print(f"  approvals: {n} 项待批（ocos approvals list）")
        if n:
            row = conn.execute(
                "SELECT id, action_type, text FROM pending_actions "
                "WHERE status='pending' ORDER BY queued_at LIMIT 1"
            ).fetchone()
            print(f"             {row[0]}  {row[1]}  {str(row[2])[:40]}")
    except sqlite3.OperationalError:
        print("  approvals: (表未创建)")

    # 记忆
    for table, label in (("episodes", "episodes"), ("belief", "beliefs"),
                         ("pattern", "patterns"), ("knowledge", "knowledge")):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  memory   : {label:<10} {n}" if label == "episodes"
                  else f"             {label:<10} {n}")
        except sqlite3.OperationalError:
            break

    # 计划
    try:
        n = conn.execute("SELECT COUNT(*) FROM plan_dag").fetchone()[0]
        print(f"  plans    : {n} 个已分解")
    except sqlite3.OperationalError:
        pass

    conn.close()
    print("=" * 52)
    session.record_query()
    return 0
