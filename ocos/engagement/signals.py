"""L2-2: 参与度信号采集 — 对话频率/目标完成度 → 参与度快照。

升级方案 v1.0 §L2: engagement（参与度）上电 — 接对话频率/目标完成度
信号，驱动主动交互调度器（P5.2 扩展）。

数据源 = 既有生产表（user_messages / goals），纯 SQL 聚合、确定性、
无 LLM。缺表/缺库诚实降级（零值 + missing 标注），不编造。

接线方式：ActiveInteractionEngine 注册 engagement 规则，本模块只负责
"算出参与度"，"要不要发声"仍由 AttentionTrigger/Validator/Scheduler 治理。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class EngagementSnapshot:
    """参与度快照（一次采集 = 一个不可变事实集）。"""
    collected_at: str = ""
    window_days: int = 7

    # 对话信号
    dialogue_count: int = 0            # 窗口内用户消息数（sender='cli'）
    dialogue_prev_count: int = 0       # 前一窗口（趋势对照）
    last_interaction_age_days: float = -1.0   # 最近一次用户交互距今天数（无记录 = -1）

    # 目标信号
    goals_created: int = 0
    goals_completed: int = 0
    goal_completion_rate: float = 0.0  # 窗口内 completed/created（无创建 = 0）

    # 综合分
    engagement_score: float = 0.0      # 0.0–1.0
    missing: list[str] = field(default_factory=list)

    def to_context(self) -> dict:
        return {
            "dialogue_count": self.dialogue_count,
            "dialogue_trend": (
                round(self.dialogue_count / max(1, self.dialogue_prev_count), 2)
                if self.dialogue_prev_count else (1.0 if self.dialogue_count else 0.0)),
            "last_interaction_age_days": self.last_interaction_age_days,
            "goal_completion_rate": self.goal_completion_rate,
            "engagement_score": round(self.engagement_score, 4),
        }


def _days_ago_iso(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def collect_engagement(db_path: str, window_days: int = 7) -> EngagementSnapshot:
    """从生产表聚合参与度快照。任何失败项降级为 0 并记入 missing。"""
    snap = EngagementSnapshot(
        collected_at=datetime.now(timezone.utc).isoformat(),
        window_days=window_days)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        snap.missing.append(f"db_open:{e}")
        return snap

    def _q(sql: str, params: tuple = ()) -> list:
        return conn.execute(sql, params).fetchall()

    try:
        # ── 对话频率（user_messages, sender='cli' = 真实用户输入）──
        try:
            row = _q(
                "SELECT COUNT(*) FROM user_messages WHERE sender = 'cli' "
                "AND created_at >= ?", (_days_ago_iso(window_days),))[0]
            snap.dialogue_count = int(row[0] or 0)
            row = _q(
                "SELECT COUNT(*) FROM user_messages WHERE sender = 'cli' "
                "AND created_at >= ? AND created_at < ?",
                (_days_ago_iso(window_days * 2), _days_ago_iso(window_days)))[0]
            snap.dialogue_prev_count = int(row[0] or 0)
            row = _q(
                "SELECT MAX(created_at) FROM user_messages WHERE sender = 'cli'")[0]
            if row and row[0]:
                last = datetime.fromisoformat(
                    str(row[0]).replace("Z", "+00:00"))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                snap.last_interaction_age_days = round(
                    (datetime.now(timezone.utc) - last).total_seconds() / 86400, 2)
        except sqlite3.Error as e:
            snap.missing.append(f"user_messages:{e}")

        # ── 目标完成度（goals 表；状态名兼容大小写）──
        try:
            row = _q(
                "SELECT COUNT(*) FROM goals WHERE created_at >= ?",
                (_days_ago_iso(window_days),))[0]
            snap.goals_created = int(row[0] or 0)
            row = _q(
                "SELECT COUNT(*) FROM goals WHERE status IN "
                "('COMPLETED', 'completed', 'DONE', 'done') "
                "AND updated_at >= ?",
                (_days_ago_iso(window_days),))[0]
            snap.goals_completed = int(row[0] or 0)
            if snap.goals_created > 0:
                snap.goal_completion_rate = round(
                    min(1.0, snap.goals_completed / snap.goals_created), 4)
        except sqlite3.Error as e:
            snap.missing.append(f"goals:{e}")

        # ── 综合参与度分（加权合成，全部可解释）──
        # 活跃度: 窗口内≥7 次对话 = 满分（日均 1 次）
        activity = min(1.0, snap.dialogue_count / max(1.0, window_days))
        recency = (1.0 if 0 <= snap.last_interaction_age_days <= 1
                   else max(0.0, 1.0 - snap.last_interaction_age_days / 7.0)
                   if snap.last_interaction_age_days >= 0 else 0.0)
        snap.engagement_score = round(
            0.5 * activity + 0.2 * recency
            + 0.3 * snap.goal_completion_rate, 4)
    finally:
        conn.close()
    if snap.missing:
        logger.info("engagement snapshot degraded: %s", snap.missing)
    return snap


__all__ = ["EngagementSnapshot", "collect_engagement"]
