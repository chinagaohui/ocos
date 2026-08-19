"""Phase 35: Attention ABI — 注意力认知控制协议。
Phase 36: Executive Attention Binding — 扩展 AttentionReport 为下游绑定信号。

定义 Attention 系统的对外契约。所有层（A/B/C）和所有 Tick 步骤只通过此 ABI
交换数据，不直接跨层访问内部状态。

ABI 核心类型:
  AttentionDecision       — 注意力引擎的决策输出
  DecisionType            — 决策类型枚举
  AttentionScoreTrace     — 评分溯源（可审计）
  FocusChange             — 焦点变更描述
  WMAllocation            — WorkingMemory 分配指令
  AttentionReport         — Tick 结束时的注意力状态报告（含 Phase 36 扩展）
  AttentionRecommendation  — Phase 36: Attention 对下游的推荐
  DecisionDigest          — Phase 36: 决策轻量摘要
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionType(Enum):
    """注意力决策类型（Freeze §1.2）。

    ACCEPTED:  进入 FOCUSED，替换或竞争当前焦点
    QUEUED:    进入关注队列，延迟处理
    DEFERRED:  不处理但记录（有存档价值，优先级很低）
    DISMISSED: 丢弃（噪音/重复/无关联 / 违反主权原则）
    """
    ACCEPTED = "ACCEPTED"
    QUEUED = "QUEUED"
    DEFERRED = "DEFERRED"
    DISMISSED = "DISMISSED"


@dataclass(frozen=True)
class AttentionScoreTrace:
    """评分溯源 — 每个决策带完整评分链（可审计）。（Freeze §1.3.4）

    不允许通过字符串拼接伪造；所有字段必须来自 AttentionScoringEngine 的输出。
    """
    novelty: float = 0.0          # 新颖性 [0.0, 1.0]
    goal_relevance: float = 0.0   # 目标相关性 [0.0, 1.0]
    urgency: float = 0.0          # 紧迫度 [0.0, 1.0]
    confidence: float = 0.0       # 信源可信度 [0.0, 1.0] (§4.5)
    time_decay: float = 0.0       # 时间衰减因子
    composite: float = 0.0        # 加权综合分 (§4.1)
    weights_used: dict[str, float] = field(default_factory=dict)
    source: str = ""              # 信源标识 ("user_input" / "event:file_change" / ...)


@dataclass(frozen=True)
class FocusChange:
    """焦点变更描述（Freeze §2.2 状态机）。"""
    old_focus_id: str | None = None
    old_target_type: str | None = None
    new_focus_id: str | None = None
    new_target_type: str | None = None
    reason: str = ""              # "interrupt" / "completion" / "re_evaluation" / ...
    suspend_context: bool = False  # 旧焦点是否保存到 SUSPENDED_CONTEXT


@dataclass(frozen=True)
class WMAllocation:
    """WM 分配指令 — AttentionController 告诉 WM 如何存放此事件（Freeze §5）。"""
    event_id: str = ""
    slot_type: str = ""           # "current_focus" / "environmental_scan" / "suspended_context"
    attention_weight: float = 0.0 # 用于驱逐排序
    ttl_seconds: int | None = None


@dataclass(frozen=True)
class AttentionDecision:
    """注意力引擎的单条决策（Freeze §1.2 Output）。

    这是 Attention 系统的唯一输出格式。所有下游（WM、Planning、Execution）
    只消费这个结构，不直接访问 AttentionController 内部状态。
    """
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_id: str = ""
    decision: DecisionType = DecisionType.DISMISSED
    score_trace: AttentionScoreTrace = field(default_factory=AttentionScoreTrace)
    focus_change: FocusChange | None = None
    wm_allocation: WMAllocation | None = None
    reason: str = ""
    tick_id: str = ""

    @property
    def is_accepted(self) -> bool:
        return self.decision == DecisionType.ACCEPTED

    @property
    def is_dismissed(self) -> bool:
        return self.decision == DecisionType.DISMISSED

    @property
    def causes_focus_change(self) -> bool:
        return self.focus_change is not None


# ── Phase 36: Executive Attention Binding types ──────────────────────────────

@dataclass
class DecisionDigest:
    """AttentionDecision 的轻量摘要。Phase 36 — 供 AttentionReport 批量引用。"""
    event_id: str = ""
    decision: str = ""   # ACCEPTED|QUEUED|DEFERRED|DISMISSED
    composite: float = 0.0


@dataclass
class AttentionRecommendation:
    """Attention 对下游的推荐指令（纯建议，不绑定）。

    Phase 36: Goal Maintenance / Planning Trigger / Execution Check 各自有权忽略。
    """

    suppress_planning: bool = False
    prioritize_goals: list[str] = field(default_factory=list)
    deprioritize_goals: list[str] = field(default_factory=list)
    ready_for_new_goal: bool = True
    suggested_maintenance_depth: int = 3

    @property
    def is_idle(self) -> bool:
        """Attention 是否处于空闲、可接受新任务的状态。"""
        return self.ready_for_new_goal and not self.suppress_planning


# ── Phase 36 execution signal constants ──────────────────────────────────────

ALLOW_PLANNING = "ALLOW_PLANNING"
DEFER_PLANNING = "DEFER_PLANNING"
EXECUTION_ALLOW = "EXECUTION_ALLOW"
EXECUTION_BLOCK_ATTENTION = "EXECUTION_BLOCK_ATTENTION"


# ── Phase 35 (with Phase 36 extensions) ──────────────────────────────────────

@dataclass
class AttentionReport:
    """Tick 结束时的注意力状态报告。

    不同于 AttentionDecision（单事件决策），这是整个 Tick 的注意力摘要。
    Phase 36 扩展：新增 focus_type / focus_priority / last_decisions / recommendation。
    """
    tick_id: str = ""
    mode: str = "IDLE"
    current_focus_id: str | None = None
    decisions_made: int = 0
    accepted_count: int = 0
    queued_count: int = 0
    deferred_count: int = 0
    dismissed_count: int = 0
    fatigue: float = 0.0
    queue_depth: int = 0
    interrupt_occurred: bool = False
    sovereignty_violations: int = 0
    wm_slots_used: dict[str, int] = field(default_factory=dict)
    events_scored: int = 0
    scoring_time_ms: float = 0.0
    decision_time_ms: float = 0.0
    total_attention_budget_ms: float = 0.0
    # ── Phase 36 扩展 ──
    focus_type: str | None = None         # EVENT|GOAL|TASK|None
    focus_priority: float = 0.0           # 当前焦点复合优先级
    interrupt_count_1m: int = 0           # 过去 1 分钟中断次数
    last_decisions: list[DecisionDigest] = field(default_factory=list)
    recommendation: AttentionRecommendation = field(default_factory=AttentionRecommendation)


# ── Sovereignty 检查常量 ──────────────────────────────────────────────────

# 任何决策的原因字段不得包含这些字符串（主权原则 §11）
FORBIDDEN_DECISION_REASONS: set[str] = {
    "create goal",
    "create_goal",
    "modify goal",
    "modify_goal",
    "change priority",
    "change_priority",
    "call agent",
    "execute task",
    "execute_task",
}
