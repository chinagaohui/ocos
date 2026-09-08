"""感知层上电（2026-09-07）: StimulusScanner — 真实环境刺激 → 感知事件。

"上电而非重写"：EventBus（perception_bus）与 EnvironmentSensor
（内感轮询）早已在库，缺的是"扫描 → 事件 → 动机"这根驱动神经。

四类真实刺激（全部实测真值，无 LLM）:
    disk_high        根分区使用率越阈（≥85% 高 / ≥92% 危急）
    memory_high      daemon 进程 RSS 越阈（默认 500MB — 内感自观察）
    failure_cluster  24h 内 goal_result 失败 ≥3 次（学习闭环信号）
    goal_stuck       自主目标 IN_PROGRESS 超 6h 无更新（执行卡死信号）

冷却: 同 key 默认 6h 不重发（进程内存态；重启后重发一次可接受——
事件本就是"状态仍异常"的再确认）。每次触发落
$OCOS_AUDIT_DIR/perception.jsonl（vitals V3 感知指标数据源）。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class StimulusScanner:
    """环境刺激扫描器 — OCOS 的刺激驱动行为之源（V3 感知-反应）。"""

    def __init__(
        self,
        db_path: str,
        audit_dir: str | None = None,
        disk_warn_pct: float = 85.0,
        disk_crit_pct: float = 92.0,
        memory_high_mb: float = 500.0,
        fail_window_hours: int = 24,
        fail_min_count: int = 3,
        stuck_hours: int = 6,
        cooldown_hours: float = 6.0,
    ) -> None:
        self._db_path = db_path
        self._disk_warn_pct = disk_warn_pct
        self._disk_crit_pct = disk_crit_pct
        self._memory_high_mb = memory_high_mb
        self._fail_window_hours = fail_window_hours
        self._fail_min_count = fail_min_count
        self._stuck_hours = stuck_hours
        self._cooldown_sec = cooldown_hours * 3600.0
        base = (audit_dir or os.environ.get("OCOS_AUDIT_DIR", "")).strip()
        self._audit_dir = (Path(base).expanduser() if base
                           else Path.home() / ".ocos" / "audit")
        self._last_fired: dict[str, float] = {}

    # ── 主入口 ────────────────────────────────────────────────────────

    def scan(self) -> list[dict]:
        """扫描全部刺激源，返回触发的事件列表（已冷却过滤）。

        事件: {key, severity, description, evidence}
        severity ∈ low/high/critical — 映射 EventBus EventSeverity。
        """
        fired: list[dict] = []
        for stim in (self._check_disk(), self._check_memory(),
                     self._check_failure_cluster(), self._check_goal_stuck()):
            if stim is None:
                continue
            if not self._cooldown_ok(stim["key"]):
                continue
            self._last_fired[stim["key"]] = time.time()
            self._log_stimulus(stim)
            fired.append(stim)
            logger.info("Perception stimulus fired: %s — %s",
                        stim["key"], stim["description"][:80])
        return fired

    # ── 刺激源 ────────────────────────────────────────────────────────

    def _check_disk(self) -> dict | None:
        """根分区使用率（shutil — 无 psutil 依赖）。"""
        try:
            usage = shutil.disk_usage("/")
            pct = usage.used / usage.total * 100.0
        except Exception:
            return None
        if pct >= self._disk_crit_pct:
            return self._stim("disk_critical", "critical",
                              f"根分区使用率 {pct:.0f}%，接近写满"
                              "（危急线 92%）——需清理或迁移",
                              {"used_pct": round(pct, 1)})
        if pct >= self._disk_warn_pct:
            return self._stim("disk_high", "high",
                              f"根分区使用率 {pct:.0f}% 越过告警线 85%"
                              "——建议排查大文件",
                              {"used_pct": round(pct, 1)})
        return None

    def _check_memory(self) -> dict | None:
        """daemon 进程 RSS（/proc 直读，psutil 缺失亦可用）。"""
        rss_mb = self._read_rss_mb()
        if rss_mb is None or rss_mb < self._memory_high_mb:
            return None
        return self._stim(
            "memory_high", "high",
            f"daemon 内存 RSS {rss_mb:.0f}MB 越过 {self._memory_high_mb:.0f}MB"
            "——存在泄漏风险，建议自检",
            {"rss_mb": round(rss_mb, 1)})

    @staticmethod
    def _read_rss_mb() -> float | None:
        try:
            with open("/proc/self/status", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        except Exception:
            pass
        try:
            import psutil  # type: ignore
            return psutil.Process().memory_info().rss / 1024 / 1024
        except Exception:
            return None

    def _check_failure_cluster(self) -> dict | None:
        """24h 内 goal_result 失败聚集 — 学习闭环的真实信号源。"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path)
            window = (datetime.now(timezone.utc)
                      - timedelta(hours=self._fail_window_hours)).isoformat()
            rows = conn.execute(
                "SELECT outcome FROM episodes WHERE source='goal_result' "
                "AND created_at >= ?", (window,)).fetchall()
            conn.close()
        except sqlite3.OperationalError:
            return None
        except Exception:
            logger.debug("failure cluster scan failed", exc_info=True)
            return None
        fails: list[str] = []
        for (outcome,) in rows:
            try:
                d = json.loads(outcome) if isinstance(outcome, str) else outcome
                if isinstance(d, dict) and d.get("success") is False:
                    fails.append(str(d.get("error") or d.get("summary") or "")[:60])
            except (ValueError, TypeError):
                continue
        if len(fails) < self._fail_min_count:
            return None
        return self._stim(
            "failure_cluster", "high",
            f"近 {self._fail_window_hours}h 内目标执行失败 {len(fails)} 次"
            "（≥3）——建议复盘失败模式并检查 lesson 先验是否生效",
            {"fail_count": len(fails), "samples": fails[:3]})

    def _check_goal_stuck(self) -> dict | None:
        """自主目标认领后长时间无进展 — 执行器卡死的直接观测。"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path)
            cutoff = (datetime.now(timezone.utc)
                      - timedelta(hours=self._stuck_hours)).isoformat()
            rows = conn.execute(
                "SELECT id, description, updated_at FROM goals WHERE "
                "status='IN_PROGRESS' AND source='autonomous' AND "
                "updated_at < ? LIMIT 3", (cutoff,)).fetchall()
            conn.close()
        except sqlite3.OperationalError:
            return None
        except Exception:
            logger.debug("goal stuck scan failed", exc_info=True)
            return None
        if not rows:
            return None
        return self._stim(
            "goal_stuck", "low",
            f"{len(rows)} 个自主目标超过 {self._stuck_hours}h 无进展"
            "——检查执行器是否卡死",
            {"goals": [{"id": r[0], "description": str(r[1])[:50],
                        "updated_at": str(r[2])} for r in rows]})

    # ── 基础设施 ──────────────────────────────────────────────────────

    @staticmethod
    def _stim(key: str, severity: str, description: str,
              evidence: dict) -> dict:
        return {"key": key, "severity": severity,
                "description": description, "evidence": evidence}

    def _cooldown_ok(self, key: str) -> bool:
        last = self._last_fired.get(key)
        return last is None or (time.time() - last) >= self._cooldown_sec

    def _log_stimulus(self, stim: dict) -> None:
        """感知审计留痕 — vitals V3 感知响应率的数据源。"""
        try:
            self._audit_dir.mkdir(parents=True, exist_ok=True)
            rec = {"ts": datetime.now(timezone.utc).isoformat(), **stim}
            with (self._audit_dir / "perception.jsonl").open(
                    "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("perception log failed", exc_info=True)


__all__ = ["StimulusScanner"]
