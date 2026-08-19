"""Phase 24.2-B — Gate Integration。

SignificanceEvaluator + EpisodeStore 的桥接层。

链路:
    ExperienceCandidate
        → SignificanceEvaluator.evaluate()
        → GateDecision.PASS
        → episode_from_decision()
        → EpisodeStore.save()
"""

from __future__ import annotations

from typing import Optional

from ocos.memory.experience.models import ExperienceCandidate
from ocos.memory.significance.models import GateDecision, GateVerdict
from ocos.memory.significance.evaluator import SignificanceEvaluator
from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.episode.store import EpisodeStore


def episode_from_decision(
    candidate: ExperienceCandidate,
    decision: GateDecision,
    tags: Optional[list[str]] = None,
) -> Episode:
    """从 ExperienceCandidate + GateDecision 构建 Episode。

    只能在 decision.verdict == PASS 时调用。
    """
    if decision.verdict != GateVerdict.PASS:
        raise ValueError(
            f"Cannot create Episode from FAIL decision for {candidate.id}"
        )

    bundle = candidate.trace_bundle
    outcome = bundle.outcome or {}

    # 构建 evaluation_trace
    score = decision.score
    trace = {
        "experience_id": candidate.id,
        "dimensions": {
            "goal_impact": score.goal_impact.raw_score,
            "prediction_error": score.prediction_error.raw_score,
            "knowledge_change": score.knowledge_change.raw_score,
            "future_relevance": score.future_relevance.raw_score,
        },
        "weights": {
            "goal_impact": score.goal_impact.weight,
            "prediction_error": score.prediction_error.weight,
            "knowledge_change": score.knowledge_change.weight,
            "future_relevance": score.future_relevance.weight,
        },
        "weighted_total": score.weighted_total,
        "threshold": score.threshold,
        "verdict": decision.verdict.value,
    }

    return Episode.from_candidate(
        experience_id=candidate.id,
        context={
            "observation": bundle.observation,
            "environment": bundle.environment_state,
            **(candidate.context or {}),
        },
        goal=(
            bundle.goal_context.get("goal_id")
            if bundle.goal_context
            else None
        ),
        decision=bundle.decision_trace_id,
        action=str(bundle.action_result),
        outcome=outcome,
        condition=str(bundle.environment_state or {}),
        significance_score=score.weighted_total,
        evaluation_trace=trace,
        source=candidate.source.value,
        tags=tags,
    )


class EpisodeGate:
    """SignificanceEvaluator → EpisodeStore 集成门。

    一条链完成: 评估 → 决策 → 入库。
    """

    def __init__(self, store: EpisodeStore, evaluator: SignificanceEvaluator | None = None) -> None:
        self._store = store
        self._evaluator = evaluator or SignificanceEvaluator()

    def process(
        self,
        candidate: ExperienceCandidate,
        *,
        active_goals: Optional[list[str]] = None,
        expected_outcome: Optional[dict] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[Episode]:
        """完整链路: 评估 → 如果 PASS → 创建 Episode 并入库。

        Returns:
            Episode if PASS, None if FAIL.
        """
        decision = self._evaluator.evaluate(
            candidate,
            active_goals=active_goals,
            expected_outcome=expected_outcome,
        )

        if decision.verdict != GateVerdict.PASS:
            return None

        episode = episode_from_decision(candidate, decision, tags=tags)
        self._store.save(episode)
        return episode

    def process_all(
        self,
        candidates: list[ExperienceCandidate],
        **kwargs,
    ) -> list[Episode]:
        """批量处理。只返回 PASS 的 Episode。"""
        episodes: list[Episode] = []
        for candidate in candidates:
            episode = self.process(candidate, **kwargs)
            if episode is not None:
                episodes.append(episode)
        return episodes
