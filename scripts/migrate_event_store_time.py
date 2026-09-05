#!/usr/bin/env python3
"""S2.5: event_store.created_at 时间格式一次性迁移。

背景（白皮书 P2 / EM54-02）：S2.5 之前 event_store._persist 以
本地时区无亚秒 ISO 写库，而表默认 datetime('now') 生成 UTC 空格式
——同列两种格式并存，load_from_db 解析与时间线重建受影响。

迁移规则（一次性假设，见评审版 S2.5 步骤 2）：
  1. "YYYY-MM-DDTHH:MM:SS.ffffffZ"      → 已是目标格式，跳过
  2. "YYYY-MM-DDTHH:MM:SS"（本地 ISO）  → 视为本地时间，
       减 --assume-offset 小时（默认 8=Asia/Shanghai）转 UTC
  3. "YYYY-MM-DD HH:MM:SS"（datetime('now')，UTC）→ 直接补 T/亚秒/Z
统一目标格式："YYYY-MM-DDTHH:MM:SS.%fZ"（UTC）。

用法:
  python3 scripts/migrate_event_store_time.py [--db PATH] [--apply]
默认 dry-run：只统计将迁移的行数与样例，不写库。
"""

from __future__ import annotations

import argparse
import calendar
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

TARGET_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def classify(value: str) -> tuple[str, datetime | None]:
    """返回 (类别, 解析后的 UTC datetime)；无法解析 → ("unknown", None)。"""
    for fmt, kind in (
        ("%Y-%m-%dT%H:%M:%S.%fZ", "target"),
        ("%Y-%m-%dT%H:%M:%S.%f", "target"),
        ("%Y-%m-%dT%H:%M:%SZ", "target"),
    ):
        try:
            return kind, datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        # 本地 ISO（无 Z）——按一次性假设视为本地时间
        return "local_iso", datetime.strptime(
            value, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        return "utc_space", datetime.strptime(
            value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return "unknown", None


def migrate(db_path: Path, assume_offset_hours: int, apply: bool) -> int:
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 2
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT rowid, created_at FROM event_store").fetchall()
    stats = {"target": 0, "local_iso": 0, "utc_space": 0, "unknown": 0}
    updates: list[tuple[str, int]] = []
    offset = timedelta(hours=assume_offset_hours)
    for rowid, created_at in rows:
        if not created_at:
            stats["unknown"] += 1
            continue
        kind, dt = classify(created_at)
        if dt is None:
            stats["unknown"] += 1
            continue
        if kind == "target":
            stats["target"] += 1
            continue
        if kind == "local_iso":
            dt = dt - offset  # 本地(东八区) → UTC
        stats[kind] += 1
        updates.append((dt.strftime(TARGET_FMT), rowid))

    print(f"DB: {db_path}")
    print(f"rows total={len(rows)} already-target={stats['target']} "
          f"local_iso(→UTC-{assume_offset_hours}h)={stats['local_iso']} "
          f"utc_space={stats['utc_space']} unknown={stats['unknown']}")
    for fmt_val, rowid in updates[:5]:
        print(f"  sample rowid={rowid} → {fmt_val}")

    if not updates:
        print("nothing to migrate.")
        return 0
    if not apply:
        print(f"dry-run: {len(updates)} rows would be updated. "
              f"重跑加 --apply 执行写库。")
        return 0
    conn.executemany(
        "UPDATE event_store SET created_at = ? WHERE rowid = ?", updates)
    conn.commit()
    conn.close()
    print(f"applied: {len(updates)} rows updated.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(
        Path.home() / ".ocos" / "ocos.db"))
    ap.add_argument("--assume-offset", type=int, default=8,
                    help="本地 ISO 行的时区偏移（小时），默认 8（东八区）")
    ap.add_argument("--apply", action="store_true",
                    help="实际写库（默认 dry-run）")
    args = ap.parse_args()
    return migrate(Path(args.db), args.assume_offset, args.apply)


if __name__ == "__main__":
    sys.exit(main())
