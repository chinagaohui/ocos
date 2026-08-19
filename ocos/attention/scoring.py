"""Phase 39.5: Scoring Engine — 注意力候选项评分 + 惯性控制。

核心公式:
    AttentionScore = goal_importance × w_gi + urgency × w_u
                   + context_relevance × w_cr + user_preference × w_up
                   - switch_cost

惯性约束:
    只有当 new_score / current_score > switch_threshold 时才切换焦点。
    并且 minimum_focus_duration 必须满足。

设计理由:
    如果每次 tick 都选最高分，系统会 tick1→A, tick2→B, tick3→C
    形成认知抖动，没有连续思考能力。
"""

from __future__ import annotations

from .attention_types import (
    AttentionCandidate,
    AttentionScoringWeights,
    AttentionState,
    AttentionTrace,
    FocusSelectionResult,
    FocusType,
    InertiaPolicy,
)


class AttentionScoringEngine:
    """注意力评分引擎 — 计算候选项综合评分，应用惯性策略选择焦点。"""

    def __init__(
        self,
        weights: AttentionScoringWeights | None = None,
        inertia: InertiaPolicy | None = None,
        enable_trace: bool = True,
    ) -> None:
        self._weights = weights or AttentionScoringWeights()
        self._inertia = inertia or InertiaPolicy()
        self._enable_trace = enable_trace

    # ── 评分 ──

    def score(self, candidate: AttentionCandidate) -> float:
        """计算候选项的综合评分。

        Formula:
            score = goal_importance × w_gi
                  + urgency × w_u
                  + context_relevance × w_cr
                  + user_preference × w_up
                  - switch_cost
        """
        w = self._weights
        base = (
            candidate.goal_importance * w.goal_importance
            + candidate.urgency * w.urgency
            + candidate.context_relevance * w.context_relevance
            + candidate.user_preference * w.user_preference
        )
        # switch_cost is only applied during selection, not per-candidate scoring
        return min(max(base, 0.0), 1.0)

    def score_all(self, candidates: list[AttentionCandidate]) -> list[tuple[AttentionCandidate, float]]:
        """对所有候选项评分，返回 (candidate, score) 列表。"""
        return [(c, self.score(c)) for c in candidates]

    # ── 选择 ──

    def select(
        self,
        candidates: list[AttentionCandidate],
        current_state: AttentionState | None,
        current_tick: int,
    ) -> FocusSelectionResult:
        """从候选中选择焦点。

        1. 对所有候选评分
        2. 选出最高分
        3. 如果当前已有焦点，检查惯性策略
        4. 如果切换，记录 AttentionTrace

        Returns:
            FocusSelectionResult with selected/none + new state + trace
        """
        if not candidates:
            return FocusSelectionResult(
                tick_id=current_tick,
                selected_candidate=None,
                previous_state=current_state,
                new_state=current_state,
                switched=False,
                switch_reason="no candidates",
                trace=None,
                candidates_evaluated=0,
            )

        # Score all
        scored = self.score_all(candidates)
        scored.sort(key=lambda x: x[1], reverse=True)
        best_candidate, best_score = scored[0]

        # No current focus — accept best (no cooldown for initial)
        if current_state is None or not current_state.is_focused:
            new_state = AttentionState(
                focus_id=best_candidate.candidate_id,
                focus_type=best_candidate.candidate_type,
                focus_priority=best_score,
                start_tick=current_tick,
                last_switch_tick=0,  # 初始选择不计入切换冷却
                total_focus_changes=(current_state.total_focus_changes + 1 if current_state else 1),
            )
            trace = self._build_trace(
                current_tick=current_tick,
                previous_state=current_state,
                new_state=new_state,
                reason="initial_focus",
                switch_ratio=0.0,
                candidates_evaluated=len(candidates),
            )
            return FocusSelectionResult(
                tick_id=current_tick,
                selected_candidate=best_candidate,
                previous_state=current_state,
                new_state=new_state,
                switched=True,
                switch_reason="initial_focus",
                trace=trace,
                candidates_evaluated=len(candidates),
            )

        # Same focus — keep it
        if best_candidate.candidate_id == current_state.focus_id:
            # Update priority but keep focus
            new_state = AttentionState(
                focus_id=current_state.focus_id,
                focus_type=current_state.focus_type,
                focus_priority=best_score,
                start_tick=current_state.start_tick,
                interrupted_tick=current_state.interrupted_tick,
                context_refs=current_state.context_refs,
                interruption_count=current_state.interruption_count,
                previous_focus_id=current_state.previous_focus_id,
                previous_focus_type=current_state.previous_focus_type,
                last_switch_tick=current_state.last_switch_tick,
                total_focus_changes=current_state.total_focus_changes,
            )
            return FocusSelectionResult(
                tick_id=current_tick,
                selected_candidate=best_candidate,
                previous_state=current_state,
                new_state=new_state,
                switched=False,
                switch_reason="same focus",
                trace=None,
                candidates_evaluated=len(candidates),
            )

        # Different focus — check inertia
        focus_duration = current_tick - current_state.start_tick
        ticks_since_switch = current_tick - current_state.last_switch_tick
        should_switch, inertia_reason = self._inertia.should_switch(
            current_priority=current_state.focus_priority,
            candidate_priority=best_score,
            focus_duration=focus_duration,
            ticks_since_last_switch=ticks_since_switch,
        )

        if not should_switch:
            # Keep current focus
            return FocusSelectionResult(
                tick_id=current_tick,
                selected_candidate=None,
                previous_state=current_state,
                new_state=current_state,
                switched=False,
                switch_reason=inertia_reason,
                trace=None,
                candidates_evaluated=len(candidates),
            )

        # Switch focus
        switch_ratio = best_score / max(current_state.focus_priority, 0.001)
        previous_focus_id = current_state.focus_id
        previous_focus_type = current_state.focus_type

        new_state = AttentionState(
            focus_id=best_candidate.candidate_id,
            focus_type=best_candidate.candidate_type,
            focus_priority=best_score,
            start_tick=current_tick,
            context_refs=current_state.context_refs,
            interruption_count=current_state.interruption_count + 1,
            previous_focus_id=previous_focus_id,
            previous_focus_type=previous_focus_type,
            last_switch_tick=current_tick,
            total_focus_changes=current_state.total_focus_changes + 1,
        )
        trace = self._build_trace(
            current_tick=current_tick,
            previous_state=current_state,
            new_state=new_state,
            reason="re_evaluation" if best_candidate.candidate_type == current_state.focus_type else "interrupt",
            switch_ratio=switch_ratio,
            candidates_evaluated=len(candidates),
        )
        return FocusSelectionResult(
            tick_id=current_tick,
            selected_candidate=best_candidate,
            previous_state=current_state,
            new_state=new_state,
            switched=True,
            switch_reason=inertia_reason,
            trace=trace,
            candidates_evaluated=len(candidates),
        )

    # ── helpers ──

    def _build_trace(
        self,
        current_tick: int,
        previous_state: AttentionState | None,
        new_state: AttentionState,
        reason: str,
        switch_ratio: float,
        candidates_evaluated: int,
    ) -> AttentionTrace | None:
        if not self._enable_trace:
            return None
        return AttentionTrace(
            tick_id=current_tick,
            previous_focus_id=previous_state.focus_id if previous_state else None,
            previous_focus_type=previous_state.focus_type.value if previous_state and previous_state.focus_type else None,
            new_focus_id=new_state.focus_id,
            new_focus_type=new_state.focus_type.value if new_state.focus_type else None,
            reason=reason,
            switch_ratio=switch_ratio,
            previous_priority=previous_state.focus_priority if previous_state else 0.0,
            new_priority=new_state.focus_priority,
            focus_duration=current_tick - (previous_state.start_tick if previous_state else 0),
            candidates_evaluated=candidates_evaluated,
        )
