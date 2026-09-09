"""Phase 1 — Daily Self-Care 薄编排器。

每日定时自我关心循环的编排层。Phase 1 只跑 Phase 0（环境快照 + DB 备份）
和 Phase 1（S1-S5 代码扫描），输出 JSON 到 stdout。

Phase 2+（分类/执行/报告落盘）后续补充。不重建已有模块，只复用:
  watchdog.run_daily_backup() — DB 在线备份
  CodeHealthScanner           — 代码级扫描（本项目唯一新扫描逻辑）

关键约束:
  - 只读，Phase 1 不创建/不修改 .py、不写 episodes/goals 表、不落报告文件
  - 每个阶段独立 try/except 隔离，任一失败不影响其余
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 整次 Phase 0-1 扫描总超时（秒）—— 超过截断
PHASE01_TOTAL_TIMEOUT = 120


class DailySelfCare:
    """每日自我关心编排器 — Phase 0-1 骨架。"""

    def __init__(
        self,
        project_root: str | None = None,
        db_path: str | None = None,
        skip_backup: bool = False,
    ) -> None:
        from ocos.monitoring.code_scanner import CodeHealthScanner
        self._scanner = CodeHealthScanner(
            project_root=project_root, db_path=db_path,
        )
        self._db_path = db_path
        self._skip_backup = skip_backup
        self._started = 0.0

    # ── 主入口 ─────────────────────────────────────────────────────────────

    def run(self, output: str | None = None) -> dict[str, Any]:
        """跑 Phase 0 + Phase 1，返回完整报告字典。

        Args:
            output: 输出文件路径（Phase 1 只写 stdout，不写文件）
        """
        self._started = time.monotonic()
        report: dict[str, Any] = {
            "cycle": "daily_self_care",
            "phase": "1",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "phases": {},
            "errors": [],
            "total_elapsed_seconds": 0.0,
        }

        # ── Phase 0: 环境快照 + DB 备份 ──────────────────────────────
        try:
            report["phases"]["phase_0"] = self._run_phase_0()
        except Exception as e:
            err_msg = f"Phase 0 failed: {type(e).__name__}: {e}"
            report["errors"].append(err_msg)
            report["phases"]["phase_0"] = {"error": err_msg}
            logger.warning(err_msg)

        # ── Phase 1: S1-S5 代码扫描 ────────────────────────────────
        try:
            report["phases"]["phase_1"] = self._scanner.scan_all()
        except Exception as e:
            err_msg = f"Phase 1 failed: {type(e).__name__}: {e}"
            report["errors"].append(err_msg)
            report["phases"]["phase_1"] = {"error": err_msg}
            logger.warning(err_msg)

        report["total_elapsed_seconds"] = round(time.monotonic() - self._started, 3)
        return report

    # ── Phase 0 ────────────────────────────────────────────────────────────

    def _run_phase_0(self) -> dict[str, Any]:
        """环境快照: watchdog.run_daily_backup() + 简单系统信息。"""
        phase: dict[str, Any] = {}

        # DB 在线备份（复用 watchdog）
        if not self._skip_backup:
            try:
                from ocos.daemon.watchdog import run_daily_backup
                backup_path = run_daily_backup(
                    Path(self._db_path) if self._db_path else None,
                )
                phase["db_backup"] = {
                    "executed": True,
                    "backup_path": backup_path,
                }
            except Exception as e:
                phase["db_backup"] = {
                    "executed": False,
                    "error": f"{type(e).__name__}: {e}",
                }
        else:
            phase["db_backup"] = {"executed": False, "reason": "skip_backup=True"}

        return phase


# ── CLI 入口辅助 ──────────────────────────────────────────────────────────


def run_daily_self_care(
    project_root: str | None = None,
    db_path: str | None = None,
    skip_backup: bool = False,
    indent: int = 2,
) -> dict[str, Any]:
    """便捷入口：跑扫描 → 打印 JSON → 返回报告。"""
    runner = DailySelfCare(
        project_root=project_root, db_path=db_path, skip_backup=skip_backup,
    )
    report = runner.run()
    print(json.dumps(report, indent=indent, ensure_ascii=False, default=str))
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    result = run_daily_self_care()
    sys.exit(0 if not result.get("errors") else 1)
