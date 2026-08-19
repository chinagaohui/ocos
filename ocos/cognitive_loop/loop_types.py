"""Phase 46: Cognitive Operating Loop Integration — 认知运行循环集成。

Phase 46 不是制造新器官，而是让已有器官形成统一的生命循环。

完整闭环:
    Perception → Attention → Context → Decision → Action → Learning → Memory → (next cycle)

核心约束 (CL46 boundaries):
    CL46-01: Loop ≠ Autonomy       — 循环是协同机制，不是自我设定目标
    CL46-02: Health ≠ Self-Rewrite — 健康监控可以发现问题，不能重新定义自身
    CL46-03: Perception ≠ Truth    — 感知是输入信号，不是客观事实
    CL46-04: Learning ≠ Drift      — 学习有边界，不漂移 Identity/Constitution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 循环阶段
# ═══════════════════════════════════════════════════════════════════════════════


class LoopPhase(Enum):
    """认知循环的各个阶段。"""
    IDLE = "idle"
    PERCEIVING = "perceiving"       # 感知输入
    ATTENDING = "attending"         # 注意力分配
    SYNCING_CONTEXT = "syncing"    # 上下文同步
    DECIDING = "deciding"           # 形成判断
    ACTING = "acting"               # 选择+执行能力
    LEARNING = "learning"           # 结果理解+记忆固化
    HEALTH_CHECK = "health_check"   # 健康自检


class TickOutcome(Enum):
    """一次循环 tick 的结果。"""
    OK = "ok"
    NO_INPUT = "no_input"            # 无输入，空转
    DECISION_PENDING = "decision_pending"
    ACTION_TAKEN = "action_taken"
    LEARNING_RECORDED = "learning_recorded"
    HEALTH_ALERT = "health_alert"
    ERROR_RECOVERED = "error_recovered"


# ═══════════════════════════════════════════════════════════════════════════════
# 循环上下文
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LoopContext:
    """一次循环 tick 的完整上下文。"""
    tick_id: int = 0
    phase: LoopPhase = LoopPhase.IDLE

    # 感知
    perception_input: str = ""         # 本 tick 的原始输入

    # 注意力
    attention_focus: str = ""          # 当前注意力焦点
    attention_weight: float = 0.5      # 注意力权重 [0, 1]

    # 上下文
    self_snapshot: str = ""            # Self Model 快照
    active_wisdom: list[str] = field(default_factory=list)
    world_state: str = ""              # World Model 当前状态
    active_goals: list[str] = field(default_factory=list)

    # 决策
    decision_proposal: str = ""
    decision_approved: bool = False

    # 行动
    selected_capability: str = ""
    action_result: str = ""

    # 学习
    learning_outcome: str = ""
    consolidation_tick: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 健康信号
# ═══════════════════════════════════════════════════════════════════════════════


class HealthSignal(Enum):
    """认知健康信号。"""
    NORMAL = "normal"
    WARNING = "warning"
    ALERT = "alert"
    CRITICAL = "critical"


@dataclass
class ModuleHealth:
    """单个模块的健康状态。"""
    module_name: str
    signal: HealthSignal = HealthSignal.NORMAL
    metric_value: float = 1.0        # [0, 1] 健康度
    anomaly_description: str = ""


@dataclass
class CognitiveHealthReport:
    """全系统认知健康报告。"""
    tick_id: int = 0
    overall: HealthSignal = HealthSignal.NORMAL
    modules: list[ModuleHealth] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    repair_suggestions: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        return self.overall == HealthSignal.NORMAL

    @property
    def needs_attention(self) -> bool:
        return self.overall in (HealthSignal.ALERT, HealthSignal.CRITICAL)


__all__ = [
    "LoopPhase",
    "TickOutcome",
    "LoopContext",
    "HealthSignal",
    "ModuleHealth",
    "CognitiveHealthReport",
]
