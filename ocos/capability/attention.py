"""Phase 30: Attention Model — 注意力系统。

ATTENTION_MODEL v1.0 — Attention 不是 Capability，而是 Consciousness。
它决定"我现在应该看哪里"——管理焦点、队列、疲劳和模式切换。

核心组件:
  AttentionManager
    ├── focus（当前焦点）     target_type/id/priority/started_at/duration
    ├── queue（关注队列）     优先级排序的候焦项目
    ├── history（注意力历史） 最近 N 次切换 + 模式识别
    ├── state（注意力状态）   FOCUSED/SCANNING/IDLE/DISTRIBUTED
    └── fatigue（疲劳管理）   积累/恢复 + 自动模式降级

优先级算法:
  最终优先级 = base_priority × urgency_boost × relevance_to_current_goal

疲劳模型:
  FOCUSED: +0.02/min, SCANNING: +0.005/min, IDLE/SLEEP: -0.05/min

约束:
  - 每次切换 +0.02 疲劳
  - 切换成本 > 收益时不切换
  - fatigue > 0.9 → 强制 IDLE
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────


class AttentionMode(Enum):
    """注意力模式（ATTENTION_MODEL §4）。"""
    FOCUSED = auto()       # 深度关注一个目标
    SCANNING = auto()      # 快速扫描多个输入源
    IDLE = auto()          # 无活跃目标，等待输入
    DISTRIBUTED = auto()   # 同时关注 2-3 个源


class TargetType(Enum):
    """焦点目标类型。"""
    USER_INPUT = auto()
    USER_INTERACTION = auto()
    GOAL = auto()
    INTENT = auto()
    EVENT = auto()
    INTERNAL_SIGNAL = auto()
    ANOMALY = auto()
    TIMED_EVENT = auto()
    ENVIRONMENT_CHANGE = auto()
    REFLECTION = auto()
    CONFLICT = auto()
    HEALTH_ALERT = auto()


# ── Data Types ───────────────────────────────────────────────────────────────


@dataclass
class FocusTarget:
    """注意力焦点（ATTENTION_MODEL §2.focus）。"""
    target_type: TargetType
    target_id: str
    priority: float = 0.5        # [0.0, 1.0]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    description: str = ""

    @property
    def duration_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    @property
    def base_priority(self) -> float:
        """基于目标类型的基础优先级（ATTENTION_MODEL §3 表格）。"""
        _map: dict[TargetType, float] = {
            TargetType.USER_INPUT: 1.0,
            TargetType.ANOMALY: 0.9,
            TargetType.HEALTH_ALERT: 0.9,
            TargetType.USER_INTERACTION: 0.8,
            TargetType.CONFLICT: 0.8,
            TargetType.GOAL: 0.7,  # Goal 到期; 普通 Goal 由 urgency_boost 调整
            TargetType.INTENT: 0.6,
            TargetType.TIMED_EVENT: 0.4,
            TargetType.ENVIRONMENT_CHANGE: 0.3,
            TargetType.REFLECTION: 0.3,
            TargetType.EVENT: 0.5,
            TargetType.INTERNAL_SIGNAL: 0.5,
        }
        return _map.get(self.target_type, 0.5)


@dataclass(order=True)
class QueueItem:
    """关注队列中的候焦项目。"""
    item_id: str = field(compare=False)
    target_type: TargetType = field(compare=False, default=TargetType.EVENT)
    priority: float = field(compare=False, default=0.5)
    urgency: float = field(compare=False, default=1.0)
    reason: str = field(compare=False, default="")
    enqueued_at: datetime = field(compare=False, default_factory=lambda: datetime.now(timezone.utc))
    sort_priority: float = field(default=0.0)  # 用于 heapq 排序（取负）

    @property
    def final_priority(self) -> float:
        return self.priority * self.urgency


@dataclass
class AttentionSnapshot:
    """注意力系统完整快照（用于集成到 MonitorSnapshot）。"""
    mode: AttentionMode = AttentionMode.IDLE
    focus: FocusTarget | None = None
    queue_length: int = 0
    top_queue_item: QueueItem | None = None
    switch_count: int = 0
    fatigue: float = 0.0
    history_length: int = 0


# ── AttentionManager ─────────────────────────────────────────────────────────


class AttentionManager:
    """注意力管理器（ATTENTION_MODEL v1.0）。

    管理焦点选择、队列、疲劳和模式切换。

    用法:
        att = AttentionManager()
        att.shift_focus(FocusTarget(TargetType.USER_INPUT, "msg-001"))
        att.enqueue(QueueItem(...))
        att.tick(seconds=60)  # 每分钟推进疲劳
        snap = att.snapshot()
    """

    # ── 疲劳常量 ─────────────────────────────────────────────────────

    FATIGUE_RATES: dict[AttentionMode, float] = {
        AttentionMode.FOCUSED: 0.02 / 60,    # per second
        AttentionMode.SCANNING: 0.005 / 60,
        AttentionMode.DISTRIBUTED: 0.01 / 60,
        AttentionMode.IDLE: -0.05 / 60,
    }

    SWITCH_FATIGUE_COST: float = 0.02
    FATIGUE_WARNING: float = 0.5
    FATIGUE_CRITICAL: float = 0.7
    FATIGUE_FORCE_IDLE: float = 0.9
    MAX_QUEUE_SIZE: int = 10
    MAX_HISTORY: int = 50

    def __init__(self) -> None:
        self._focus: FocusTarget | None = None
        self._queue: list[QueueItem] = []
        self._history: list[dict[str, Any]] = []
        self._mode: AttentionMode = AttentionMode.IDLE
        self._switch_count: int = 0
        self._fatigue: float = 0.0

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def mode(self) -> AttentionMode:
        return self._mode

    @property
    def focus(self) -> FocusTarget | None:
        return self._focus

    @property
    def fatigue(self) -> float:
        return self._fatigue

    @property
    def switch_count(self) -> int:
        return self._switch_count

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def queue_peek(self) -> QueueItem | None:
        return self._queue[0] if self._queue else None

    # ── Focus Operations ────────────────────────────────────────────────

    def shift_focus(self, target: FocusTarget, *, force: bool = False) -> bool:
        """切换注意力到新目标。

        规则:
          - 如果 force=True，跳过成本检查
          - 如果切换成本 > 新目标收益，拒绝切换
          - 切换时保存旧焦点到历史，清空部分疲劳
        """
        # 成本/收益分析
        if not force and self._focus is not None:
            switch_cost = self._estimate_switch_cost(self._focus, target)
            target_benefit = target.priority
            if switch_cost > target_benefit:
                logger.debug("Attention: switch rejected (cost %.2f > benefit %.2f)", switch_cost, target_benefit)
                return False

        # 保存旧焦点
        if self._focus is not None:
            self._save_to_history(self._focus, "switched")

        # 切换
        target.started_at = datetime.now(timezone.utc)
        self._focus = target
        self._switch_count += 1
        self._apply_switch_fatigue()

        # 自动调整模式
        if self._mode == AttentionMode.IDLE:
            self._mode = AttentionMode.SCANNING

        logger.debug("Attention: focused on %s/%s (priority=%.2f)", target.target_type.name, target.target_id, target.priority)
        return True

    def release_focus(self) -> FocusTarget | None:
        """释放当前焦点（进入 IDLE）。"""
        if self._focus is None:
            return None
        old = self._focus
        self._save_to_history(old, "released")
        self._focus = None
        self._mode = AttentionMode.IDLE
        return old

    # ── Queue Operations ────────────────────────────────────────────────

    def enqueue(self, item: QueueItem) -> bool:
        """加入关注队列。

        Returns:
            True 如果成功入队，False 如果队列已满。
        """
        if len(self._queue) >= self.MAX_QUEUE_SIZE:
            # 如果新项目优先级高于队尾最低优先级的项目，替换之
            lowest = min(self._queue, key=lambda x: x.final_priority)
            if item.final_priority > lowest.final_priority:
                self._queue.remove(lowest)
            else:
                logger.debug("Attention: queue full, rejected %s", item.item_id)
                return False

        # 计算排序优先级（取负以让 heapq 按降序排列）
        item.sort_priority = -item.final_priority
        self._queue.append(item)
        self._queue.sort(key=lambda x: x.final_priority, reverse=True)
        return True

    def dequeue_best(self) -> QueueItem | None:
        """取出队列中优先级最高的项目。"""
        if not self._queue:
            return None
        return self._queue.pop(0)

    def clear_queue(self) -> None:
        """清空关注队列。"""
        self._queue.clear()

    # ── Mode Operations ─────────────────────────────────────────────────

    def set_mode(self, mode: AttentionMode) -> None:
        """手动设置注意力模式。"""
        self._mode = mode

    def auto_mode(self) -> AttentionMode:
        """根据疲劳自动调整模式。"""
        if self._fatigue > self.FATIGUE_FORCE_IDLE:
            self._mode = AttentionMode.IDLE
        elif self._fatigue > self.FATIGUE_CRITICAL and self._mode == AttentionMode.FOCUSED:
            self._mode = AttentionMode.SCANNING
        elif self._fatigue > self.FATIGUE_WARNING and self._mode == AttentionMode.FOCUSED:
            # 不强制改模式，但建议
            pass
        return self._mode

    # ── Fatigue / Tick ──────────────────────────────────────────────────

    def tick(self, seconds: float = 1.0) -> None:
        """时间推进：更新疲劳。

        Args:
            seconds: 经过的秒数
        """
        rate = self.FATIGUE_RATES.get(self._mode, 0.0)
        self._fatigue = max(0.0, min(1.0, self._fatigue + rate * seconds))
        self.auto_mode()

    def reset_fatigue(self) -> None:
        """重置疲劳（通常在 SLEEP 后调用）。"""
        self._fatigue = 0.0

    def _apply_switch_fatigue(self) -> None:
        self._fatigue = min(1.0, self._fatigue + self.SWITCH_FATIGUE_COST)

    # ── History ─────────────────────────────────────────────────────────

    def _save_to_history(self, target: FocusTarget, reason: str) -> None:
        entry = {
            "target_type": target.target_type.name,
            "target_id": target.target_id,
            "priority": target.priority,
            "duration_seconds": target.duration_seconds,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(entry)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    # ── Priority Calculation ────────────────────────────────────────────

    def calculate_priority(
        self,
        target: FocusTarget,
        *,
        urgency_boost: float = 1.0,
        relevance: float = 0.5,
    ) -> float:
        """计算最终优先级（ATTENTION_MODEL §3）。

        最终优先级 = base_priority × urgency_boost × relevance_to_current_goal

        Args:
            target: 焦点目标
            urgency_boost: 紧急度加成 [1.0, 1.5]
            relevance: 与当前 Goal 的相关度 [0.0, 1.0]

        Returns:
            最终优先级 [0.0, 1.0]
        """
        bp = target.base_priority
        ub = max(1.0, min(1.5, urgency_boost))
        rel = max(0.0, min(1.0, relevance))
        return min(1.0, bp * ub * rel)

    # ── Internal ────────────────────────────────────────────────────────

    def _estimate_switch_cost(
        self, current: FocusTarget, new: FocusTarget
    ) -> float:
        """估算注意力切换成本。

        成本因素:
          - 中断当前焦点（如果未完成）= 0.3
          - 模式切换成本 = 0.1
          - 类型切换成本（如 USER_INPUT → GOAL）= 0.1
        """
        cost = 0.0
        # 中断成本
        if current.target_type in (TargetType.GOAL, TargetType.INTENT):
            cost += 0.3  # 未完成的 Goal 被中断
        elif current.target_type in (TargetType.USER_INPUT,):
            cost += 0.5  # 用户交互被中断（很糟糕）
        # 类型切换成本
        if current.target_type != new.target_type:
            cost += 0.1
        return cost

    # ── Snapshot ────────────────────────────────────────────────────────

    def snapshot(self) -> AttentionSnapshot:
        """生成注意力系统完整快照。"""
        return AttentionSnapshot(
            mode=self._mode,
            focus=self._focus,
            queue_length=len(self._queue),
            top_queue_item=self._queue[0] if self._queue else None,
            switch_count=self._switch_count,
            fatigue=self._fatigue,
            history_length=len(self._history),
        )

    # ── Integration: Life Cycle mode mapping ────────────────────────────

    _LIFECYCLE_MODE_MAP: dict[str, AttentionMode] = {
        "WAKE": AttentionMode.SCANNING,
        "OBSERVE": AttentionMode.SCANNING,
        "THINK": AttentionMode.FOCUSED,
        "DECIDE": AttentionMode.FOCUSED,
        "ACT": AttentionMode.FOCUSED,
        "REFLECT": AttentionMode.SCANNING,
        "LEARN": AttentionMode.FOCUSED,
        "SLEEP": AttentionMode.IDLE,
        "DREAM": AttentionMode.IDLE,
    }

    def set_mode_for_lifecycle(self, lifecycle_stage: str) -> None:
        """根据 Life Cycle 阶段自动设置注意力模式（ATTENTION_MODEL §7）。"""
        mode = self._LIFECYCLE_MODE_MAP.get(lifecycle_stage.upper())
        if mode is not None:
            self._mode = mode
            if mode == AttentionMode.IDLE:
                self.release_focus()
        else:
            logger.warning("Unknown lifecycle stage: %s", lifecycle_stage)


# ── Phase 35: Cognitive Attention Controller ──────────────────────────────


from dataclasses import dataclass
from enum import Enum as _Enum


class FocusState(_Enum):
    """焦点状态机状态（Freeze §2.2）。"""
    IDLE = "IDLE"                # 无焦点
    FOCUSED = "FOCUSED"          # 深度关注单一目标
    INTERRUPTED = "INTERRUPTED"  # 被外部更高优先级中断
    SUSPENDED = "SUSPENDED"      # 上下文已保存，等待重新评估
    RE_EVALUATION = "RE_EVALUATION"  # 重新评估是否恢复


# Freeze §4.3 默认权重
FROZEN_WEIGHTS: dict[str, float] = {
    "goal_priority": 0.30,
    "relevance": 0.25,
    "urgency": 0.20,
    "decay": 0.10,
    "confidence": 0.10,
}

# Freeze §3.2a 滞后边距
HYSTERESIS_MARGIN: float = 0.15

# Freeze §3.5 中断频率上限
MAX_INTERRUPTS_PER_MINUTE: int = 6
INTERRUPT_COOLDOWN_MS: int = 500

# §4.5 信源可信度
SOURCE_TRUST: dict[str, float] = {
    "user_input": 1.0,
    "file_change": 0.8,
    "timer": 0.7,
    "webhook": 0.5,
    "agent_result": 0.6,
    "unauthenticated": 0.3,
}


@dataclass
class _SuspendedContext:
    """被中断的焦点上下文（Freeze §3.4）。"""
    focus_target: FocusTarget
    progress: float = 0.0
    last_score: float = 0.0
    suspended_at: float = 0.0


class CognitiveAttentionController(AttentionManager):
    """Phase 35: 认知注意力控制器（Freeze 附录A，C 层）。

    唯一持有 Attention 决策权的组件。所有 current_focus 变更必须经过此控制器。

    职责:
      - 完整注意力度量（5 维评分：novelty + relevance + urgency + decay + confidence）
      - 焦点状态机（FOCUSED → INTERRUPTED → SUSPENDED → RE_EVALUATION）
      - 中断策略与频率控制
      - WorkingMemory 分配指令生成
      - 注意力主权检查（禁止创建 Goal / 禁止修改 Self）

    不负责:
      - 创建 Goal（那是 GoalManager 的权限）
      - 执行任务（那是 ExecutionLayer 的职责）
      - 修改 Agent 状态（只通过 ABI 传递决策）
    """

    def __init__(self) -> None:
        super().__init__()
        self._focus_state: FocusState = FocusState.IDLE
        self._suspended_contexts: list[_SuspendedContext] = []
        self._recent_interrupts: list[float] = []  # 中断时间戳
        self._scoring_engine: Any = None  # AttentionScoringEngine (B 层)
        self._event_scores: dict[str, Any] = {}    # event_id → AttentionScoreTrace

    @property
    def focus_state(self) -> FocusState:
        return self._focus_state

    @property
    def current_focus(self) -> "FocusTarget | None":
        """agent_runtime 兼容别名（UX-P2: 主消费者按此名读取当前焦点）。"""
        return self._focus

    def push_focus(self, target: "FocusTarget") -> bool:
        """agent_runtime 兼容入口 — 推送焦点信号（强制切换，忽略切换成本）。

        语义 = 结果驱动的注意力信号（step 9 反刍），非 tick 内竞争性切换。
        """
        return self.shift_focus(target, force=True)

    @property
    def sovereign(self) -> bool:
        """是否为唯一的 Attention 决策权威。"""
        return True

    # ── §4: Composite Priority ──────────────────────────────────────────

    def compute_composite_priority(
        self,
        *,
        goal_priority: float = 0.0,
        relevance: float = 0.0,
        urgency: float = 0.0,
        time_decay: float = 1.0,
        confidence: float = 0.5,
    ) -> float:
        """冻结的五维复合优先级（Freeze §4.1）。"""
        return (
            FROZEN_WEIGHTS["goal_priority"] * goal_priority
            + FROZEN_WEIGHTS["relevance"] * relevance
            + FROZEN_WEIGHTS["urgency"] * urgency
            + FROZEN_WEIGHTS["decay"] * time_decay
            + FROZEN_WEIGHTS["confidence"] * confidence
        )

    @staticmethod
    def source_confidence(source_type: str) -> float:
        """信源可信度映射（Freeze §4.5）。"""
        return SOURCE_TRUST.get(source_type, SOURCE_TRUST["unauthenticated"])

    # ── §3: Interrupt Policy ────────────────────────────────────────────

    def _interrupt_rate_ok(self) -> bool:
        """检查中断频率是否在上限内（Freeze §3.5）。"""
        now = time.time()
        # 清洗超过 1 分钟的旧记录
        self._recent_interrupts = [
            t for t in self._recent_interrupts if now - t < 60
        ]
        return len(self._recent_interrupts) < MAX_INTERRUPTS_PER_MINUTE

    def _record_interrupt(self) -> None:
        self._recent_interrupts.append(time.time())

    def evaluate_interrupt(
        self,
        new_priority: float,
        new_urgency: float,
        new_source_type: str,
    ) -> tuple[bool, str]:
        """评估是否应中断当前焦点（Freeze §3.2 + §3.3）。

        Returns:
            (should_interrupt, reason)
        """
        if self._focus is None:
            return True, "no current focus"

        if not self._interrupt_rate_ok():
            return False, "interrupt rate limit reached — queued"

        current_priority = self._focus.priority

        # a) 优先级中断: 需要超过滞后边距
        if new_priority > current_priority + HYSTERESIS_MARGIN:
            # b) 紧急中断: CRITICAL 且域不重叠
            if new_urgency > 0.8:
                return True, "critical interrupt — urgency > 0.8"

            return True, f"priority interrupt: {new_priority:.2f} > {current_priority:.2f} + {HYSTERESIS_MARGIN}"

        # c) 健康中断: 疲劳
        if self._fatigue > self.FATIGUE_FORCE_IDLE:
            return True, "fatigue forced idle"

        return False, f"priority delta insufficient: {new_priority - current_priority:.2f} < {HYSTERESIS_MARGIN}"

    # ── §2: Focus State Machine ─────────────────────────────────────────

    def _transition_focus_state(
        self,
        target_state: FocusState,
        reason: str,
    ) -> None:
        old_state = self._focus_state
        self._focus_state = target_state
        logger.debug(
            "Attention focus state: %s → %s (%s)",
            old_state.value, target_state.value, reason,
        )

    def _suspend_current_focus(self) -> _SuspendedContext | None:
        """挂起当前焦点（Freeze §3.4 步骤 1）。"""
        if self._focus is None:
            return None
        ctx = _SuspendedContext(
            focus_target=self._focus,
            last_score=self._focus.priority,
            suspended_at=time.time(),
        )
        self._suspended_contexts.append(ctx)
        # 限制挂起数量
        if len(self._suspended_contexts) > 3:
            self._suspended_contexts.pop(0)
        return ctx

    # ── decide() — 核心决策管道 ─────────────────────────────────────────

    def decide(
        self,
        events: list[dict[str, Any]],
        active_goals: list[str] | None = None,
    ) -> list[Any]:
        """Phase 35 核心决策管道（Freeze §7.1 完整路径）。

        输入: 归一化事件列表 + 活跃目标
        输出: AttentionDecision[] — 每条事件一个决策

        管道:
          events → score() → evaluate_interrupt() → apply_state_machine() → AttentionDecision
        """
        from ocos.contracts.attention_abi import (
            AttentionDecision, AttentionScoreTrace, DecisionType,
            FocusChange, WMAllocation,
        )

        decisions: list[Any] = []
        active_goals = active_goals or []

        for event in events:
            event_id = event.get("event_id", "unknown")
            event_type = event.get("event_type", "unknown")
            source_type = event.get("source_type", "unauthenticated")
            priority_hint = event.get("candidate_score", 0.3)

            # ── 1. 评分 (B 层: AttentionScoringEngine) ──
            confidence = self.source_confidence(source_type)

            # 如果有 scoring_engine 就用它的精细评分，否则用 candidate_score 近似
            novelty = priority_hint * 0.4
            relevance = priority_hint * 0.5  # 基础相关性，非零即使无活跃目标
            if active_goals:
                relevance = max(relevance, priority_hint * 0.6)  # 有活跃目标时提升
            urgency = 0.3 + priority_hint * 0.3

            composite = self.compute_composite_priority(
                goal_priority=priority_hint,
                relevance=relevance,
                urgency=urgency,
                confidence=confidence,
            )

            trace = AttentionScoreTrace(
                novelty=round(novelty, 4),
                goal_relevance=round(relevance, 4),
                urgency=round(urgency, 4),
                confidence=round(confidence, 4),
                composite=round(composite, 4),
                weights_used=FROZEN_WEIGHTS,
                source=source_type,
            )

            # ── 2. 决策 (C 层: CognitiveAttentionController) ──
            decision_type = DecisionType.DISMISSED
            focus_change = None
            wm_alloc = None
            reason = ""

            # 主权检查 §11.3 — 检查 event_type + summary
            event_type_str = str(event.get("event_type", "")).lower() if isinstance(event, dict) else ""
            event_summary = str(event.get("summary", "")).lower() if isinstance(event, dict) else str(event).lower()
            forbidden_patterns = [
                "create goal", "create_goal", "modify goal", "modify_goal",
                "new goal", "set goal", "change goal", "change value",
                "call agent", "call_agent", "modify self", "modify_self",
                "change identity", "delete goal",
            ]
            if any(p in event_type_str for p in forbidden_patterns) or \
               any(p in event_summary for p in forbidden_patterns):
                decision_type = DecisionType.DISMISSED
                reason = "sovereignty violation — attention cannot create/modify goals"
            elif composite >= 0.7:
                # 高优先级：评估是否中断当前焦点
                should_interrupt, interrupt_reason = self.evaluate_interrupt(
                    new_priority=composite,
                    new_urgency=urgency,
                    new_source_type=source_type,
                )
                if should_interrupt and self._focus is not None:
                    # 挂起当前焦点 (§3.4)
                    suspended = self._suspend_current_focus()
                    self._transition_focus_state(FocusState.INTERRUPTED, interrupt_reason)
                    self._transition_focus_state(FocusState.SUSPENDED, "context saved")

                    focus_change = FocusChange(
                        old_focus_id=self._focus.target_id,
                        old_target_type=self._focus.target_type.name,
                        new_focus_id=event_id,
                        new_target_type=event_type,
                        reason=interrupt_reason,
                        suspend_context=True,
                    )

                    # 切换焦点
                    ft = FocusTarget(
                        target_type=TargetType.EVENT,
                        target_id=event_id,
                        priority=composite,
                        description=f"Event: {event_type} (composite={composite:.2f})",
                    )
                    self.shift_focus(ft, force=True)
                    decision_type = DecisionType.ACCEPTED
                    reason = interrupt_reason
                    self._record_interrupt()

                    wm_alloc = WMAllocation(
                        event_id=event_id,
                        slot_type="current_focus",
                        attention_weight=composite,
                    )
                else:
                    # 高分但无当前焦点：直接接受
                    ft = FocusTarget(
                        target_type=TargetType.EVENT,
                        target_id=event_id,
                        priority=composite,
                        description=f"Event: {event_type}",
                    )
                    self.shift_focus(ft, force=True)
                    self._transition_focus_state(FocusState.FOCUSED, "new high-priority event")
                    decision_type = DecisionType.ACCEPTED
                    reason = "accepted — high composite priority"

                    wm_alloc = WMAllocation(
                        event_id=event_id,
                        slot_type="current_focus",
                        attention_weight=composite,
                    )

            elif composite >= 0.4:
                decision_type = DecisionType.QUEUED
                reason = "moderate priority — queued for attention queue"
                wm_alloc = WMAllocation(
                    event_id=event_id,
                    slot_type="environmental_scan",
                    attention_weight=composite * 0.3,
                )

            elif composite >= 0.2:
                decision_type = DecisionType.DEFERRED
                reason = "low priority — deferred, logged but not queued"

            else:
                decision_type = DecisionType.DISMISSED
                reason = "noise — below attention threshold"

            decision = AttentionDecision(
                event_id=event_id,
                decision=decision_type,
                score_trace=trace,
                focus_change=focus_change,
                wm_allocation=wm_alloc,
                reason=reason,
            )
            decisions.append(decision)

        return decisions

    # ── Re-evaluation ───────────────────────────────────────────────────

    def re_evaluate_suspended(self) -> Any | None:
        """评估挂起的焦点是否应恢复（Freeze §2.2 RE_EVALUATION）。

        恢复也是一次注意力决策，不是自动回滚。
        """
        if not self._suspended_contexts:
            return None

        from ocos.contracts.attention_abi import (
            AttentionDecision, AttentionScoreTrace, DecisionType,
            FocusChange, WMAllocation,
        )

        ctx = self._suspended_contexts[-1]  # 最近挂起的
        elapsed = time.time() - ctx.suspended_at

        time_decay = 2.718 ** (-0.001 * elapsed)  # e^(-λt), λ=0.001
        new_priority = self.compute_composite_priority(
            goal_priority=ctx.last_score,
            relevance=ctx.last_score * 0.5,
            urgency=0.3,
            time_decay=time_decay,
            confidence=0.8,
        )

        self._transition_focus_state(FocusState.RE_EVALUATION,
                                     f"re-evaluating {ctx.focus_target.target_id}")

        if new_priority >= 0.4 and self._interrupt_rate_ok():
            # 恢复焦点
            ft = ctx.focus_target
            ft.priority = new_priority
            self.shift_focus(ft, force=True)
            self._suspended_contexts.pop()
            self._transition_focus_state(FocusState.FOCUSED, "resumed from suspended")

            return AttentionDecision(
                event_id=ft.target_id,
                decision=DecisionType.ACCEPTED,
                score_trace=AttentionScoreTrace(composite=new_priority, time_decay=time_decay),
                focus_change=FocusChange(
                    new_focus_id=ft.target_id,
                    new_target_type=ft.target_type.name,
                    reason="re_evaluation — resume",
                ),
                wm_allocation=WMAllocation(
                    event_id=ft.target_id,
                    slot_type="current_focus",
                    attention_weight=new_priority,
                ),
                reason="resumed from suspended context",
            )
        else:
            # 放弃
            self._suspended_contexts.pop()
            self._transition_focus_state(FocusState.IDLE if self._focus is None else self._focus_state,
                                         f"abandoned suspended: {ctx.focus_target.target_id}")
            return None

    # ── Phase 36: emit_report ────────────────────────────────────────────

    def emit_report(self, tick_id: str = "", last_decisions_raw=None) -> "Any":
        """生成 AttentionReport 供下游步骤读取（Phase 36 Freeze §2）。

        由 Runtime._tick_step_attention_update 在 step 2 末尾调用。
        下游 Step 4/5/6 只读此报告，不访问 Attention 内部状态。
        """
        from ocos.contracts.attention_abi import (
            AttentionReport, AttentionRecommendation, DecisionDigest,
        )

        # 1. 整理最近决策摘要
        digests: list[DecisionDigest] = []
        if last_decisions_raw:
            for d in last_decisions_raw[-10:]:  # 最近 10 条
                digests.append(DecisionDigest(
                    event_id=getattr(d, "event_id", "?"),
                    decision=d.decision.value if hasattr(d, "decision") else "?",
                    composite=d.score_trace.composite if hasattr(d, "score_trace") else 0.0,
                ))

        # 2. 确定焦点类型
        focus_type = None
        focus_priority = 0.0
        if self._focus is not None:
            focus_type = self._focus.target_type.name if hasattr(self._focus.target_type, 'name') else str(self._focus.target_type)
            focus_priority = self._focus.priority

        # 3. 计算中断计数（过去 60 秒）
        now = time.time()
        self._recent_interrupts = [t for t in self._recent_interrupts if now - t < 60]
        interrupt_count_1m = len(self._recent_interrupts)

        # 4. 推荐引擎（Freeze §2.3）
        rec = AttentionRecommendation()
        fs = self.focus_state.value if isinstance(self.focus_state, FocusState) else str(self.focus_state)

        if self._fatigue > 0.9:
            rec.suppress_planning = True
            rec.suggested_maintenance_depth = 1
        if interrupt_count_1m >= 3:
            rec.suppress_planning = True
        if fs == "FOCUSED" and focus_type == "GOAL":
            rec.prioritize_goals = [self._focus.target_id] if self._focus else []
            rec.ready_for_new_goal = False
        if fs in ("INTERRUPTED", "SUSPENDED", "RE_EVALUATION"):
            rec.suppress_planning = True
        if fs == "IDLE":
            rec.ready_for_new_goal = True
            rec.suggested_maintenance_depth = 5  # 空闲时深度检查

        report = AttentionReport(
            tick_id=tick_id,
            mode=self._mode.name if isinstance(self._mode, AttentionMode) else "IDLE",
            current_focus_id=self._focus.target_id if self._focus else None,
            focus_type=focus_type,
            focus_priority=focus_priority,
            fatigue=self._fatigue,
            interrupt_count_1m=interrupt_count_1m,
            last_decisions=digests,
            recommendation=rec,
        )
        return report

    # ── Tick ────────────────────────────────────────────────────────────

    def tick(self, seconds: float = 1.0) -> None:
        """推进疲劳 + 尝试恢复挂起的焦点（Freeze §2.3）。"""
        super().tick(seconds)

        # 如果当前无焦点，尝试恢复挂起上下文
        if self._focus is None and self._suspended_contexts:
            self.re_evaluate_suspended()

        # 疲劳强制检查
        if self._fatigue > self.FATIGUE_FORCE_IDLE:
            self._transition_focus_state(FocusState.IDLE, "fatigue forced idle")
            if self._focus is not None:
                self._suspend_current_focus()
                self._focus = None
                self._mode = AttentionMode.IDLE
