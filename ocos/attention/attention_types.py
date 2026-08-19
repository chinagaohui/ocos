"""Phase 39.5 Attention ABI — 认知焦点类型定义。

核心区分：
    Attention ≠ Desire — 注意力分配认知资源，不产生欲望
    Focus ≠ Goal — 焦点是当前关注，Goal 是用户意图
    Observation ≠ Obligation — 注意到 ≠ 必须处理

这是在 Phase 35/36 Attention ABI 之上新增的认知选择层。
原有 AttentionDecision / AttentionReport / DecisionType 保持不变。
Phase 39.5 新增：每 Tick 的焦点选择 + 惯性控制 + 审计追踪。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# FocusType — 注意力焦点类型
# ═══════════════════════════════════════════════════════════════════════════

class FocusType(str, Enum):
    """注意力焦点类型。

    只有用户已创建的 Goal 或系统产生的 Event/Maintenance
    能够成为焦点。Attention 自身不产生新 Goal。
    """
    GOAL = "goal"              # 用户创建的 Goal
    EVENT = "event"            # 系统/外部事件
    MAINTENANCE = "maintenance"  # 系统自维护任务


# ═══════════════════════════════════════════════════════════════════════════
# AttentionState — 认知焦点状态矢量
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AttentionState:
    """认知焦点状态 — 每 Tick 的注意力快照。

    这是最小认知状态矢量，保存在 Snapshot 中用于恢复。
    不是完整记忆，而是"恢复意识所需的信息"。

    Constraints (Phase 38 Attention Boundary):
        - 焦点可以是 Goal/Event/Maintenance
        - 禁止通过 Attention 创建 Goal
        - 禁止通过 Attention 修改 UserGoal 的 priority
        - 禁止通过 Attention 修改 Identity.anchor
    """
    focus_id: str | None = None          # 当前焦点 ID (goal_id / event_id / maintenance_id)
    focus_type: FocusType | None = None   # 焦点类型
    focus_priority: float = 0.0           # 综合评分 [0.0, 1.0]
    start_tick: int = 0                   # 本轮焦点开始的 tick
    interrupted_tick: int | None = None   # 被打断的 tick (如果有)
    context_refs: tuple[str, ...] = ()    # 上下文引用 (goal_id, event_id, ...)
    interruption_count: int = 0           # 累计中断次数
    previous_focus_id: str | None = None  # 前一个焦点 (恢复/审计用)
    previous_focus_type: FocusType | None = None
    last_switch_tick: int = 0             # 上次切换焦点的 tick
    total_focus_changes: int = 0          # 累计焦点切换次数

    @property
    def focus_duration(self) -> int:
        """当前焦点已持续的 tick 数。"""
        if self.start_tick == 0:
            return 0
        return (self.interrupted_tick or self.start_tick) - self.start_tick

    @property
    def is_focused(self) -> bool:
        """是否正在关注某个目标。"""
        return self.focus_id is not None

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（用于 Snapshot）。"""
        return {
            "focus_id": self.focus_id,
            "focus_type": self.focus_type.value if self.focus_type else None,
            "focus_priority": self.focus_priority,
            "start_tick": self.start_tick,
            "interrupted_tick": self.interrupted_tick,
            "context_refs": list(self.context_refs),
            "interruption_count": self.interruption_count,
            "previous_focus_id": self.previous_focus_id,
            "previous_focus_type": self.previous_focus_type.value if self.previous_focus_type else None,
            "last_switch_tick": self.last_switch_tick,
            "total_focus_changes": self.total_focus_changes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AttentionState:
        """从 dict 反序列化。"""
        ft = data.get("focus_type")
        pft = data.get("previous_focus_type")
        return cls(
            focus_id=data.get("focus_id"),
            focus_type=FocusType(ft) if ft else None,
            focus_priority=data.get("focus_priority", 0.0),
            start_tick=data.get("start_tick", 0),
            interrupted_tick=data.get("interrupted_tick"),
            context_refs=tuple(data.get("context_refs", [])),
            interruption_count=data.get("interruption_count", 0),
            previous_focus_id=data.get("previous_focus_id"),
            previous_focus_type=FocusType(pft) if pft else None,
            last_switch_tick=data.get("last_switch_tick", 0),
            total_focus_changes=data.get("total_focus_changes", 0),
        )


# ═══════════════════════════════════════════════════════════════════════════
# AttentionCandidate — 可被关注的对象
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AttentionCandidate:
    """注意力候选项 — Attention 只选择，不创建。

    来源: GoalTree (用户创建的 Goal) + EventQueue (系统事件) + MaintenanceQueue (自我维护)。
    """
    candidate_id: str                   # goal_id / event_id / maintenance_id
    candidate_type: FocusType           # GOAL / EVENT / MAINTENANCE
    summary: str = ""                   # 简短描述 (用于追踪)
    # 评分因子
    goal_importance: float = 0.0        # Goal 重要性 [0.0, 1.0] (GOAL 类型有效)
    urgency: float = 0.0                # 紧迫度 [0.0, 1.0]
    context_relevance: float = 0.0      # 上下文相关性 [0.0, 1.0]
    user_preference: float = 0.0        # 用户偏好 [0.0, 1.0]
    # 元数据
    created_tick: int = 0               # 候选项出现的 tick
    age: int = 0                        # 已存在的 tick 数
    source: str = ""                    # "goal_tree" / "event_queue" / "maintenance_queue"


# ═══════════════════════════════════════════════════════════════════════════
# InertiaPolicy — 注意力惯性策略
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class InertiaPolicy:
    """注意力惯性 — 防止认知抖动。

    核心约束：只有 new_score > current_score × switch_threshold 才切换焦点。
    同时要求 minimum_focus_duration ticks 后才能考虑切换。

    设计理由：
        如果没有惯性，tick1→A, tick2→B, tick3→C ...
        系统没有连续思考能力。
    """
    minimum_focus_duration: int = 3     # 最小焦点持续 tick 数
    switch_threshold: float = 1.3       # 切换阈值乘数 (new_score / current_score > 1.3 才切换)
    max_interruptions_per_minute: int = 5  # 每分钟最多中间次数
    cooldown_ticks: int = 5              # 切换后冷却 tick 数

    def should_switch(
        self,
        current_priority: float,
        candidate_priority: float,
        focus_duration: int,
        ticks_since_last_switch: int,
    ) -> tuple[bool, str]:
        """判断是否应该切换焦点。

        Returns:
            (should_switch, reason)
        """
        # 1. 最小持续时间未满
        if focus_duration < self.minimum_focus_duration:
            return False, f"focus_duration={focus_duration} < min={self.minimum_focus_duration}"

        # 2. 冷却期
        if ticks_since_last_switch < self.cooldown_ticks:
            return False, f"cooldown: {ticks_since_last_switch} < {self.cooldown_ticks}"

        # 3. 综合评分未超过阈值
        if current_priority == 0:
            return True, "no current focus"

        ratio = candidate_priority / current_priority
        if ratio < self.switch_threshold:
            return False, f"ratio={ratio:.2f} < threshold={self.switch_threshold}"

        return True, f"ratio={ratio:.2f} >= threshold={self.switch_threshold}"


# ═══════════════════════════════════════════════════════════════════════════
# AttentionTrace — 认知审计追踪
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AttentionTrace:
    """注意力切换的认知审计记录。

    接入 Cognitive Audit Trail:
        ExecutionTrace + MemoryTrace + PermissionTrace + AttentionTrace
    """
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    tick_id: int = 0
    previous_focus_id: str | None = None
    previous_focus_type: str | None = None
    new_focus_id: str | None = None
    new_focus_type: str | None = None
    reason: str = ""                     # "interrupt" / "completion" / "re_evaluation" / ...
    switch_ratio: float = 0.0            # new_score / current_score
    previous_priority: float = 0.0
    new_priority: float = 0.0
    focus_duration: int = 0              # 切换前焦点已持续 tick 数
    candidates_evaluated: int = 0        # 本轮评估的候选项数

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tick_id": self.tick_id,
            "previous_focus_id": self.previous_focus_id,
            "previous_focus_type": self.previous_focus_type,
            "new_focus_id": self.new_focus_id,
            "new_focus_type": self.new_focus_type,
            "reason": self.reason,
            "switch_ratio": self.switch_ratio,
            "previous_priority": self.previous_priority,
            "new_priority": self.new_priority,
            "focus_duration": self.focus_duration,
            "candidates_evaluated": self.candidates_evaluated,
        }


# ═══════════════════════════════════════════════════════════════════════════
# ScoringWeights — 评分权重配置
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AttentionScoringWeights:
    """评分权重 — 用于计算候选 AttentionScore。

    AttentionScore = goal_importance × w_gi + urgency × w_u
                   + context_relevance × w_cr + user_preference × w_up
                   - switch_cost
    """
    goal_importance: float = 0.35
    urgency: float = 0.25
    context_relevance: float = 0.25
    user_preference: float = 0.15
    switch_cost: float = 0.05            # 切换成本 (减项)

    def __post_init__(self) -> None:
        total = self.goal_importance + self.urgency + self.context_relevance + self.user_preference
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


# ═══════════════════════════════════════════════════════════════════════════
# FocusSelectionResult — 焦点选择结果
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FocusSelectionResult:
    """每 Tick 的焦点选择结果。"""
    tick_id: int
    selected_candidate: AttentionCandidate | None = None
    previous_state: AttentionState | None = None
    new_state: AttentionState | None = None
    switched: bool = False
    switch_reason: str = ""
    trace: AttentionTrace | None = None
    candidates_evaluated: int = 0
