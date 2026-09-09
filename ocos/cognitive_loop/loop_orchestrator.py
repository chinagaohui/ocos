"""Phase 46: LoopOrchestrator — 认知循环主编排器。

让所有 Phase 39-45 的器官形成统一的生命循环。

完整闭环 (每 tick):
    1. Perception  → 接收外部输入
    2. Attention   → 分配注意力
    3. Sync        → Self + Memory + World 上下文
    4. Decision    → 形成判断提案
    5. Action      → 选择+执行能力
    6. Learning    → 理解结果 → 验证 → 固化
    7. Health      → 全系统健康自检

核心原则:
    CL46-01: Loop ≠ Autonomy — 循环是协同机制，不自行设定目标
    CL46-02: Health ≠ Self-Rewrite — 检查可以发现问题，不能修改 Identity
    CL46-03: Perception ≠ Truth — 输入信号，不是客观事实
    CL46-04: Learning ≠ Drift — 学习有边界，不漂移 Identity/Constitution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.cognitive_loop.loop_types import (
    LoopPhase, TickOutcome, LoopContext, CognitiveHealthReport,
)
from ocos.cognitive_loop.perception_bridge import PerceptionBridge
from ocos.cognitive_loop.attention_coordinator import AttentionCoordinator
from ocos.cognitive_loop.context_synchronizer import ContextSynchronizer
from ocos.cognitive_loop.decision_pipeline import DecisionPipeline
from ocos.cognitive_loop.action_controller import ActionController, ActionOutcome
from ocos.cognitive_loop.learning_coordinator import (
    LearningCoordinator, ConsolidationResult,
)
from ocos.cognitive_loop.health_monitor import HealthMonitor


@dataclass
class LoopOrchestrator:
    """认知循环主编排器。

    管理 OCOS 的完整认知循环——所有器官协同工作的总指挥。
    """

    perception: PerceptionBridge = field(default_factory=PerceptionBridge)
    attention: AttentionCoordinator = field(default_factory=AttentionCoordinator)
    synchronizer: ContextSynchronizer = field(default_factory=ContextSynchronizer)
    decision: DecisionPipeline = field(default_factory=DecisionPipeline)
    action: ActionController = field(default_factory=ActionController)
    learning: LearningCoordinator = field(default_factory=LearningCoordinator)
    health: HealthMonitor = field(default_factory=HealthMonitor)
    _coupling_bridge: Optional["CognitiveCouplingBridge"] = None  # Phase 62d

    _tick: int = 0
    _contexts: list[LoopContext] = field(default_factory=list)
    _outcomes: list[TickOutcome] = field(default_factory=list)

    # ── Phase 62d: 注入认知耦合桥接 ──

    def inject_coupling_bridge(self, bridge) -> None:
        """注入 CognitiveCouplingBridge — 将信念事件实时反馈给稳态。"""
        self._coupling_bridge = bridge

    # ── 记忆提供者注入（让 wisdom / belief / goals 真正被消费） ──

    def inject_memory_providers(
        self,
        *,
        db_path: Optional[str] = None,
        belief_store=None,
        goal_store=None,
        self_snapshot_fn=None,
    ) -> None:
        """一次性把所有记忆/知识提供者接进 ContextSynchronizer。

        这是"学习闭环"的消费端接线 —— 没有这行，wisdom/belief 就是死数据。
        """
        # Wisdom provider — 从 WisdomStore 读 principle 文本
        def _wisdom_provider() -> list[str]:
            if db_path:
                try:
                    from ocos.agent.wisdom_trigger import load_wisdom_context
                    return load_wisdom_context(db_path, limit=5)
                except Exception:
                    return []
            return []

        # Goals provider — 活跃 goal 列表
        def _goals_provider() -> list[str]:
            if goal_store is None:
                return []
            try:
                goals = goal_store.query_active() if hasattr(goal_store, "query_active") else []
                return [g.description[:80] for g in goals if g]
            except Exception:
                return []

        # Self snapshot provider
        def _self_provider() -> str:
            if self_snapshot_fn:
                try:
                    return str(self_snapshot_fn())[:200]
                except Exception:
                    return ""
            return "Agent current state: unknown"

        self.synchronizer.set_wisdom_provider(_wisdom_provider)
        self.synchronizer.set_goals_provider(_goals_provider)
        self.synchronizer.set_self_provider(_self_provider)

    # ── 主循环 ──

    def tick(self, perception_input: str = "") -> LoopContext:
        """执行一次完整认知循环。"""
        self._tick += 1
        ctx = LoopContext(tick_id=self._tick)

        # ── Phase 1: Perception ──
        ctx.phase = LoopPhase.PERCEIVING
        if perception_input:
            event = self.perception.receive(
                content=perception_input,
                source="input",
                tick_id=self._tick,
            )
            ctx.perception_input = event.raw_content

        # ── Phase 2: Attention ──
        ctx.phase = LoopPhase.ATTENDING
        events = self.perception.pending_events()
        focus = self.attention.evaluate(
            events=events,
            goals=ctx.active_goals,
            context=ctx,
        )
        ctx.attention_focus = focus.target
        ctx.attention_weight = focus.weight

        # Mark event as processed
        for e in events:
            if f"event:{e.event_id}" == focus.target:
                self.perception.mark_processed(e.event_id)

        # ── Phase 3: Context Sync ──
        ctx.phase = LoopPhase.SYNCING_CONTEXT
        ctx = self.synchronizer.sync(ctx)

        # ── Phase 4: Decision ──
        ctx = self.decision.process(ctx)

        # ── Phase 5: Action ──
        outcome, _ = self.action.act(ctx)

        # ── Phase 6: Learning ──
        cons = self.learning.consolidate(ctx)

        # ── Phase 7: Health Check (every 10 ticks) ──
        # Phase 62d: Cognitive coupling — poll belief events every tick
        if self._coupling_bridge is not None:
            self._coupling_bridge.poll()

        if self._tick % 10 == 0:
            ctx.phase = LoopPhase.HEALTH_CHECK
            report = self.health.check(
                tick_id=self._tick,
                memory_count=len(self.learning._experience_log),
                attention_weight=ctx.attention_weight,
            )
            if not report.is_healthy:
                self._tick_outcome(ctx, TickOutcome.HEALTH_ALERT)
                self._contexts.append(ctx)
                return ctx

        # ── Determine outcome ──
        if outcome == ActionOutcome.EXECUTED:
            if cons == ConsolidationResult.CONSOLIDATED:
                self._tick_outcome(ctx, TickOutcome.LEARNING_RECORDED)
            else:
                self._tick_outcome(ctx, TickOutcome.ACTION_TAKEN)
        elif ctx.decision_proposal and ctx.decision_approved:
            self._tick_outcome(ctx, TickOutcome.DECISION_PENDING)
        elif perception_input:
            self._tick_outcome(ctx, TickOutcome.OK)
        else:
            self._tick_outcome(ctx, TickOutcome.NO_INPUT)

        self._contexts.append(ctx)
        # 保持最近 500 个上下文
        if len(self._contexts) > 500:
            self._contexts = self._contexts[-250:]

        return ctx

    def _tick_outcome(self, ctx: LoopContext, outcome: TickOutcome) -> None:
        self._outcomes.append(outcome)

    # ── 状态查询 ──

    @property
    def current_tick(self) -> int:
        return self._tick

    @property
    def recent_contexts(self) -> list[LoopContext]:
        return self._contexts[-20:]

    @property
    def recent_outcomes(self) -> list[TickOutcome]:
        return self._outcomes[-20:]

    @property
    def all_phases_active(self) -> bool:
        """所有阶段是否都有至少一次记录。"""
        seen = {ctx.phase for ctx in self._contexts}
        return LoopPhase.PERCEIVING in seen and LoopPhase.DECIDING in seen

    @property
    def health_report(self) -> CognitiveHealthReport | None:
        return self.health.latest_report

    # ── 生命循环统计 ──

    def loop_summary(self) -> dict:
        """循环运行统计。"""
        outcomes = self._outcomes[-100:]
        return {
            "total_ticks": self._tick,
            "actions_taken": outcomes.count(TickOutcome.ACTION_TAKEN),
            "learning_consolidated": outcomes.count(TickOutcome.LEARNING_RECORDED),
            "decisions_pending": outcomes.count(TickOutcome.DECISION_PENDING),
            "health_alerts": outcomes.count(TickOutcome.HEALTH_ALERT),
            "experiences_stored": len(self.learning._experience_log),
            "attention_focus": self.attention.current,
            "attention_weight": self.attention.weight,
            "is_healthy": self.health.is_healthy,
        }


__all__ = ["LoopOrchestrator"]
