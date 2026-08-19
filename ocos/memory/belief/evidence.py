"""Phase 24.4-A — Evidence Binding。

Knowledge + EvidenceSet → BeliefCandidate。

合同:
    - min_evidence = 3
    - min_quality = 0.5
    - 不直接 Belief ← Knowledge，必须经过 Evidence。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ocos.memory.belief.models import Belief, BeliefStatus, Evidence
from ocos.memory.semantic.models import KnowledgeEntry
from ocos.memory.belief.confidence import ConfidenceEngine, ConfidenceConfig


# ── Binding Contract ─────────────────────────────────────────────────────────


@dataclass
class BindingConfig:
    min_evidence: int = 3
    min_quality: float = 0.5


class EvidenceBinding:
    """Knowledge + Evidence → Belief 的绑定引擎。

    集成 ConfidenceEngine 进行置信度计算。
    """

    def __init__(
        self,
        config: BindingConfig | None = None,
        confidence_engine: ConfidenceEngine | None = None,
    ) -> None:
        self._config = config or BindingConfig()
        self._engine = confidence_engine or ConfidenceEngine()

    # ── 公共接口 ─────────────────────────────────────────────────────────

    def bind(
        self,
        knowledge: KnowledgeEntry,
        evidence_set: list[Evidence],
    ) -> Optional[Belief]:
        """尝试将 Knowledge + Evidence 绑定为 Belief。

        Returns: Belief 或 None (证据不足)。
        """
        # 数量检查
        if not self._sufficient_evidence(evidence_set):
            return None

        # 质量检查
        if not self._sufficient_quality(evidence_set):
            return None

        # 使用 ConfidenceEngine 计算置信度
        result = self._engine.evaluate(
            evidence_set,
            counterexamples=knowledge.counterexample_count,
        )

        return Belief.create(
            statement=knowledge.statement,
            source_knowledge_ids=[knowledge.id],
            evidence_ids=[e.id for e in evidence_set],
            confidence=result.confidence,
            uncertainty=result.uncertainty,
            scope={
                "domain": knowledge.scope.domain,
                "preconditions": list(knowledge.scope.preconditions),
                "limitations": list(knowledge.scope.limitations),
            },
        )

    def rebind(
        self,
        belief: Belief,
        knowledge: KnowledgeEntry,
        new_evidence: list[Evidence],
    ) -> Optional[Belief]:
        """新证据出现 → 重新绑定 (可能 weaken/invalidate)。"""
        all_evidence = new_evidence

        if len(all_evidence) < self._config.min_evidence:
            return belief.weaken()

        result = self._engine.evaluate(
            all_evidence,
            counterexamples=knowledge.counterexample_count,
        )

        if result.is_invalidated:
            return belief.invalidate()
        elif result.is_weakened:
            return belief.weaken()

        return None  # 仍需更新，保留旧 Belief

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _sufficient_evidence(self, evidence: list[Evidence]) -> bool:
        return len(evidence) >= self._config.min_evidence

    def _sufficient_quality(self, evidence: list[Evidence]) -> bool:
        if not evidence:
            return False
        avg_quality = sum(e.quality for e in evidence) / len(evidence)
        return avg_quality >= self._config.min_quality
