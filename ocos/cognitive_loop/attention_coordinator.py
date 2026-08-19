"""Phase 46: AttentionCoordinator — 注意力协调器。

协调注意力在感知事件、活跃目标、上下文之间的分配。

不创建 Goal (Phase 39 边界)，只调整焦点和权重。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_loop.perception_bridge import PerceptionEvent
from ocos.cognitive_loop.loop_types import LoopContext


@dataclass
class AttentionFocus:
    """注意力焦点描述。"""
    target: str = ""            # 焦点对象
    weight: float = 0.0          # 权重 [0, 1]
    source: str = ""             # 来源: perception/goal/memory


@dataclass
class AttentionCoordinator:
    """注意力协调器。

    管理注意力分配:
        - 感知事件 → 焦点
        - 目标优先级 → 焦点
        - 记忆提醒 → 焦点
    """

    _current_focus: str = ""
    _weight: float = 0.5
    _history: list[AttentionFocus] = field(default_factory=list)

    def evaluate(
        self,
        events: list[PerceptionEvent],
        goals: list[str],
        context: LoopContext | None = None,
    ) -> AttentionFocus:
        """评估当前 tick 的注意力分配。

        优先级:
            1. 感知事件 (有输入时最高)
            2. 活跃目标
            3. 默认状态
        """
        # 1. 感知事件优先
        unprocessed = [e for e in events if not e.processed]
        if unprocessed:
            latest = unprocessed[-1]
            focus = AttentionFocus(
                target=f"event:{latest.event_id}",
                weight=0.9,
                source="perception",
            )
            self._apply(focus)
            return focus

        # 2. 活跃目标
        if goals:
            focus = AttentionFocus(
                target=f"goal:{goals[0]}",
                weight=0.7,
                source="goal",
            )
            self._apply(focus)
            return focus

        # 3. 默认
        focus = AttentionFocus(target="idle", weight=0.3, source="default")
        self._apply(focus)
        return focus

    def _apply(self, focus: AttentionFocus) -> None:
        self._current_focus = focus.target
        self._weight = focus.weight
        self._history.append(focus)
        # 保持最近 100 条
        if len(self._history) > 100:
            self._history = self._history[-50:]

    @property
    def current(self) -> str:
        return self._current_focus

    @property
    def weight(self) -> float:
        return self._weight

    @property
    def recent_focus_history(self) -> list[AttentionFocus]:
        return self._history[-20:]


__all__ = ["AttentionFocus", "AttentionCoordinator"]
