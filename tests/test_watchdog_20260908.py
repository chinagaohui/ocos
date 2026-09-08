"""L2 自愈环看门狗测试 — 心跳过期自动重启 daemon（2026-09-08）。

覆盖: 健康零动作 / 无心跳诚实跳过（不误杀）/ 过期重启+记账 /
每日备份节流与轮转 / JSONL 日志格式约定。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ocos.daemon import watchdog as wd


@pytest.fixture
def hb_path(tmp_path, monkeypatch):
    p = tmp_path / "daemon_heartbeat.json"
    monkeypatch.setattr(wd, "HEARTBEAT_PATH", p)
    return p


@pytest.fixture
def ops_log(tmp_path, monkeypatch):
    p = tmp_path / "restart.log"
    monkeypatch.setattr(wd, "OPS_LOG", p)
    return p


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    p = tmp_path / "backups"
    monkeypatch.setattr(wd, "BACKUP_DIR", p)
    monkeypatch.setattr(wd, "_LAST_BACKUP_DAY_FILE", p / ".last_backup_day")
    return p


def _write_hb(hb_path: Path, age_s: float) -> None:
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    hb_path.write_text(json.dumps({"ts": ts.isoformat(), "pid": 1}),
                       encoding="utf-8")


def test_healthy_no_action(hb_path, ops_log, backup_dir):
    _write_hb(hb_path, age_s=5.0)
    r = wd.run_watchdog()
    assert r["action"] == "healthy"
    assert r["age_s"] <= 10.0
    assert not ops_log.exists()          # 无动作不记账


def test_no_heartbeat_skipped_never_kills(hb_path, ops_log, backup_dir):
    # 心跳文件不存在 = daemon 被人为 stop / 从未启动 — 不误杀
    r = wd.run_watchdog()
    assert r["action"] == "skipped"
    assert r["age_s"] is None
    assert not ops_log.exists()


def test_stale_heartbeat_triggers_restart(hb_path, ops_log, backup_dir,
                                          monkeypatch):
    _write_hb(hb_path, age_s=120.0)
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(wd.subprocess, "run", fake_run)
    r = wd.run_watchdog()
    assert r["action"] == "restarted"
    assert calls == [["systemctl", "--user", "restart", "ocos-daemon.service"]]
    # JSONL 记账（与 cli restart.py 同格式约定）
    entry = json.loads(ops_log.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["user"] == "watchdog"
    assert entry["components"]["daemon"]["ok"] is True
    assert "stale" in entry["note"]


def test_restart_failure_honest_report(hb_path, ops_log, backup_dir,
                                       monkeypatch):
    _write_hb(hb_path, age_s=120.0)
    monkeypatch.setattr(wd.subprocess, "run",
                        lambda cmd, **kw: type("P", (), {
                            "returncode": 1, "stdout": "", "stderr": "boom"})())
    r = wd.run_watchdog()
    assert r["action"] == "restart_failed"
    entry = json.loads(ops_log.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["components"]["daemon"]["ok"] is False


def test_corrupt_heartbeat_file_skipped(hb_path, ops_log, backup_dir):
    # 损坏心跳 = 读不到时间戳 — 诚实跳过而非误判重启
    hb_path.write_text("not json", encoding="utf-8")
    r = wd.run_watchdog()
    assert r["action"] == "skipped"


def test_daily_backup_once_and_rotation(tmp_path, monkeypatch, backup_dir):
    db = tmp_path / "ocos.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(wd, "_LAST_BACKUP_DAY_FILE",
                        backup_dir / ".last_backup_day")

    first = wd.run_daily_backup(db)
    assert first and Path(first).exists()
    assert (backup_dir / ".last_backup_day").read_text().strip()  # 当日标记
    second = wd.run_daily_backup(db)      # 同日第二次 → 节流跳过
    assert second is None

    # 轮转: 预置 8 个旧备份 → 只保留最近 7 份
    for i in range(8):
        (backup_dir / f"ocos-2025090{i}.db").write_text("x")
    monkeypatch.setattr(wd, "_LAST_BACKUP_DAY_FILE",
                        backup_dir / ".none")   # 强制绕过节流
    wd.run_daily_backup(db)
    remaining = sorted(backup_dir.glob("ocos-*.db"))
    assert len(remaining) == wd.BACKUP_KEEP


def test_backup_skipped_when_db_missing(backup_dir):
    assert wd.run_daily_backup(Path("/nonexistent/ocos.db")) is None
