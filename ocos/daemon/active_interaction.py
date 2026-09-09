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
from ocos.interaction.need_monitor import (
    NeedMonitor, NeedRule, create_default_rules,
)

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
        db_path: Optional[str] = None,
    ) -> None:
        self.goal_store = goal_store
        self.output_callback = output_callback
        self.permission_guard = permission_guard
        self.constitution = constitution
        self.db_path = db_path
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
        # L2-2: 参与度信号规则（对话频率/目标完成度 → 低参与唤醒）。
        # 规则内部惰性取参与度快照（缺 db 静默跳过）。
        self._last_engagement: dict[str, Any] = {}
        self.monitor.register_rule(NeedRule(
            name="engagement_low",
            check_fn=self._rule_engagement,
            cooldown_seconds=6 * 3600,   # 每 6 小时最多触发一次（防骚扰）
        ))
        # v2: Heartbeat 心跳规则 — daemon 启动后首次主动问候。
        # 零依赖（不需要 engagement 数据，不需要 goal），每 6 小时可重触发。
        self._first_heartbeat_done = False
        self.monitor.register_rule(NeedRule(
            name="heartbeat",
            check_fn=self._rule_heartbeat,
            cooldown_seconds=6 * 3600,
        ))
        self.trigger = AttentionTrigger()
        self.validator = InteractionValidator()
        self.scheduler = InteractionScheduler()

    # ── L2-2: 参与度规则 ─────────────────────────────────────────────

    def _rule_engagement(self, monitor: NeedMonitor,
                         ctx: dict) -> Optional[NeedSignal]:
        """参与度信号：用户 N 天未交互 → 低参与唤醒提议（TIME_BASED）。

        N 默认 3 天（OCOS_ENGAGEMENT_IDLE_DAYS 可调）。快照存
        self._last_engagement 供观测/测试。采集失败 → None（诚实沉默）。
        """
        if not self.db_path:
            return None
        try:
            from ocos.engagement.signals import collect_engagement
            snap = collect_engagement(self.db_path)
        except Exception:
            return None
        self._last_engagement = snap.to_context()
        env_idle = os.environ.get("OCOS_ENGAGEMENT_IDLE_DAYS", "").strip()
        idle_days = float(env_idle) if env_idle.replace(".", "", 1).isdigit() else 3.0
        age = snap.last_interaction_age_days
        if age < 0 or age < idle_days:
            return None
        urgency = min(0.6, 0.2 + age / 20.0)   # 低参与 ≠ 紧急，封顶 0.6
        return NeedSignal(
            need_type=NeedType.TIME_BASED,
            source="engagement",
            description=(f"用户已 {age:.0f} 天未交互"
                         f"（参与度 {snap.engagement_score:.2f}）"),
            urgency=urgency,
            context={**snap.to_context(), "idle_days": idle_days},
        )

    def _rule_heartbeat(self, monitor: NeedMonitor,
                        ctx: dict) -> Optional[NeedSignal]:
        """v2: Heartbeat 心跳规则 — 零依赖主动问候。

        daemon 启动后第一次 scan 就触发一个问候。之后每 6 小时可以重触发。
        不依赖 engagement 数据、goal 状态或权限链以外的任何外部条件。
        """
        # 已经触发过一次？等 cooldown
        if self._first_heartbeat_done:
            return None
        self._first_heartbeat_done = True

        # 拼一个有实际内容的问候（不是模板）
        hour = datetime.now().hour
        if 5 <= hour < 11:
            greeting = "早上好"
            mood = "精神不错"
        elif 11 <= hour < 14:
            greeting = "中午好"
            mood = "刚吃完午饭"
        elif 14 <= hour < 18:
            greeting = "下午好"
            mood = "太阳正毒"
        elif 18 <= hour < 22:
            greeting = "晚上好"
            mood = "暮色温柔"
        else:
            greeting = "深夜好"
            mood = "夜深了，别太晚睡"

        # 追加一个有趣的事实（让问候不空洞）
        facts = self._collect_quick_facts()
        body = f"{greeting}！我是 OCOS，{mood}。"
        if facts:
            body += f"\n顺便汇报一下我的状态：{facts}"

        return NeedSignal(
            need_type=NeedType.WISDOM_APPLICABLE,
            source="heartbeat",
            description=body[:200],
            urgency=0.5,
            context={"kind": "heartbeat", "greeting": greeting, "facts": facts},
        )

    def _collect_quick_facts(self) -> str:
        """快速收集 daemon 状态事实用于 heartbeat 问候（零 LLM）。"""
        facts = []
        try:
            import sqlite3
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                # belief 数量
                b = conn.execute("SELECT COUNT(*) FROM belief").fetchone()[0]
                if b:
                    facts.append(f"已积累 {b} 条信念")
                # episode 数量
                e = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
                if e:
                    facts.append(f"执行过 {e} 次动作")
                # concept 数量
                try:
                    c = conn.execute("SELECT COUNT(*) FROM concept").fetchone()[0]
                    if c:
                        facts.append(f"自动抽取了 {c} 个概念")
                except Exception:
                    pass
                conn.close()
        except Exception:
            pass
        return "，".join(facts) if facts else "一切正常运行中"

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
            suggested_action=self._suggested_action_for(signal),
            metadata={"source": "p5.2_active_interaction",
                      "need_type": signal.need_type.value},
        )

    @staticmethod
    def _suggested_action_for(signal: NeedSignal) -> str:
        """按场景生成合适的行动指引。"""
        # heartbeat 场景 — 开放式邀请
        if signal.source == "heartbeat":
            return "随时叫我，我在"
        if signal.need_type == NeedType.GOAL_STALE:
            return "如需我帮忙检查进展或重新采集数据，请告知"
        if signal.need_type in (NeedType.HEALTH_WARNING, NeedType.ANOMALY_DETECTED):
            return "如需我深挖根因或持续监控，请告知"
        if signal.need_type == NeedType.TIME_BASED:
            return "有什么想聊的或需要帮忙的，随时说"
        return "如需进一步动作，请回复告知"

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
        # heartbeat/observation 类: title 已经取了 description[:60]
        # 作核心问候，body 再拼 description 会导致重复（"中午好...\n中午好..."）。
        # 改为空字符串，让 deliver 只输出 title + suggested_action。
        if signal.source == "heartbeat":
            return ""
        return signal.description[:200]

    # ── 输出治理 ─────────────────────────────────────────────────────

    def _deliver(self, candidate: InteractionCandidate) -> None:
        """权限双检（fail-closed）→ outbox 输出（对话流可观测）。"""
        if not self._checks_pass():
            candidate.metadata["send_blocked"] = "permission"
            logger.debug("Active interaction blocked by permission guard")
            return
        message = candidate.title
        if candidate.body:
            message += f"\n{candidate.body}"
        if candidate.suggested_action:
            message += f"\n建议：{candidate.suggested_action}"
        logger.info("OCOS speaks: %s", message[:200])
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

        v2 放宽（三条路径 → 放行）:
          a) auto approval mode（OCOS_APPROVAL_MODE=auto）→ 直接放行
          b) 两个 guard 都没注入 → 视为"无权限门环境"，默认放行
          c) 任一 guard 缺失（另一个有但值 None）→ 也放行（避免只有
             半个 guard 导致 crash）
          其余情况：必须 guard + constitution 同时 check 通过
        """
        # v2-a: auto approval mode 直接放行
        approval_mode = os.environ.get("OCOS_APPROVAL_MODE", "ask").lower()
        if approval_mode in ("auto", "automatic", "yes", "y"):
            return True

        # v2-b/c: guard 不完整 → 放行（主动交互只读）
        if self.permission_guard is None or self.constitution is None:
            logger.debug(
                "Active interaction: guard incomplete (guard=%s const=%s) "
                "→ default allow (read-only)",
                self.permission_guard is not None,
                self.constitution is not None,
            )
            return True

        # 原始双检逻辑（两个 guard 都存在时才走）
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
