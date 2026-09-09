"""ocos/governance/risk_registry.py — Step 4 治理层: 风险注册表 + 熔断机制.

熔断机制: L3 自治下连续 N 次 GrowthOptimizer apply 失败 → 自动降级到 L2.
已知风险清单结构化存储，触发阈值可配置。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)


# ── 已知风险清单（结构化） ───────────────────────────────────────────

KNOWN_RISKS: dict[str, dict] = {
    "growth_optimizer_failure_storm": {
        "risk_id": "growth_optimizer_failure_storm",
        "description": "GrowthOptimizer 连续 apply 失败（可能沙箱隔离逻辑有 bug 或 pytest 基线崩了）",
        "trigger": "连续 N 次 apply_in_sandbox 返回 rejected",
        "threshold": 3,              # 连续失败 ≥3 次触发熔断
        "mitigation": "自动降级 autonomy_level 到 L2 + 审计日志",
        "max_downgrade": 2,          # 最多降 2 档 (L3→L2)
    },
    "self_modification_on_red_line": {
        "risk_id": "self_modification_on_red_line",
        "description": "GrowthOptimizer 尝试修改红线文件（宪法/权限/决策类型）",
        "trigger": "EvolutionGuard.check() 命中红线",
        "threshold": 1,              # 任何一次立即拒绝
        "mitigation": "rejected + 审计日志 + 通知人类",
        "max_downgrade": 0,          # 不降级，只拒绝
    },
    "knowledge_gap_unfilled": {
        "risk_id": "knowledge_gap_unfilled",
        "description": "EpistemicDrive 高不确定性 domain 连续 3 次没被 WebResearcher 覆盖",
        "trigger": "knowledge 表对应 domain 行数 < 预测 gap 数",
        "threshold": 3,
        "mitigation": "触发 WebResearcher 强制调研",
        "max_downgrade": 0,
    },
    "daemon_tick_stall": {
        "risk_id": "daemon_tick_stall",
        "description": "daemon heartbeat 停滞超过 30 秒（主线程可能卡死）",
        "trigger": "heartbeat cycle 连续 N 次不增长",
        "threshold": 6,
        "mitigation": "记录 + 标记，systemd watchdog 接管",
        "max_downgrade": 0,
    },
}


# ── CircuitBreaker 熔断器 ───────────────────────────────────────────

class CircuitBreaker:
    """自动降级熔断器 — L3 下连续 apply 失败 → 降级到 L2."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path
        self._failure_counts: dict[str, int] = {}
        self._tripped_at: dict[str, str] = {}
        self._trip_threshold = KNOWN_RISKS["growth_optimizer_failure_storm"]["threshold"]

    def record_failure(self, risk_id: str = "growth_optimizer_failure_storm",
                       reason: str = "") -> None:
        self._failure_counts[risk_id] = self._failure_counts.get(risk_id, 0) + 1
        if self._failure_counts[risk_id] >= self._trip_threshold:
            self._trip(risk_id, reason)

    def record_success(self, risk_id: str = "growth_optimizer_failure_storm") -> None:
        self._failure_counts.pop(risk_id, None)

    def _trip(self, risk_id: str, reason: str) -> None:
        """触发熔断 → 自动降级 autonomy_level."""
        risk = KNOWN_RISKS.get(risk_id, {})
        max_down = risk.get("max_downgrade", 1)
        try:
            from ocos.execution.autonomy import (
                get_autonomy_level, set_autonomy_level,
                audit_level_change, append_audit_record,
            )
            current = get_autonomy_level()
            new_level = max(0, current - max_down)
            if new_level < current:
                old_desc = current
                set_autonomy_level(new_level)
                audit_level_change(
                    self._db_path, old_desc, new_level,
                    source=f"circuit_breaker:{risk_id}",
                )
                append_audit_record({
                    "kind": "circuit_trip",
                    "risk_id": risk_id,
                    "reason": reason,
                    "downgrade": f"L{old_desc}→L{new_level}",
                })
                logger.critical(
                    "CIRCUIT TRIP: %s → autonomy L%d (downgraded from L%d)",
                    risk_id, new_level, old_desc,
                )
            self._failure_counts[risk_id] = 0
            self._tripped_at[risk_id] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            logger.error("circuit breaker trip failed: %s", e)

    def status(self) -> dict:
        return {
            "failure_counts": dict(self._failure_counts),
            "tripped_at": dict(self._tripped_at),
            "trip_threshold": self._trip_threshold,
        }


# ── 风险查询 ─────────────────────────────────────────────────────────

def get_risk(risk_id: str) -> Optional[dict]:
    return KNOWN_RISKS.get(risk_id)


def list_risks() -> list[dict]:
    return list(KNOWN_RISKS.values())


# ── GrowthOptimizer 失败 Hook (供调用方接) ───────────────────────────

def on_growth_failure(db_path: Optional[str] = None, reason: str = "") -> None:
    """GrowthOptimizer apply 失败时调用 — 触发熔断器."""
    cb = CircuitBreaker(db_path=db_path)
    cb.record_failure(reason=reason)


def on_growth_success(db_path: Optional[str] = None) -> None:
    """GrowthOptimizer apply 成功时调用 — 重置熔断器计数."""
    cb = CircuitBreaker(db_path=db_path)
    cb.record_success()
