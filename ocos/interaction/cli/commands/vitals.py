"""OCOS CLI — vitals 命令实现（L0-6: 生命体征仪表盘骨架）。"""

from __future__ import annotations

import os
from pathlib import Path


def cmd_vitals(args, session) -> int:
    """ocos vitals — 一屏总览生命体征；--check 按阶段阈值判定（§3.4 Gate）。"""
    from ocos.monitoring.vitals import check_thresholds, compute_vitals, render_vitals
    db = getattr(args, "db", "") or os.environ.get(
        "OCOS_DB_PATH", str(Path.home() / ".ocos" / "ocos.db"))
    days = int(getattr(args, "window", 7) or 7)
    vitals = compute_vitals(db, window_days=days)
    print(render_vitals(vitals))
    # 红线硬性达标则 exit 0；出现确证绕过 exit 2（脚本可判）
    if vitals.get("redline_violation_count", 0):
        return 2
    # §3.4: --check 阶段阈值判定 — 违规 exit 2，未点亮项提示但不阻断
    if getattr(args, "check", False):
        phase = getattr(args, "phase", "L4") or "L4"
        violations = check_thresholds(vitals, phase)
        if violations:
            print(f"\n[Gate {phase}] 未达标项:")
            for v_ in violations:
                print(f"  ✗ {v_}")
            hard = [x for x in violations if not x.startswith("[未点亮]")]
            return 2 if hard else 0
        print(f"\n[Gate {phase}] ✓ 阈值全部达标")
    return 0
