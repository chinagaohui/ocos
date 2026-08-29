"""Stage ②: Attention — Phase 39.5 认知焦点选择。

每 Tick:
    1. 从 CandidateCollector 获取候选项
    2. 通过 ScoringEngine 评分 + 惯性控制
    3. 选择焦点或保持当前焦点
    4. 输出 FocusSelectionResult 到 TickContext

约束:
    - Stage 自身无状态 (AttentionState 存储在 RuntimeKernel)
    - 只选择焦点，不创建 Goal
    - 惯性策略防止认知抖动
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext

if TYPE_CHECKING:
    from ocos.attention.attention_types import AttentionState, FocusSelectionResult
    from ocos.attention.candidate_selector import CandidateCollector
    from ocos.attention.scoring import AttentionScoringEngine


class AttentionStage:
    """注意力阶段 — 认知焦点选择。

    依赖 (由 RuntimeKernel 注入):
        - scoring_engine: AttentionScoringEngine
        - candidate_collector: CandidateCollector (每 tick 重新填充)
        - attention_state: 当前认知状态 (由 RuntimeKernel 持有)
    """

    name = "ATTENTION"

    def __init__(
        self,
        scoring_engine: AttentionScoringEngine | None = None,
        candidate_collector: CandidateCollector | None = None,
    ) -> None:
        self._scoring = scoring_engine
        self._collector = candidate_collector

    def execute(self, context: TickContext) -> TickContext:
        """执行注意力选择。

        Returns:
            TickContext with attention_snapshot = FocusSelectionResult
        """
        if self._scoring is None or self._collector is None:
            # Stub mode: no attention configured
            return context.with_updates(
                attention_snapshot=None
            ).with_stage_trace(self.name)

        candidates = self._collector.candidates()
        current_state = getattr(self, "_current_state", None)

        result = self._scoring.select(
            candidates=candidates,
            current_state=current_state,
            current_tick=context.tick_id,
        )

        # Update state for next tick
        self._current_state = result.new_state

        return context.with_updates(
            attention_snapshot=result,
        ).with_stage_trace(self.name)

    def get_current_state(self) -> AttentionState | None:
        """获取当前注意力状态（供 RuntimeKernel / RecoveryManager 读取）。"""
        return getattr(self, "_current_state", None)

    def set_current_state(self, state: AttentionState | None) -> None:
        """设置注意力状态（恢复时使用）。"""
        self._current_state = state

    def clear_candidates(self) -> None:
        """清空候选项（每 tick 结束时调用）。"""
        if self._collector is not None:
            self._collector.clear()
