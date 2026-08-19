"""KnowledgeBase — 语义知识表示与查询。

知识 = <主体, 谓词, 客体, 置信度> 三元组。
支持多层级查询和关系推理。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class KnowledgeTriple:
    """知识三元组。"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source: str = "system"
    created_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    id: Optional[str] = None


class KnowledgeBase:
    """知识库 — 语义知识的三元组存储。"""

    def __init__(self):
        self._triples: list[KnowledgeTriple] = []
        self._lock = threading.RLock()

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._triples)

    def add(self, subject: str, predicate: str, object: str,
            confidence: float = 1.0, source: str = "system",
            tags: Optional[list[str]] = None) -> str:
        """添加知识三元组。"""
        with self._lock:
            triple = KnowledgeTriple(
                subject=subject,
                predicate=predicate,
                object=object,
                confidence=confidence,
                source=source,
                tags=tags or [],
                id=f"k-{len(self._triples) + 1}",
            )
            self._triples.append(triple)
            return triple.id or ""

    def query(self, subject: Optional[str] = None,
              predicate: Optional[str] = None,
              object: Optional[str] = None,
              min_confidence: float = 0.0) -> list[KnowledgeTriple]:
        """查询知识。任意字段可留空作为通配符。"""
        with self._lock:
            results = list(self._triples)
            if subject is not None:
                results = [r for r in results if r.subject == subject]
            if predicate is not None:
                results = [r for r in results if r.predicate == predicate]
            if object is not None:
                results = [r for r in results if r.object == object]
            if min_confidence > 0:
                results = [r for r in results
                           if r.confidence >= min_confidence]
            return results

    def find_by_subject(self, subject: str) -> list[KnowledgeTriple]:
        """查找关于某主体的所有知识。"""
        return self.query(subject=subject)

    def find_by_object(self, object: str) -> list[KnowledgeTriple]:
        """查找引用了某客体的所有知识。"""
        return self.query(object=object)

    def find_relations(self, subject: str, object: str) -> list[KnowledgeTriple]:
        """查找两个实体之间的关系。"""
        with self._lock:
            return [
                r for r in self._triples
                if r.subject == subject and r.object == object
            ]

    def update_confidence(self, subject: str, predicate: str,
                          object: str, new_confidence: float) -> bool:
        """更新特定三元组的置信度。"""
        with self._lock:
            for triple in self._triples:
                if (triple.subject == subject
                        and triple.predicate == predicate
                        and triple.object == object):
                    triple.confidence = new_confidence
                    return True
            return False

    def remove(self, subject: str, predicate: str,
               object: str) -> bool:
        """移除特定三元组。"""
        with self._lock:
            original_len = len(self._triples)
            self._triples = [
                t for t in self._triples
                if not (t.subject == subject
                        and t.predicate == predicate
                        and t.object == object)
            ]
            return len(self._triples) < original_len

    def search(self, text: str) -> list[KnowledgeTriple]:
        """全文搜索知识。"""
        text_lower = text.lower()
        with self._lock:
            return [
                t for t in self._triples
                if text_lower in t.subject.lower()
                or text_lower in t.predicate.lower()
                or text_lower in t.object.lower()
            ]

    def clear(self) -> None:
        with self._lock:
            self._triples.clear()
