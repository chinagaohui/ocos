"""Phase T: CrossModalFusion — 跨模态融合。

整合多个模态的感知结果，产生更可靠的综合判断：
- 加权投票融合
- 冲突检测与消解
- 置信度传播
- 时序对齐
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FusionStrategy(Enum):
    """融合策略。"""
    WEIGHTED_VOTE = auto()     # 加权投票
    MAX_CONFIDENCE = auto()    # 取最高置信度
    CONSENSUS = auto()         # 一致性协议（多数票）
    SEQUENTIAL = auto()        # 顺序融合（后覆盖前）


@dataclass
class ModalObservation:
    """单模态观察。"""
    modality: str              # 模态名称
    content: Any
    confidence: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.7


@dataclass
class FusedObservation:
    """融合后的观察。"""
    fused_content: Any
    fused_confidence: float
    contributing_modalities: list[str]
    conflicts_detected: bool = False
    conflict_count: int = 0
    conflict_resolution: str = ""
    timestamp: float = field(default_factory=time.time)


class CrossModalFusion:
    """跨模态融合器。"""

    def __init__(
        self,
        strategy: FusionStrategy = FusionStrategy.WEIGHTED_VOTE,
        default_weights: Optional[dict[str, float]] = None,
    ) -> None:
        self._strategy = strategy
        self._weights = default_weights or {}
        self._history: list[FusedObservation] = []
        self._max_history = 100

    def set_weight(self, modality: str, weight: float) -> None:
        """设置模态权重。"""
        self._weights[modality] = max(0.0, min(1.0, weight))

    def fuse(
        self,
        observations: list[ModalObservation],
    ) -> FusedObservation:
        """融合多个模态的观察。"""
        if not observations:
            return FusedObservation(
                fused_content=None,
                fused_confidence=0.0,
                contributing_modalities=[],
            )

        if len(observations) == 1:
            obs = observations[0]
            return FusedObservation(
                fused_content=obs.content,
                fused_confidence=obs.confidence,
                contributing_modalities=[obs.modality],
            )

        # 检测冲突
        conflicts = self._detect_conflicts(observations)

        # 按策略融合
        if self._strategy == FusionStrategy.WEIGHTED_VOTE:
            result = self._weighted_vote(observations)
        elif self._strategy == FusionStrategy.MAX_CONFIDENCE:
            result = self._max_confidence(observations)
        elif self._strategy == FusionStrategy.CONSENSUS:
            result = self._consensus(observations)
        elif self._strategy == FusionStrategy.SEQUENTIAL:
            result = self._sequential(observations)
        else:
            result = self._weighted_vote(observations)

        result.conflicts_detected = len(conflicts) > 0
        result.conflict_count = len(conflicts)
        if conflicts:
            result.conflict_resolution = f"{len(conflicts)} conflict(s) detected and resolved"

        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        return result

    def _weighted_vote(self, observations: list[ModalObservation]) -> FusedObservation:
        """加权投票融合。"""
        weighted_sum = 0.0
        weight_total = 0.0
        content_values: dict[str, int] = defaultdict(int)

        for obs in observations:
            weight = self._weights.get(obs.modality, 0.5)
            weighted_sum += obs.confidence * weight
            weight_total += weight
            # 简单内容统计
            content_key = str(obs.content)[:50] if obs.content else ""
            content_values[content_key] += 1

        if weight_total > 0:
            avg_confidence = weighted_sum / weight_total
        else:
            avg_confidence = sum(o.confidence for o in observations) / len(observations)

        # 选择最常出现的内容
        most_common = max(content_values, key=content_values.get) if content_values else ""

        return FusedObservation(
            fused_content=most_common if most_common else observations[0].content,
            fused_confidence=avg_confidence,
            contributing_modalities=[o.modality for o in observations],
        )

    def _max_confidence(self, observations: list[ModalObservation]) -> FusedObservation:
        """取最高置信度。"""
        best = max(observations, key=lambda o: o.confidence)
        return FusedObservation(
            fused_content=best.content,
            fused_confidence=best.confidence,
            contributing_modalities=[o.modality for o in observations],
        )

    def _consensus(self, observations: list[ModalObservation]) -> FusedObservation:
        """一致性协议。"""
        reliable = [o for o in observations if o.is_reliable]
        if not reliable:
            return FusedObservation(
                fused_content=observations[0].content if observations else None,
                fused_confidence=0.3,
                contributing_modalities=[o.modality for o in observations],
            )

        # 可靠观察的一致性
        contents = [str(o.content)[:50] for o in reliable]
        unique = set(contents)
        if len(unique) == 1:
            # 完全一致
            avg_conf = sum(o.confidence for o in reliable) / len(reliable)
            return FusedObservation(
                fused_content=reliable[0].content,
                fused_confidence=avg_conf,
                contributing_modalities=[o.modality for o in observations],
            )

        # 不一致，降低置信度
        return FusedObservation(
            fused_content=reliable[0].content,
            fused_confidence=min(o.confidence for o in reliable) * 0.7,
            contributing_modalities=[o.modality for o in observations],
        )

    def _sequential(self, observations: list[ModalObservation]) -> FusedObservation:
        """顺序融合（后覆盖前）。"""
        last = observations[-1]
        return FusedObservation(
            fused_content=last.content,
            fused_confidence=last.confidence,
            contributing_modalities=[o.modality for o in observations],
        )

    def _detect_conflicts(
        self,
        observations: list[ModalObservation],
    ) -> list[tuple[str, str]]:
        """检测模态间的冲突。"""
        conflicts = []
        for i in range(len(observations)):
            for j in range(i + 1, len(observations)):
                o1, o2 = observations[i], observations[j]
                # 高置信度但不一致视为冲突
                if (o1.is_reliable and o2.is_reliable and
                        str(o1.content)[:50] != str(o2.content)[:50]):
                    conflicts.append((o1.modality, o2.modality))
        return conflicts

    def get_stats(self) -> dict[str, Any]:
        """获取融合统计。"""
        total = len(self._history)
        conflicts = sum(1 for h in self._history if h.conflicts_detected)
        return {
            "total_fusions": total,
            "conflicts_detected": conflicts,
            "conflict_rate": conflicts / total if total > 0 else 0.0,
            "avg_confidence": (
                sum(h.fused_confidence for h in self._history) / total
                if total > 0 else 0.0
            ),
        }
