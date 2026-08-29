"""Phase 24-D — AttentionDrivenRetrieval: 注意力焦点→检索 Long-Term Memory。

Freeze §5: Long-Term → Working → Current Cognitive Context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AttentionSignal:
    """注意力信号 — 决定检索方向。"""
    keywords: list[str] = field(default_factory=list)
    recency_weight: float = 0.3
    importance_weight: float = 0.5
    similarity_threshold: float = 0.3
    max_results: int = 10


@dataclass
class RetrievedItem:
    content: str
    score: float
    source: str  # episodic / long_term
    metadata: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RetrievedItem):
            return NotImplemented
        return (
            self.content == other.content
            and self.score == other.score
            and self.source == other.source
        )

    def __hash__(self) -> int:
        return hash((self.content, self.score, self.source))


@dataclass
class AttentionDrivenRetrieval:
    """注意力驱动的记忆检索。

    用法:
        adr = AttentionDrivenRetrieval(memory_hub)
        items = adr.retrieve(AttentionSignal(keywords=["project", "task"]))
    """

    memory_hub: Any = None  # MemoryHub instance for querying
    cache: dict[str, list[RetrievedItem]] = field(default_factory=dict)

    def retrieve(self, signal: AttentionSignal) -> list[RetrievedItem]:
        """根据注意力信号检索相关记忆。"""
        results: list[RetrievedItem] = []
        cache_key = ",".join(sorted(signal.keywords))
        if cache_key in self.cache:
            return self.cache[cache_key]

        if self.memory_hub is None:
            logger.debug("AttentionRetrieval: no memory_hub, returning empty")
            return results

        # 从长期记忆检索
        try:
            long_term = self.memory_hub.get_long_term() or []
            for item in long_term:
                score = self._score(item, signal)
                if score >= signal.similarity_threshold:
                    results.append(RetrievedItem(
                        content=str(item)[:200],
                        score=score,
                        source="long_term",
                    ))
        except Exception as _lt_e:
            # BR-04 B批（2026-08-25）：长期记忆检索降级留痕。
            logger.warning("long-term retrieval failed: %s", _lt_e)

        # 从情景记忆检索
        try:
            episodic = self.memory_hub.get_episodic() or []
            for item in episodic:
                score = self._score(item, signal) * signal.recency_weight
                if score >= signal.similarity_threshold:
                    results.append(RetrievedItem(
                        content=str(item)[:200],
                        score=score,
                        source="episodic",
                    ))
        except Exception as _ep_e:
            # BR-04 B批（2026-08-25）：情景记忆检索降级留痕。
            logger.warning("episodic retrieval failed: %s", _ep_e)

        # 按分数排序 + 截断
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:signal.max_results]
        self.cache[cache_key] = results
        return results

    def _score(self, item: Any, signal: AttentionSignal) -> float:
        text = str(item).lower()
        if not signal.keywords:
            return signal.similarity_threshold
        hits = sum(1 for kw in signal.keywords if kw.lower() in text)
        return hits / len(signal.keywords) * signal.importance_weight

    def clear_cache(self) -> None:
        self.cache.clear()
