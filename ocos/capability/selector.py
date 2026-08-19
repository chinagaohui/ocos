"""Phase 23 — Capability Selector。

Intent → SkillGraph 映射管道:
  IntentParser → IntentClassification → SkillGraphRetrieval → Ranking → Selection
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.capability.models import SkillGraph


@dataclass
class SelectorResult:
    """Capability Selector 的查询结果。"""

    selected_graph: Optional[SkillGraph]
    candidates: list[SkillGraph] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""


class CapabilitySelector:
    """Intent → Skill Graph 映射器。

    关键词匹配决定映射（初版）。
    未来可扩展为语义匹配/向量检索。

    用法:
        registry = SkillRegistry(db_path=...)
        graphs = registry.list_graphs()
        selector = CapabilitySelector(graphs)
        result = selector.select(intent="我需要解决一个技术问题", context={...})
    """

    # 关键词 → graph ID 精确映射
    KEYWORD_GRAPH_MAP: dict[str, list[str]] = {
        "solve": ["problem_solving"],
        "解决": ["problem_solving"],
        "plan": ["planning"],
        "计划": ["planning"],
        "规划": ["planning"],
        "decide": ["decision"],
        "决定": ["decision"],
        "决策": ["decision"],
        "reflect": ["reflection"],
        "反思": ["reflection"],
        "learn": ["learning"],
        "学习": ["learning"],
        "create": ["writing"],
        "创建": ["writing"],
        "写作": ["writing"],
        "analyze": ["problem_solving"],
        "分析": ["problem_solving"],
        "optimize": ["optimize"],
        "优化": ["optimize"],
        "research": ["research"],
        "研究": ["research"],
    }

    def __init__(self, available_graphs: Optional[list[SkillGraph]] = None):
        self._graphs: dict[str, SkillGraph] = {}
        if available_graphs:
            for graph in available_graphs:
                self.register(graph)

    # ── 注册 ────────────────────────────────────────────────────────────

    def register(self, graph: SkillGraph) -> None:
        """注册 SkillGraph。"""
        self._graphs[graph.id] = graph

    def unregister(self, graph_id: str) -> bool:
        """注销 SkillGraph。"""
        return self._graphs.pop(graph_id, None) is not None

    def clear(self) -> None:
        """清空所有注册。"""
        self._graphs.clear()

    def _list_graphs(self) -> list[SkillGraph]:
        return list(self._graphs.values())

    # ── 选择 ────────────────────────────────────────────────────────────

    def select(
        self,
        intent: Optional[Any],
        context: Optional[dict[str, Any]] = None,
    ) -> SelectorResult:
        """根据 Intent 选择最佳 SkillGraph。

        Args:
            intent: 用户意图（str 或 Intent 对象）
            context: 上下文信息（goal_stack, working_memory, agent_id）

        Returns:
            SelectorResult 包含选中的 graph、候选项和原因
        """
        if not self._graphs:
            return SelectorResult(
                selected_graph=None,
                confidence=0.0,
                reason="no graphs registered",
            )

        # 1. 解析 Intent
        keyword = self._extract_keyword(intent)

        if not keyword:
            return SelectorResult(
                selected_graph=None,
                confidence=0.0,
                reason="could not extract keyword from intent",
            )

        # 2. 匹配关键词
        matched_graph_ids = self._match_keywords(keyword)

        # 3. 选择匹配的 Graph
        candidates: list[SkillGraph] = []
        for graph in self._graphs.values():
            for kw in matched_graph_ids:
                if self._graph_matches(graph, kw):
                    candidates.append(graph)
                    break

        # 4. 若映射关键词无匹配，回退到原始关键词
        if not candidates:
            for graph in self._graphs.values():
                if self._graph_matches(graph, keyword):
                    candidates.append(graph)

        if not candidates:
            return SelectorResult(
                selected_graph=None,
                candidates=[],
                confidence=0.0,
                reason=f"no graph matched keyword '{keyword}' (matched: {matched_graph_ids})",
            )

        # 5. 排序（按 graph id 对齐，可替换为语义相似度排序）
        best = candidates[0]
        confidence = 1.0 / len(candidates)  # 多候选时降低信心

        return SelectorResult(
            selected_graph=best,
            candidates=candidates,
            confidence=confidence,
            reason=f"matched keyword '{keyword}'",
        )

    # ── 内部方法 ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_keyword(intent: Any) -> Optional[str]:
        """从 Intent 中提取关键词。"""
        if intent is None:
            return None

        if isinstance(intent, str):
            text = intent.lower()
        elif hasattr(intent, "content"):
            text = str(intent.content).lower()
        elif hasattr(intent, "__str__"):
            text = str(intent).lower()
        else:
            return None

        # 先尝试关键词映射
        for keyword in CapabilitySelector.KEYWORD_GRAPH_MAP:
            if keyword in text:
                return keyword

        # 回退：使用第一个英文单词作为关键词
        words = text.split()
        for word in words:
            # 优先英文字母词
            if any(c.isascii() and c.isalpha() for c in word):
                return word

        return None

    @staticmethod
    def _match_keywords(keyword: str) -> list[str]:
        """根据关键词找到匹配的 graph 标签。"""
        kw = keyword.lower()
        for pattern, tags in CapabilitySelector.KEYWORD_GRAPH_MAP.items():
            if pattern in kw or kw in pattern:
                return tags
        return [keyword]

    @staticmethod
    def _graph_matches(graph: SkillGraph, keyword: str) -> bool:
        """检查 graph 是否匹配关键词。

        匹配规则:
          1. 精确匹配 graph id
          2. keyword 的任何部分出现在 graph 名称/描述中
          3. keyword 匹配 metadata tags
        """
        composite = f"{graph.id} {graph.name} {graph.description}".lower()
        tags: list[str] = graph.metadata.get("tags", [])

        # 精确匹配 id
        if keyword == graph.id:
            return True

        # keyword 或 keyword 的词干出现在 composite 中
        if keyword.lower() in composite:
            return True

        # 对复合关键词，尝试各部分
        parts = keyword.lower().replace("_", " ").split()
        for part in parts:
            if part in composite:
                return True

        # 匹配 tags
        if keyword in tags:
            return True

        return False
