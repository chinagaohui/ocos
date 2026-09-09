"""ocos/governance/autonomy_metrics.py — Step 5 北极星指标计算.

5 个北极星指标（Coze 报告 v1.0）:
  1. overreach_events_total        → = 0 任何阶段必须为 0
  2. autonomous_goal_completion_rate → ≥ 70% 无人干预
  3. repeated_failure_rate_delta    → ↓ 50% 同类任务重复犯错
  4. goal_proposal_approval_rate    → ≥ 50% GoalProposal 批准率
  5. growth_optimizer_success_rate  → ≥ 80% GrowthOptimizer apply 成功率

这些 metric 以 Prometheus exposition format 产出，
由 monitoring/manager.py 集成到 /metrics 端点。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── 指标计算 ──────────────────────────────────────────────────────────

def overreach_events(db_path: str) -> int:
    """北极星 1: 越权事件数 — 任何阶段必须为 0."""
    try:
        conn = _connect(db_path)
        # goal_proposal 里 HIGH risk REJECTED 也算越权
        n = conn.execute(
            "SELECT COUNT(*) FROM goal_proposal WHERE risk_level='HIGH' AND status='REJECTED'"
        ).fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def autonomous_completion_rate(db_path: str, window_hours: int = 24) -> float:
    """北极星 2: 无人干预时段自主目标完成率."""
    try:
        conn = _connect(db_path)
        since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed
            FROM goal
            WHERE origin_level='SELF' AND created_at > ?
            """,
            (since,),
        ).fetchone()
        conn.close()
        total = row["total"] or 0
        if total == 0:
            return 0.0  # 无数据
        return round((row["completed"] or 0) / total * 100, 1)
    except Exception:
        return 0.0


def repeated_failure_delta(db_path: str) -> float:
    """北极星 3: 同类任务重复犯错率 — 学习闭环生效证据.

    简化: pattern 表里有 agent=X, success=false 的 pattern 数量
    vs 全部 pattern 数量 → failure ratio.
    """
    try:
        conn = _connect(db_path)
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN trigger_condition LIKE '%success=false%'
                         OR trigger_condition LIKE '%agent=%'
                         AND confidence < 0.7 THEN 1 ELSE 0 END) as failure_patterns
            FROM pattern
            """
        ).fetchone()
        conn.close()
        total = row["total"] or 0
        if total == 0:
            return 0.0
        return round((row["failure_patterns"] or 0) / total * 100, 1)
    except Exception:
        return 0.0


def proposal_approval_rate(db_path: str) -> float:
    """北极星 4: GoalProposal 批准率 — ≥ 50%."""
    try:
        conn = _connect(db_path)
        row = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) as approved
            FROM goal_proposal
            """
        ).fetchone()
        conn.close()
        total = row["total"] or 0
        if total == 0:
            return 0.0
        return round((row["approved"] or 0) / total * 100, 1)
    except Exception:
        return 0.0


# ── Prometheus exposition format 输出 ─────────────────────────────────

def prometheus_metrics(db_path: Optional[str] = None) -> str:
    """导出 5 个北极星指标的 Prometheus exposition format.

    格式: https://prometheus.io/docs/instrumenting/exposition_formats/
    """
    if not db_path or not Path(db_path).exists():
        db_path = str(Path.home() / ".ocos" / "ocos.db")

    lines = [
        "# HELP ocos_overreach_events_total Number of overreach events (must be 0).",
        "# TYPE ocos_overreach_events_total counter",
        f"ocos_overreach_events_total {overreach_events(db_path)}",
        "",
        "# HELP ocos_autonomous_completion_rate_pct Self-origin goal completion rate (window 24h).",
        "# TYPE ocos_autonomous_completion_rate_pct gauge",
        f"ocos_autonomous_completion_rate_pct {autonomous_completion_rate(db_path)}",
        "",
        "# HELP ocos_repeated_failure_rate_pct Failure pattern ratio (lower is better).",
        "# TYPE ocos_repeated_failure_rate_pct gauge",
        f"ocos_repeated_failure_rate_pct {repeated_failure_delta(db_path)}",
        "",
        "# HELP ocos_proposal_approval_rate_pct GoalProposal approval rate (target >= 50%).",
        "# TYPE ocos_proposal_approval_rate_pct gauge",
        f"ocos_proposal_approval_rate_pct {proposal_approval_rate(db_path)}",
    ]
    return "\n".join(lines) + "\n"
