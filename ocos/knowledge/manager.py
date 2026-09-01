"""Knowledge Manager — 统一的知识管理接口

Freeze Phase 51: 聚合本地知识库 + 外部知识源，提供统一查询接口
"""

from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor

from ocos.agent.knowledge_base import KnowledgeBase, KnowledgeTriple
from ocos.knowledge.store.registry import KnowledgeRegistry, AccessScope

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    """知识查询结果"""
    query: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    sources: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": self.results[:10],  # 限制返回数量
            "total": self.total,
            "sources": self.sources,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExternalSource:
    """外部知识源配置"""
    source_id: str
    name: str
    fetch_fn: Any  # callable(query: str) -> list[dict]
    timeout_seconds: int = 30
    enabled: bool = True


class KnowledgeManager:
    """统一知识管理器

    聚合：
    - 本地知识三元组
    - 语义记忆
    - 外部知识源（可扩展）
    """

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        registry: Optional[KnowledgeRegistry] = None,
    ):
        self._kb = knowledge_base or KnowledgeBase()
        self._registry = registry or KnowledgeRegistry()
        self._external_sources: dict[str, ExternalSource] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)

    # ── 知识管理 ────────────────────────────────────────────────

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        confidence: float = 1.0,
        source: str = "system",
        tags: Optional[list[str]] = None,
    ) -> str:
        """添加知识三元组到本地知识库。"""
        triple_id = self._kb.add(subject, predicate, object, confidence, source, tags)
        logger.debug("Added triple: %s", triple_id)
        return triple_id

    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[KnowledgeTriple]:
        """查询本地知识三元组。"""
        return self._kb.query(subject, predicate, object, min_confidence)

    def search_text(self, text: str) -> list[KnowledgeTriple]:
        """全文搜索本地知识。"""
        return self._kb.search(text)

    # ── 统一知识检索 ───────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        limit: int = 10,
        include_external: bool = True,
    ) -> KnowledgeResult:
        """统一知识检索 — 聚合本地 + 外部。

        Args:
            query: 查询文本
            limit: 最大返回数量
            include_external: 是否包含外部知识源
        """
        results: list[dict[str, Any]] = []
        sources: set[str] = {"local"}

        # 1. 本地知识搜索
        local_results = self.search_text(query)
        for triple in local_results[:limit]:
            results.append({
                "source": "knowledge_base",
                "subject": triple.subject,
                "predicate": triple.predicate,
                "object": triple.object,
                "confidence": triple.confidence,
                "content": f"{triple.subject} {triple.predicate} {triple.object}",
            })

        # 2. 语义记忆（如果已注册）
        semantic_results = self._search_semantic(query, limit - len(results))
        if semantic_results:
            results.extend(semantic_results)
            sources.add("semantic_memory")

        # 3. 外部知识源
        if include_external:
            external_results = self._search_external(query, limit - len(results))
            if external_results:
                results.extend(external_results)
                sources.update(r.get("source", "unknown") for r in external_results)

        return KnowledgeResult(
            query=query,
            results=results[:limit],
            total=len(results),
            sources=list(sources),
        )

    # ── 外部知识源 ─────────────────────────────────────────────

    def register_external_source(self, source: ExternalSource) -> None:
        """注册外部知识源。"""
        self._external_sources[source.source_id] = source
        logger.info("Registered external source: %s", source.name)

    def unregister_external_source(self, source_id: str) -> bool:
        """注销外部知识源。"""
        if source_id in self._external_sources:
            del self._external_sources[source_id]
            return True
        return False

    def _search_external(self, query: str, max_results: int) -> list[dict]:
        """搜索所有已注册的外部知识源。"""
        results: list[dict] = []
        for source in self._external_sources.values():
            if not source.enabled:
                continue
            try:
                source_results = source.fetch_fn(query)
                for r in source_results[:max_results - len(results)]:
                    r["source"] = source.source_id
                results.extend(source_results)
                if len(results) >= max_results:
                    break
            except Exception as e:
                logger.warning("External source %s failed: %s", source.source_id, e)
        return results

    # ── 语义记忆桥接 ───────────────────────────────────────────

    def _search_semantic(self, query: str, max_results: int) -> list[dict]:
        """搜索语义记忆（通过 MemoryHub 桥接）。"""
        # 延迟导入，避免循环依赖
        from ocos.memory.recall import MemoryRecall
        
        recall = MemoryRecall()
        if not recall.supports_hub(None):
            return []

        results = recall.recall(query, limit=max_results)
        return [
            {
                "source": "semantic_memory",
                "content": r.content,
                "relevance": r.relevance,
                "doc_type": r.doc_type,
            }
            for r in results
        ]

    # ── 知识更新 ───────────────────────────────────────────────

    def update_confidence(
        self,
        subject: str,
        predicate: str,
        object: str,
        new_confidence: float,
    ) -> bool:
        """更新知识三元组的置信度。"""
        return self._kb.update_confidence(subject, predicate, object, new_confidence)

    def remove_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
    ) -> bool:
        """移除知识三元组。"""
        return self._kb.remove(subject, predicate, object)

    def clear_all(self) -> None:
        """清空所有本地知识。"""
        self._kb.clear()

    # ── 统计信息 ───────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """获取知识管理统计。"""
        return {
            "local_triples": self._kb.count,
            "external_sources": len(self._external_sources),
            "enabled_sources": sum(
                1 for s in self._external_sources.values() if s.enabled
            ),
        }

    def close(self) -> None:
        """关闭资源。"""
        self._executor.shutdown(wait=False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── 便捷函数 ────────────────────────────────────────────────────


def create_knowledge_manager(
    knowledge_base: Optional[KnowledgeBase] = None,
    registry: Optional[KnowledgeRegistry] = None,
) -> KnowledgeManager:
    """创建知识管理器的便捷函数。"""
    return KnowledgeManager(knowledge_base, registry)
