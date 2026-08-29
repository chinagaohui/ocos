"""Phase 39.2: TickContext — 一次心跳的不可变数据容器。

TickContext 是 Tick Pipeline 各阶段之间的数据传输载体。
每个 Stage 读入 ctx，返回新的 ctx（不可变流水线）。

约束 (Phase 38 Governance Freeze):
    - TickContext 不可变 (frozen dataclass)
    - tick 过程中不允许随意修改关键字段
    - 为 Tick Replay 保留完整状态快照
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Sequence


@dataclass(frozen=True)
class TickContext:
    """一次心跳的完整上下文。

    每个 Pipeline Stage 读取上下文、返回新的 TickContext。
    不可变设计保证 replay 一致性。
    """

    tick_id: int
    runtime_state: str  # RuntimeState value

    # ── Stage 输出 ──
    events: tuple[Any, ...] = ()
    attention_snapshot: Any | None = None
    memory_changes: tuple[Any, ...] = ()
    goal_updates: tuple[Any, ...] = ()
    execution_candidates: tuple[Any, ...] = ()
    execution_results: tuple[Any, ...] = ()
    learning_signals: tuple[Any, ...] = ()
    checkpoint_decision: bool = False

    # ── Timing ──
    started_at: float = 0.0
    completed_at: float = 0.0

    # ── Metadata ──
    stage_traces: tuple[str, ...] = ()  # 记录经过的 stage 名称

    def with_updates(self, **kwargs) -> TickContext:
        """创建更新后的 TickContext 副本（保留不可变性）。

        用法: ctx.with_updates(events=new_events, attention_snapshot=snap)
        """
        return replace(self, **kwargs)

    def with_stage_trace(self, stage_name: str) -> TickContext:
        """追加 stage 轨迹。"""
        return replace(self, stage_traces=self.stage_traces + (stage_name,))

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 Tick Replay / checkpoint）。"""
        return {
            "tick_id": self.tick_id,
            "runtime_state": self.runtime_state,
            "events_count": len(self.events),
            "attention_snapshot": str(self.attention_snapshot) if self.attention_snapshot else None,
            "memory_changes_count": len(self.memory_changes),
            "goal_updates_count": len(self.goal_updates),
            "execution_candidates_count": len(self.execution_candidates),
            "execution_results_count": len(self.execution_results),
            "learning_signals_count": len(self.learning_signals),
            "checkpoint_decision": self.checkpoint_decision,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stage_traces": list(self.stage_traces),
        }


def create_tick_context(
    tick_id: int,
    runtime_state: str,
    started_at: float | None = None,
) -> TickContext:
    """创建初始 TickContext（Pipeline 入口）。"""
    import time
    return TickContext(
        tick_id=tick_id,
        runtime_state=runtime_state,
        started_at=started_at or time.time(),
    )
