"""CLI 子命令 — ocos daily-self-care scan。

Phase 1 只读扫描，零副作用。用法:
  ocos daily-self-care scan
  ocos daily-self-care scan --no-backup
  ocos daily-self-care scan --db /path/to/ocos.db
"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession


def cmd_daily_self_care(args, session: InteractionSession) -> int:
    """ocos daily-self-care — 每日自我关心 CLI 入口。"""
    action = getattr(args, "dsc_action", None)

    if action == "scan":
        return _cmd_scan(args, session)
    else:
        print("Usage: ocos daily-self-care scan [--no-backup] [--db PATH]")
        return 1


def _cmd_scan(args, session: InteractionSession) -> int:
    """Phase 1: 只读扫描 → JSON 报告。"""
    from ocos.daemon.daily_self_care import DailySelfCare

    skip_backup = bool(getattr(args, "no_backup", False))
    db_path = getattr(args, "db", "") or None

    runner = DailySelfCare(db_path=db_path, skip_backup=skip_backup)
    report = runner.run()

    import json
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))

    # 返回码: 无错误 → 0；有子扫描失败 → 1（但不是 crash 级）
    errors = report.get("errors", [])
    phase_errors = sum(
        1 for p in report.get("phases", {}).values()
        if isinstance(p, dict) and "error" in p
    )
    return 0 if not errors and phase_errors == 0 else 1
