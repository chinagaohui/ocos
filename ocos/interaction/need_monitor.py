"""Phase 53: NeedMonitor — 内部状态监控，生成主动交互需求。

监控维度:
    - 目标停滞: goal 超过 N 天无进展
    - 健康告警: 系统资源异常
    - 模式识别: 识别到可应用的历史智慧
    - 时间触发: 周期性汇报

类似人脑:
    边缘系统持续扫描内部状态 → 产生需求信号 → 前额叶评估是否行动
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
import time as _time

from ocos.interaction.interaction_types import (
    NeedSignal, NeedType, InteractionPriority,
)


@dataclass
class GoalHealth:
    """目标健康状态。"""
    goal_id: str = ""
    title: str = ""
    days_since_progress: int = 0
    is_stuck: bool = False


@dataclass
class NeedRule:
    """需求检测规则 — 定义何时触发 NeedSignal。

    check_fn: 接受 (monitor, context) → NeedSignal | None
    """
    name: str
    check_fn: Callable[["NeedMonitor", dict], NeedSignal | None]
    cooldown_seconds: float = 300.0  # 同一规则冷却时间
    _last_fired: float = 0.0


@dataclass
class NeedMonitor:
    """需求监控器 — OCOS 的"边缘系统"。

    持续扫描内部状态，产生 NeedSignal。
    不决定是否输出 (交给 InteractionScheduler)。
    不决定输出内容 (交给 InteractionCandidate)。
    只负责: "有什么需要关注的？"
    """

    rules: list[NeedRule] = field(default_factory=list)

    # 外部注入的状态 (由 Cognitive Loop 更新)
    goal_health: dict[str, GoalHealth] = field(default_factory=dict)
    system_health_map: dict[str, float] = field(default_factory=dict)  # module → health_score

    # 统计
    total_signals: int = 0
    last_scan_at: float = 0.0

    def register_rule(self, rule: NeedRule) -> None:
        self.rules.append(rule)

    def remove_rule(self, name: str) -> None:
        self.rules = [r for r in self.rules if r.name != name]

    def scan(self, context: dict | None = None) -> list[NeedSignal]:
        """扫描所有规则，产生 NeedSignal 列表。"""
        ctx = context or {}
        now = _time.time()
        signals: list[NeedSignal] = []

        for rule in self.rules:
            # 冷却检查
            if now - rule._last_fired < rule.cooldown_seconds:
                continue

            try:
                signal = rule.check_fn(self, ctx)
                if signal is not None:
                    signals.append(signal)
                    rule._last_fired = now
            except Exception:
                continue  # 规则崩溃不影响其他

        self.last_scan_at = now
        self.total_signals += len(signals)
        return signals

    def update_goal_health(self, goal_id: str, title: str,
                           days_since_progress: int) -> None:
        """更新单个目标的健康状态。"""
        self.goal_health[goal_id] = GoalHealth(
            goal_id=goal_id,
            title=title,
            days_since_progress=days_since_progress,
            is_stuck=days_since_progress > 30,
        )

    def update_system_health(self, module: str, score: float) -> None:
        self.system_health_map[module] = score

    def get_stale_goals(self, threshold_days: int = 30) -> list[GoalHealth]:
        """获取停滞超过阈值的所有目标。"""
        return [g for g in self.goal_health.values()
                if g.days_since_progress >= threshold_days]


# ═══════════════════════════════════════════════════════════════════════════════
# 内置规则
# ═══════════════════════════════════════════════════════════════════════════════


def _rule_goal_stale(monitor: NeedMonitor, ctx: dict) -> NeedSignal | None:
    """目标停滞检测。

    P5.2 (AGI 计划): 停滞窗口可由 ctx["goal_stale_threshold_days"] 调制
    （默认 30 天；验收场景可调低到 3 天以匹配"依赖数据过期"判定）。
    """
    threshold_days = int(ctx.get("goal_stale_threshold_days", 30))
    stale = monitor.get_stale_goals(threshold_days=threshold_days)
    if not stale:
        return None

    worst = max(stale, key=lambda g: g.days_since_progress)
    # P5.2 (AGI 计划): urgency 按阈值缩放 — 默认 30 天 → 30×3=90 与旧语义
    # 一致（30 天停滞 ≈ 0.33）；阈值调低（如 3 天）时短停滞也能通过
    # AttentionTrigger 的优先级门槛（低阈值场景不被默认急迫度淹没）。
    urgency = min(1.0, worst.days_since_progress / (max(1, threshold_days) * 3.0))

    return NeedSignal(
        need_type=NeedType.GOAL_STALE,
        source=worst.goal_id,
        description=f"目标 '{worst.title}' 已 {worst.days_since_progress} 天无进展",
        urgency=urgency,
        context={
            "goal_id": worst.goal_id,
            "title": worst.title,
            "days": worst.days_since_progress,
        },
    )


def _rule_health_warning(monitor: NeedMonitor, ctx: dict) -> NeedSignal | None:
    """系统健康告警。"""
    unhealthy = [(m, s) for m, s in monitor.system_health_map.items() if s < 0.4]
    if not unhealthy:
        return None

    worst_module, worst_score = min(unhealthy, key=lambda x: x[1])
    return NeedSignal(
        need_type=NeedType.HEALTH_WARNING,
        source=worst_module,
        description=f"模块 '{worst_module}' 健康评分 {worst_score:.2f}，需要关注",
        urgency=0.7,
        context={"module": worst_module, "score": worst_score},
    )


def create_default_rules() -> list[NeedRule]:
    """创建默认需求检测规则集。"""
    return [
        NeedRule(
            name="goal_stale",
            check_fn=_rule_goal_stale,
            cooldown_seconds=3600,  # 每小时最多触发一次
        ),
        NeedRule(
            name="health_warning",
            check_fn=_rule_health_warning,
            cooldown_seconds=600,  # 每10分钟最多触发一次
        ),
    ]


__all__ = ["GoalHealth", "NeedRule", "NeedMonitor", "create_default_rules"]
