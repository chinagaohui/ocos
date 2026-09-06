"""P5.2 (AGI 计划): Phase 53 主动交互唤醒 — 沉睡器官生产接线。

把白皮书 Phase 53 已实现但未接线的组件串成完整生产链路：
  NeedMonitor（内部状态扫描）→ AttentionTrigger（注意力过滤）
  → InteractionValidator（IS53-03 发送前验证）→ InteractionScheduler（节奏治理）
  → 权限双检（PermissionGuard + 行为宪法，fail-closed）→ outbox 输出（对话流）

G6 对齐: 空闲期基于目标状态（停滞/依赖数据过期）触发主动交互提议。

定位: 本模块属 daemon 生产装配层（P1-B）—— daemon 是唯一获准同时依赖
ocos.interaction（Phase 53 组件宿主）与 ocos.monitoring 的装配点；
ProactiveEngine 仍在 ocos.proactive 承担 P2-D 问候/观察模板输出。

约束（IS53 系列，全部继承自 Phase 53 类型层）:
  - 交互 = 提议/提醒，绝不替用户决策、绝不声明自主目标
  - 产出只读化（不触发任何执行动作），仅走 outbox 可观测
  - 频率/去重/冷却由 InteractionScheduler 治理（防骚扰）
  - 任一防护缺失 → 拒绝输出（绝不无检发声）
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ocos.interaction.attention_trigger import AttentionTrigger
from ocos.interaction.interaction_scheduler import InteractionScheduler
from ocos.interaction.interaction_types import (
    InteractionCandidate, InteractionMode, InteractionPriority, NeedSignal,
    NeedType,
)
from ocos.interaction.interaction_validator import (
    InteractionValidator, ValidationVerdict,
)
from ocos.interaction.need_monitor import NeedMonitor, create_default_rules

logger = logging.getLogger(__name__)

# 权限双检使用的动作（主动交互 = Agent 对自身观察的低风险展示，与 P2-D 同款）
_ACTION = "view_self"


class ActiveInteractionEngine:
    """Phase 53 主动交互引擎 — NeedMonitor → AttentionTrigger → Validator → Scheduler。

    所有依赖可选注入，缺失时防御式降级（不抛、不输出）。每个 tick 调用
    scan_and_interact() 扫描一次内部状态，满足条件才经 outbox 产出提议。
    """

    def __init__(
        self,
        *,
        goal_store: Any = None,
        output_callback: Optional[Callable[[str], None]] = None,
        permission_guard: Any = None,
        constitution: Any = None,
        stale_threshold_days: Optional[int] = None,
    ) -> None:
        self.goal_store = goal_store
        self.output_callback = output_callback
        self.permission_guard = permission_guard
        self.constitution = constitution
        # 目标停滞阈值：默认 30 天（白皮书语义）；OCOS_INTERACTION_STALE_DAYS
        # 可调低（验收场景如 3 天）— "目标依赖数据过期"的判定窗口。
        env_days = os.environ.get("OCOS_INTERACTION_STALE_DAYS", "").strip()
        self.stale_threshold_days = int(
            stale_threshold_days
            if stale_threshold_days is not None
            else (env_days if env_days.isdigit() else 30)
        )

        self.monitor = NeedMonitor()
        for rule in create_default_rules():
            self.monitor.register_rule(rule)
        self.trigger = AttentionTrigger()
        self.validator = InteractionValidator()
        self.scheduler = InteractionScheduler()

    # ── 入口 ─────────────────────────────────────────────────────────

    def scan_and_interact(self) -> dict[str, Any]:
        """扫描一次内部状态 → 全链处理 → 产出可观测交互提议。

        返回统计（供日志/指标/测试断言）。全链防御：任一环节异常不阻断。
        """
        stats: dict[str, Any] = {
            "scanned": 0, "prioritized": 0, "rejected": 0,
            "submitted": 0, "sent": 0, "pending": 0,
        }
        try:
            self._refresh_goal_health()
            signals = self.monitor.scan({
                "goal_stale_threshold_days": self.stale_threshold_days,
            })
            stats["scanned"] = len(signals)

            for signal in signals:
                priority = self.trigger.evaluate(signal)
                if priority is None:
                    continue
                stats["prioritized"] += 1
                candidate = self._build_candidate(signal, priority)
                verdict = self.validator.validate(candidate)
                if verdict.verdict == ValidationVerdict.REJECT:
                    stats["rejected"] += 1
                    continue
                if self.scheduler.submit(candidate):
                    stats["submitted"] += 1

            for sent in self.scheduler.dequeue(max_count=1):
                stats["sent"] += 1
                self._deliver(sent)
            stats["pending"] = self.scheduler.pending_count()
            if stats["sent"]:
                logger.info("Active interaction sent: %s", str(stats)[:160])
            self._record_metrics(stats)
        except Exception as e:  # 防御兜底：绝不向 tick 抛
            logger.warning("ActiveInteraction scan degraded: %s", e)
            stats["error"] = str(e)
        return stats

    # ── 内部状态刷新 ────────────────────────────────────────────────

    def _refresh_goal_health(self) -> None:
        """从 goal_store 加载活跃目标 → 计算停滞天数 → 更新 NeedMonitor。

        目标依赖数据过期的判定窗口 = updated_at 距今天数 >= 阈值
        （GoalStore 认领/推进会刷新 updated_at，久未推进即视为依赖数据过期）。
        """
        if self.goal_store is None:
            return
        try:
            goals = self.goal_store.load_active()
        except Exception:
            return
        for g in goals or []:
            gid = g.get("id", "") if isinstance(g, dict) else getattr(g, "id", "")
            if not gid:
                continue
            title = (g.get("description", "")[:60]
                     if isinstance(g, dict)
                     else getattr(g, "description", "")[:60]) or gid
            days = self._days_since(
                g.get("updated_at") or g.get("created_at")
                if isinstance(g, dict)
                else getattr(g, "updated_at", "") or getattr(g, "created_at", "")
            )
            self.monitor.update_goal_health(gid, title, days)

    @staticmethod
    def _days_since(iso_ts: str) -> int:
        """ISO 时间戳 → 距今天数（解析失败/缺失 → 0，保守不误报）。"""
        if not iso_ts:
            return 0
        try:
            dt = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, int((datetime.now(timezone.utc) - dt).total_seconds() // 86400))
        except Exception:
            return 0

    # ── 交互构建 ─────────────────────────────────────────────────────

    def _build_candidate(self, signal: NeedSignal,
                         priority: InteractionPriority) -> InteractionCandidate:
        """NeedSignal → InteractionCandidate（只读提议，不含执行意图）。"""
        return InteractionCandidate(
            mode=self._mode_for(signal.need_type),
            priority=priority,
            need=signal,
            title=self._title_for(signal),
            body=self._body_for(signal),
            suggested_action="如需我帮忙检查或重新采集，请回复告知（只读检查，不擅自改动）",
            metadata={"source": "p5.2_active_interaction",
                      "need_type": signal.need_type.value},
        )

    @staticmethod
    def _mode_for(need_type: NeedType) -> InteractionMode:
        return {
            NeedType.GOAL_STALE: InteractionMode.REMINDER,
            NeedType.HEALTH_WARNING: InteractionMode.ALERT,
            NeedType.ANOMALY_DETECTED: InteractionMode.ALERT,
            NeedType.WISDOM_APPLICABLE: InteractionMode.OBSERVATION,
            NeedType.PATTERN_RECOGNIZED: InteractionMode.OBSERVATION,
            NeedType.TIME_BASED: InteractionMode.REPORT,
        }.get(need_type, InteractionMode.OBSERVATION)

    @staticmethod
    def _title_for(signal: NeedSignal) -> str:
        ctx = signal.context or {}
        if signal.need_type == NeedType.GOAL_STALE:
            return (f"目标「{ctx.get('title', signal.source)}」"
                    f"已 {ctx.get('days', '?')} 天无进展")
        if signal.need_type == NeedType.HEALTH_WARNING:
            return (f"模块「{ctx.get('module', signal.source)}」"
                    f"健康度偏低（{ctx.get('score', '?')}）")
        return signal.description[:60]

    @staticmethod
    def _body_for(signal: NeedSignal) -> str:
        if signal.need_type == NeedType.GOAL_STALE:
            return ("目标依赖的数据/指标可能已过期。建议检查进展和依赖数据"
                    "状态，是否需要重新采集或调整目标方向？")
        if signal.need_type == NeedType.HEALTH_WARNING:
            return "系统内部状态异常，建议关注相关模块运行情况。"
        return signal.description[:200]

    # ── 输出治理 ─────────────────────────────────────────────────────

    def _deliver(self, candidate: InteractionCandidate) -> None:
        """权限双检（fail-closed）→ outbox 输出（对话流可观测）。"""
        if not self._checks_pass():
            candidate.metadata["send_blocked"] = "permission"
            logger.debug("Active interaction blocked by permission gate")
            return
        message = f"{candidate.title}\n{candidate.body}"
        if candidate.suggested_action:
            message += f"\n建议：{candidate.suggested_action}"
        if self.output_callback is not None:
            try:
                self.output_callback(message)
                return
            except Exception as e:
                logger.warning("Active interaction callback failed: %s", e)
        logger.info("[active-interaction] %s", message)

    def _checks_pass(self) -> bool:
        """权限双检：PermissionGuard + 宪法均允许才放行。

        fail-closed：任一防护缺失 → False；检查异常 → False。绝不无检输出。
        """
        if self.permission_guard is None or self.constitution is None:
            return False
        context = {"origin": "active_interaction", "channel": "local"}
        try:
            g = self.permission_guard.check(_ACTION, context)
            if not getattr(g, "allowed", False):
                return False
            constitution = self.constitution
            if hasattr(constitution, "check_action"):
                c = constitution.check_action(_ACTION, context)
            elif hasattr(constitution, "check_decision"):
                from types import SimpleNamespace
                c = constitution.check_decision(
                    SimpleNamespace(action=_ACTION), context)
            else:
                return False
            if not getattr(c, "allowed", False):
                return False
        except Exception:
            return False
        return True

    def _record_metrics(self, stats: dict[str, Any]) -> None:
        """P5.2 观测打点：active_interaction 计数（未装配监控时静默 no-op）。"""
        try:
            from ocos.monitoring.manager import record_global
            record_global("active_interaction", float(stats.get("scanned", 0)),
                          labels={"stage": "scanned"})
            record_global("active_interaction", float(stats.get("sent", 0)),
                          labels={"stage": "sent"})
        except Exception:
            pass


__all__ = ["ActiveInteractionEngine"]
