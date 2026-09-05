"""memory_recall — 跨会话记忆检索引擎

Freeze Phase 48: 提供统一接口查询语义/模式/经验记忆
用于每次对话开头自动召回相关历史
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class RecallResult:
    """单次记忆召回结果.

    Blueprint v1.1 L2 (Phase 49-B): 扩展认知消费元数据.
    - confidence:     置信度 (来源记忆自身的置信, 缺失时 = relevance)
    - provenance:     来源 ID (episode/trace/entry id)
    - temporal_scope: 时间范围描述 (近/中/远期)
    """
    source: str           # 'semantic' | 'pattern' | 'experience' | 'user'
    relevance: float      # 0.0-1.0
    content: str          # 可展示内容
    metadata: dict = None  # type: ignore[assignment]
    confidence: Optional[float] = None   # Phase 49-B: 置信度
    provenance: str = ""                 # Phase 49-B: 来源 ID
    temporal_scope: str = ""             # Phase 49-B: 时间范围

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.confidence is None:
            self.confidence = self.relevance


@dataclass
class ConflictGroup:
    """冲突记忆组 (Blueprint v1.1 L2).

    同一方案/任务存在成功与失败两种经验时, 不简单 top-k,
    而是输出结构化冲突供 L8 Metacognition 决策.
    """
    subject: str            # 冲突主题 (任务/方案描述)
    success_rate: float     # 历史成功率
    evidence_count: int     # 证据总数
    success_count: int = 0
    fail_count: int = 0
    conflict: bool = True   # 存在冲突

    def summary(self) -> str:
        return (
            f"{self.subject}: success_rate={self.success_rate:.2f}, "
            f"evidence={self.evidence_count}, conflict={self.conflict}"
        )


class MemoryRecall:
    """跨会话记忆检索引擎.

    提供统一接口查询所有记忆类型:
    - Semantic: 事实知识 (query_by_domain/by_confidence)
    - Pattern: 行为模式 (find_by_condition/query_by_status)
    - Experience: 经验教训 (lessons)
    - User: 用户画像 (UserProfile)
    """

    def __init__(self, memory_hub=None, user_memory=None):
        self._hub = memory_hub
        self._user_memory = user_memory
        self._recent_recalls: list[RecallResult] = []
        self._max_history = 50

    def recall(self, context: str | None = None, limit: int = 10) -> list[RecallResult]:
        """召回与当前上下文相关的记忆.

        Args:
            context: 当前对话上下文关键词
            limit: 最大返回数量

        Returns:
            RecallResult 列表，按相关性排序
        """
        results: list[RecallResult] = []

        # 1. 语义记忆召回
        semantic = self._recall_semantic(context, limit=limit // 2)
        results.extend(semantic)

        # 2. 模式记忆召回
        patterns = self._recall_patterns(context, limit=limit // 3)
        results.extend(patterns)

        # 3. 经验记忆召回
        experiences = self._recall_experience(context, limit=limit // 4)
        results.extend(experiences)

        # 4. 用户画像（总是注入）
        user_summary = self._recall_user()
        if user_summary:
            results.insert(0, user_summary)

        # 按相关性排序并限制数量
        results.sort(key=lambda r: r.relevance, reverse=True)
        self._recent_recalls = results[:self._max_history]

        return results[:limit]

    def _recall_semantic(self, context: str | None, limit: int) -> list[RecallResult]:
        """从语义记忆中召回."""
        results = []
        if self._hub and hasattr(self._hub, 'semantic') and self._hub.semantic:
            try:
                store = self._hub.semantic
                # 尝试按领域查询
                if context:
                    keywords = self._extract_keywords(context)
                    for keyword in keywords[:3]:
                        try:
                            entries = store.query_by_domain(keyword, limit=limit)
                            for entry in entries:
                                results.append(RecallResult(
                                    source="semantic",
                                    relevance=entry.confidence if hasattr(entry, 'confidence') else 0.5,
                                    content=entry.content if hasattr(entry, 'content') else str(entry),
                                    metadata={"id": entry.id if hasattr(entry, 'id') else None},
                                ))
                        except Exception:
                            pass

                # 兜底：查询高置信度条目
                if not results:
                    entries = store.query_by_confidence(min_confidence=0.7, limit=limit)
                    for entry in entries:
                        results.append(RecallResult(
                            source="semantic",
                            relevance=entry.confidence if hasattr(entry, 'confidence') else 0.7,
                            content=entry.content if hasattr(entry, 'content') else str(entry),
                            metadata={"id": entry.id if hasattr(entry, 'id') else None},
                        ))
                # FIX-09: bi-gram 相关性过滤
                results = self._filter_by_relevance(results, context, min_score=0.12)
            except Exception as e:
                import logging
                logging.debug(f"Semantic recall failed: {e}")

        return results

    def _recall_patterns(self, context: str | None, limit: int) -> list[RecallResult]:
        """从模式记忆中召回."""
        results = []
        if self._hub and hasattr(self._hub, 'pattern') and self._hub.pattern:
            try:
                store = self._hub.pattern
                # 查询高置信度模式
                patterns = store.query_highest_confidence(limit=limit)
                for p in patterns:
                    results.append(RecallResult(
                        source="pattern",
                        relevance=p.confidence if hasattr(p, 'confidence') else 0.5,
                        content=p.description if hasattr(p, 'description') else str(p),
                        metadata={"id": p.id if hasattr(p, 'id') else None},
                    ))
                # FIX-09: bi-gram 相关性过滤
                results = self._filter_by_relevance(results, context, min_score=0.15)
            except Exception as e:
                import logging
                logging.debug(f"Pattern recall failed: {e}")

        return results

    def _recall_experience(self, context: str | None, limit: int) -> list[RecallResult]:
        """从经验记忆中召回经验教训（lesson）。

        S2.4 (白皮书 P2): 原实现引用不存在的 hub.experience 属性——
        MemoryHub 只有 episode/belief/semantic/pattern 四库，本召回恒空。
        经验教训（LessonsLearned）落库形态为 episodes 表 source='lesson'，
        故经 hub.episode.query_by_source 召回。
        """
        results: list[RecallResult] = []
        episode_store = getattr(self._hub, "episode", None) if self._hub else None
        if episode_store is None:
            return results
        try:
            lessons = episode_store.query_by_source("lesson", limit=limit)
            for lesson in lessons:
                # lesson 落库: condition=适用条件, decision=教训描述
                content = (getattr(lesson, "decision", None)
                           or getattr(lesson, "condition", None)
                           or getattr(lesson, "outcome", None))
                if not isinstance(content, str) or not content:
                    content = str(lesson.decision or lesson.condition or "")
                if not content:
                    continue
                results.append(RecallResult(
                    source="experience",
                    relevance=0.8,
                    content=content,
                    metadata={"type": "lesson"},
                ))
            # FIX-09: bi-gram 相关性过滤
            results = self._filter_by_relevance(results, context, min_score=0.15)
        except Exception as e:
            import logging
            logging.debug(f"Experience recall failed: {e}")

        return results

    def _recall_user(self) -> Optional[RecallResult]:
        """召回用户画像摘要."""
        if self._user_memory:
            try:
                summary = self._user_memory.summarize()
                if summary and summary != "(no user profile yet)":
                    return RecallResult(
                        source="user",
                        relevance=1.0,
                        content=summary,
                        metadata={"type": "user_profile"},
                    )
            except Exception:
                pass
        return None

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """从上下文中提取关键词."""
        # 简单关键词提取：按常见分隔符分割
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.split()
        # 过滤短词和停用词
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'with'}
        return [w for w in words if len(w) > 2 and w not in stopwords][:5]

    @staticmethod
    def _bi_gram_overlap(text_a: str, text_b: str) -> float:
        """计算两个文本的字符 bi-gram 重叠度 (0.0-1.0)。

        用于中文相关性过滤：相邻字符对集合的 Jaccard 相似度。
        """
        def _grams(s: str) -> set:
            s = s.lower().strip()
            return set(s[i:i+2] for i in range(len(s) - 1) if s[i:i+2].strip())
        ga, gb = _grams(text_a), _grams(text_b)
        if not ga or not gb:
            return 0.0
        intersection = ga & gb
        union = ga | gb
        return len(intersection) / len(union) if union else 0.0

    # FIX-16: 中文同义词表 — 扩大语义覆盖
    _SYNONYM_TABLE: dict[str, list[str]] = {
        "结果": ["outcome", "result", "成果", "成效"],
        "失败": ["failure", "failed", "出错", "异常"],
        "目标": ["goal", "objective", "任务"],
        "记忆": ["memory", "memories", "记录"],
        "对话": ["chat", "conversation", "dialogue"],
    }

    def _expand_keywords(self, context: str) -> set[str]:
        """FIX-16: 基于同义词表扩展关键词集合."""
        expanded = set(self._extract_keywords(context))
        for kw in list(expanded):
            for syn in self._SYNONYM_TABLE.get(kw, []):
                expanded.add(syn)
        return expanded

    def _dynamic_threshold(self, hub: Any) -> float:
        """FIX-16: 根据记忆密度动态调整阈值 — 记忆多时放宽, 少时严格."""
        if not hub or not hasattr(hub, 'get_stats'):
            return 0.15
        try:
            stats = hub.get_stats()
            total = stats.get('episode_count', 0) + stats.get('belief_count', 0)
            if total > 1000:
                return 0.10  # 记忆丰富 → 放宽阈值
            elif total < 50:
                return 0.25  # 记忆稀疏 → 严格过滤
            return 0.15
        except Exception:
            return 0.15

    def _filter_by_relevance(self, results: list[RecallResult],
                             context: str | None, min_score: float = 0.15
                             ) -> list[RecallResult]:
        """FIX-09/16: 按 bi-gram 重叠度过滤召回结果（FIX-16: 动态阈值 + 同义词扩展）."""
        if not context:
            return results
        # FIX-16: 动态阈值 — 根据记忆密度调整
        dynamic_min = self._dynamic_threshold(self._hub)
        final_min = min(min_score, dynamic_min)  # 取更严格的
        filtered = []
        for r in results:
            score = self._bi_gram_overlap(context, r.content)
            # FIX-16: 同义词扩展匹配
            if score < final_min:
                expanded = self._expand_keywords(context)
                for kw in expanded:
                    if kw.lower() in r.content.lower():
                        score = max(score, 0.15)  # 同义词命中至少 0.15
                        break
            if score >= final_min:
                r.relevance = max(r.relevance, score)
                filtered.append(r)
        return filtered

    def format_for_prompt(self, context: str | None = None, limit: int = 10,
                          learning_rules: list[dict] | None = None) -> str:
        """格式化为系统提示注入字符串."""
        recalls = self.recall(context, limit)
        lines: list[str] = []
        if recalls:
            lines.append("## Relevant Memories")
            for r in recalls:
                icon = {"user": "👤", "semantic": "📚", "pattern": "🔁", "experience": "💡"}.get(r.source, "📝")
                lines.append(f"{icon} [{r.source}] (relevance: {r.relevance:.2f})")
                lines.append(f"   {r.content[:200]}")

        # FIX-06/FIX-20: 注入学习规则（成功/失败冲突）；无召回时规则仍注入
        if learning_rules:
            conflict_lines = []
            for rule in learning_rules:
                succ = int(rule.get("success_count", 0) or 0)
                fail = int(rule.get("fail_count", 0) or 0)
                rate = float(rule.get("success_rate", 0.0) or 0.0)
                pattern = rule.get("task_pattern", "?")
                if succ + fail >= 2:
                    tag = "⚠️" if rate < 0.5 else "✅"
                    conflict_lines.append(f"{tag} {pattern}: 成功{succ}/失败{fail} (率={rate:.0%})")
            if conflict_lines:
                lines.append("\n## 学习规则（历史经验）")
                lines.extend(conflict_lines[:5])

        return "\n".join(lines)

    def clear_recent(self) -> None:
        """清空最近召回历史."""
        self._recent_recalls = []

    # ── Phase 49-B: 认知消费增强 ──────────────────────────────────────

    def recall_cognitive(self, context: str | None = None,
                         limit: int = 10,
                         learning_rules: list[dict] | None = None,
                         ) -> dict:
        """面向认知主链的召回 — 返回结构化结果 (Blueprint v1.1 L2).

        相比 recall() (纯列表), 增加:
          - conflict_set: 冲突记忆组 (来自学习规则的成功/失败统计)
          - 统一字典结构, 供 think() premises 注入

        Args:
            context: 当前上下文
            limit: 最大记忆条数
            learning_rules: Phase 49-A LearningModel.rules 列表
                           (每条含 task_pattern/success_rate/fail_count)
        """
        recalls = self.recall(context, limit)
        conflict_set: list[ConflictGroup] = []

        # 从学习规则检测冲突: 同任务既有成功又有失败 → 冲突
        if learning_rules:
            for rule in learning_rules:
                succ = int(rule.get("success_count", 0) or 0)
                fail = int(rule.get("fail_count", 0) or 0)
                if succ + fail < 2:
                    continue  # 单样本不构成冲突
                rate = float(rule.get("success_rate", 0.0) or 0.0)
                group = ConflictGroup(
                    subject=rule.get("task_pattern", "unknown")[:60],
                    success_rate=rate,
                    evidence_count=succ + fail,
                    success_count=succ,
                    fail_count=fail,
                    conflict=0.0 < rate < 1.0,
                )
                if group.conflict:
                    conflict_set.append(group)

        return {
            "memories": [
                {
                    "source": r.source,
                    "relevance": r.relevance,
                    "confidence": r.confidence,
                    "content": r.content[:300],
                    "provenance": r.provenance,
                    "temporal_scope": r.temporal_scope,
                    "metadata": r.metadata,
                }
                for r in recalls
            ],
            "conflict_set": [
                {
                    "subject": c.subject,
                    "success_rate": c.success_rate,
                    "evidence_count": c.evidence_count,
                    "success_count": c.success_count,
                    "fail_count": c.fail_count,
                    "conflict": c.conflict,
                    "summary": c.summary(),
                }
                for c in conflict_set
            ],
        }
