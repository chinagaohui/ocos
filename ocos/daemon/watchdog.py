"""daemon 心跳看门狗 — L2 自愈环（进程活着但认知循环停摆的修复通道）。

自愈三层模型（2026-09-08「核心活着就能修好自身」加固）:
    L1  进程崩溃        → systemd Restart=on-failure（既有）
    L2  线程僵死/假死    → 本看门狗: 心跳过期 → systemctl 重启 daemon（新增）
    L3  认知/数据损伤    → HealthLoop 四层自检 + repair_link 白名单修复（既有）

L2 缺口动机: tick 线程若卡死（死锁/IO 挂起），进程仍存活但心跳停更，
systemd Type=simple 不触发重启 — 全部自主循环（自检/修复/动机/目标）
同时停摆。看门狗读 ~/.ocos/daemon_heartbeat.json:
    - 文件不存在  → daemon 从未启动或被人为 stop → 诚实跳过（不误杀）
    - age ≤ 阈值  → 健康，零动作
    - age > 阈值  → systemctl --user restart ocos-daemon → JSONL 记账
阈值默认 90s（心跳每 5 tick × tick 间隔 5s = 最坏 25s 一写，留 3.6x 容错，
UI 侧 alive 判定为 30s — 看门狗必须宽于 UI 阈值避免抖动误杀）。

顺带职责（每日首次运行时）: SQLite 在线备份 → ~/.ocos/backups/（保留 7 份）
— 覆盖 DB 文件级损坏（REINDEX 白名单修不了的 disk I/O error / corruption），
修复链 L3 之外的兜底。

由 systemd timer 周期调用（ocos-watchdog.timer），无守护进程、单次退出。
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HEARTBEAT_PATH = Path.home() / ".ocos" / "daemon_heartbeat.json"
OPS_LOG = Path.home() / ".ocos" / "ops" / "restart.log"
BACKUP_DIR = Path.home() / ".ocos" / "backups"
DAEMON_UNIT = "ocos-daemon.service"
BACKUP_KEEP = 7
# 每日备份节流标记（date 字符串变更即触发当日首次备份）
_LAST_BACKUP_DAY_FILE = BACKUP_DIR / ".last_backup_day"

DEFAULT_STALE_S = 90.0


def _heartbeat_age_s() -> float | None:
    """心跳年龄（秒）；文件不存在返回 None（诚实区分"未运行"与"过期"）。"""
    try:
        hb = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
        return time.time() - datetime.fromisoformat(hb["ts"]).timestamp()
    except (OSError, ValueError, KeyError):
        return None


def _log_restart(result: dict) -> None:
    """追加 JSONL 操作日志（与 cli restart.py 同格式约定）。"""
    try:
        OPS_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {"ts": datetime.now(timezone.utc).astimezone().isoformat(),
                 "user": "watchdog", "env": "prod", **result}
        with OPS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def restart_daemon(reason: str) -> dict:
    """重启 daemon 并记账。返回结果 dict（供测试断言）。"""
    ok = False
    detail = ""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "restart", DAEMON_UNIT],
            capture_output=True, text=True, timeout=30)
        ok = proc.returncode == 0
        detail = (proc.stderr or proc.stdout or "").strip()[:200]
    except (OSError, subprocess.TimeoutExpired) as e:
        detail = str(e)[:200]
    result = {"components": {DAEMON_UNIT.removesuffix(".service")
                             .removeprefix("ocos-"): {
                  "ok": ok, "unit": DAEMON_UNIT, "detail": detail}},
              "ok": ok, "note": f"watchdog: {reason}"}
    _log_restart(result)
    return result


def run_daily_backup(db_path: Path | None = None) -> str | None:
    """每日首次运行: SQLite 在线备份（backup API，不锁库）。返回备份路径。"""
    db_path = db_path or Path.home() / ".ocos" / "ocos.db"
    if not db_path.exists():
        return None
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if _LAST_BACKUP_DAY_FILE.exists() and \
                _LAST_BACKUP_DAY_FILE.read_text(encoding="utf-8").strip() == today:
            return None   # 今日已备份
        dest = BACKUP_DIR / f"ocos-{today}.db"
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            dst = sqlite3.connect(dest)
            try:
                src.backup(dst)   # 在线备份 — 不阻塞生产库写入
            finally:
                dst.close()
        finally:
            src.close()
        _LAST_BACKUP_DAY_FILE.write_text(today, encoding="utf-8")
        # 保留最近 N 份
        backups = sorted(BACKUP_DIR.glob("ocos-*.db"))
        for old in backups[:-BACKUP_KEEP]:
            old.unlink(missing_ok=True)
        return str(dest)
    except (OSError, sqlite3.Error):
        return None


def run_watchdog(stale_s: float = DEFAULT_STALE_S) -> dict:
    """看门狗单次检查（systemd timer 周期调用）。

    返回 {"action": "healthy"|"skipped"|"restarted"|"restart_failed",
          "age_s": float|None, ...}
    """
    age = _heartbeat_age_s()
    if age is None:
        # 心跳文件不存在 = daemon 从未运行/被人为 stop — 不误杀
        return {"action": "skipped", "age_s": None,
                "reason": "no heartbeat file (daemon not running by intent)"}
    if age <= stale_s:
        run_daily_backup()   # 健康时顺带每日备份节流检查
        return {"action": "healthy", "age_s": round(age, 1)}
    reason = f"heartbeat stale {age:.0f}s > {stale_s:.0f}s — tick loop presumed dead"
    result = restart_daemon(reason)
    # 重启后立即做一次备份（趁 DB 处于重启静止窗口）
    backup = run_daily_backup()
    return {"action": ("restarted" if result.get("ok") else "restart_failed"),
            "age_s": round(age, 1),
            "backup": backup,
            **result}


def main() -> int:
    r = run_watchdog()
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["action"] in ("healthy", "skipped", "restarted") else 1


if __name__ == "__main__":
    sys.exit(main())
