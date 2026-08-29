"""
B2 Attention Engine — 注意力评分引擎。

对 Observation 计算注意力度量：
- Novelty (新颖性)：与历史观察的偏离程度
- Goal Relevance (目标相关性)：与当前 Context 中目标的对齐程度
- Urgency (紧急度)：是否需要立即处理

输出 AttentionScore，支持过滤和排序。
独立模块，仅依赖 ocos.kernel.abi。
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.kernel.abi import Observation, SCHEMA_VERSION
from ocos.kernel.abi import Goal
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 默认权重配置 ────────────────────────────────────────────

DEFAULT_NOVELTY_WEIGHT = 0.3
DEFAULT_RELEVANCE_WEIGHT = 0.4
DEFAULT_URGENCY_WEIGHT = 0.3


# ── Attention Score ─────────────────────────────────────────

@dataclass(frozen=True)
class AttentionScore:
    """注意力评分结果（冻结、可序列化）。"""
    score_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    observation_id: str = ""
    novelty: float = 0.0       # 0.0 ~ 1.0
    goal_relevance: float = 0.0  # 0.0 ~ 1.0
    urgency: float = 0.0       # 0.0 ~ 1.0
    composite: float = 0.0     # 加权综合分数
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


# ── 内容分析器接口 ──────────────────────────────────────────

class ContentAnalyzer:
    """可扩展的内容分析器基类。

    子类重写 score_novelty / score_relevance / score_urgency。
    B2 提供三个内置实现：
    - DefaultContentAnalyzer（关键词计数基线）
    - FrequencyAnalyzer（去重/频率衰减）
    - UrgencyKeywordAnalyzer（关键词触发）

    GAP-P3-8 (C.3): 移除 docstring 中 SemanticContentAnalyzer
    的"占位承诺" — 该分析器从未实现, 避免误导后续集成。
    """

    def score_novelty(
        self,
        observation: Observation,
        history: list[Observation],
    ) -> float:
        """评估新颖性。0.0 = 完全重复，1.0 = 全新内容。"""
        raise NotImplementedError

    def score_relevance(
        self,
        observation: Observation,
        goals: list[Goal],
    ) -> float:
        """评估目标相关性。0.0 = 无关，1.0 = 高度相关。"""
        raise NotImplementedError

    def score_urgency(
        self,
        observation: Observation,
    ) -> float:
        """评估紧急度。0.0 = 可延迟，1.0 = 需立即处理。"""
        raise NotImplementedError


class DefaultContentAnalyzer(ContentAnalyzer):
    """基于关键词的基线分析器。

    新颖性：与历史观察的内容重叠度倒数
    相关性：与 Goal description 的关键词匹配率
    紧急度：紧急关键词检测
    """

    # 紧急关键词表（中英文）
    URGENT_KEYWORDS: set[str] = {
        "error", "fail", "crash", "alert", "urgent", "critical",
        "halt", "stop", "blocked", "exception", "overload",
        "错误", "失败", "崩溃", "警报", "紧急", "关键",
        "停止", "阻塞", "溢出",
    }

    # 否定/低紧急关键词（降低分数）
    LOW_URGENCY_KEYWORDS: set[str] = {
        "info", "debug", "notice", "trace", "status", "heartbeat",
        "信息", "调试", "通知", "追踪", "状态", "心跳",
    }

    def __init__(self, max_history: int = 100):
        self._last_observations: list[str] = []  # content 的文本摘要
        self._max_history = max_history
        logger.debug("DefaultContentAnalyzer initialized: max_history=%d", max_history)

    def _extract_text(self, observation: Observation) -> str:
        """从 Observation.content 提取可比较文本。"""
        content = observation.content
        if isinstance(content, dict):
            # 合并所有字符串值
            parts = []
            for v in content.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, (list, dict)):
                    parts.append(str(v))
            return " ".join(parts)
        return str(content)

    @staticmethod
    def _char_ngrams(text: str, n: int = 2) -> set[str]:
        """提取字符 n-gram。中英文通用。"""
        text = text.lower()
        if len(text) < n:
            return {text}
        return {text[i:i + n] for i in range(len(text) - n + 1)}

    def _keyword_overlap(self, text_a: str, text_b: str) -> float:
        """计算两个文本的 n-gram 重叠率 [0.0, 1.0]。

        使用字符 bigram 而非空格分词，对中文/日文/韩文等 CJK 文本同样有效。
        """
        grams_a = self._char_ngrams(text_a)
        grams_b = self._char_ngrams(text_b)
        if not grams_a or not grams_b:
            return 0.0
        intersection = grams_a & grams_b
        return len(intersection) / max(len(grams_a), len(grams_b))

    def score_novelty(
        self,
        observation: Observation,
        history: list[Observation],
    ) -> float:
        """新颖性 = 1 - max(重叠率)。全新=1.0，完全重复≈0.0。"""
        text = self._extract_text(observation)

        # 检查历史记录
        if not history and not self._last_observations:
            self._update_history(text)
            return 1.0  # 第一条总是新颖

        # 与最近历史对比
        max_overlap = 0.0
        for obs in history:
            hist_text = self._extract_text(obs)
            overlap = self._keyword_overlap(text, hist_text)
            max_overlap = max(max_overlap, overlap)

        # 也与内置记忆对比
        for hist_text in self._last_observations:
            overlap = self._keyword_overlap(text, hist_text)
            max_overlap = max(max_overlap, overlap)

        novelty = 1.0 - max_overlap
        self._update_history(text)
        logger.debug("Novelty score: obs=%s score=%.4f", observation.observation_id, novelty)
        return max(0.0, min(1.0, novelty))

    def score_relevance(
        self,
        observation: Observation,
        goals: list[Goal],
    ) -> float:
        """相关性 = 与至少一个 Goal description 的最大匹配率。"""
        text = self._extract_text(observation)
        if not text or not goals:
            return 0.0

        max_relevance = 0.0
        for goal in goals:
            if goal.status != "active":
                continue
            goal_text = goal.description.lower()
            if not goal_text:
                continue
            # 关键词重叠 + 目标优先级加权
            overlap = self._keyword_overlap(text, goal_text)

            # 优先级权重：0=0.5, 1=0.75, 2=1.0, 3=1.25
            priority_weight = 0.5 + (goal.priority * 0.25)
            weighted = overlap * priority_weight
            max_relevance = max(max_relevance, weighted)

        return max(0.0, min(1.0, max_relevance))

    def score_urgency(
        self,
        observation: Observation,
    ) -> float:
        """紧急度：紧急关键词 vs 低紧急关键词。"""
        text = self._extract_text(observation).lower()
        if not text:
            return 0.0

        urgent_matches = sum(
            1 for kw in self.URGENT_KEYWORDS if kw.lower() in text
        )
        low_matches = sum(
            1 for kw in self.LOW_URGENCY_KEYWORDS if kw.lower() in text
        )

        if urgent_matches == 0 and low_matches == 0:
            return 0.0

        # 紧急信号减去低紧急信号的归一化分数
        raw = (urgent_matches - low_matches * 0.5) / max(urgent_matches + low_matches, 1)
        urgency = max(0.0, min(1.0, raw))
        logger.debug("Urgency score: obs=%s score=%.4f", observation.observation_id, urgency)
        return urgency

    def _update_history(self, text: str) -> None:
        """维护最近观察的滚动历史。"""
        self._last_observations.append(text)
        if len(self._last_observations) > self._max_history:
            self._last_observations.pop(0)

    def reset_history(self) -> None:
        """重置新颖性历史（新会话/切换上下文时调用）。"""
        self._last_observations.clear()


class FrequencyAnalyzer(ContentAnalyzer):
    """频率分析器：基于内容 hash 的重复检测。"""

    def __init__(self):
        self._seen_hashes: dict[int, int] = {}  # hash → count
        logger.debug("FrequencyAnalyzer initialized")

    def score_novelty(
        self,
        observation: Observation,
        history: list[Observation],
    ) -> float:
        """频率衰减新颖性。第1次=1.0，第2次=0.5，第3次=0.33..."""
        content_hash = hash(str(observation.content))
        count = self._seen_hashes.get(content_hash, 0) + 1
        self._seen_hashes[content_hash] = count
        return 1.0 / count  # 1, 0.5, 0.33, 0.25...

    def score_relevance(
        self,
        observation: Observation,
        goals: list[Goal],
    ) -> float:
        return 0.0  # 频率分析器不做语义相关性

    def score_urgency(self, observation: Observation) -> float:
        return 0.0

    def reset(self) -> None:
        self._seen_hashes.clear()


# ── Attention Engine ─────────────────────────────────────────

class AttentionEngine:
    """注意力引擎：对 Observation 计算并输出 AttentionScore。

    用法:
        engine = AttentionEngine(analyzer=DefaultContentAnalyzer())
        score = engine.score(observation, context)
        filtered = engine.filter(observations, context, threshold=0.3)
    """

    def __init__(
        self,
        analyzer: ContentAnalyzer | None = None,
        novelty_weight: float = DEFAULT_NOVELTY_WEIGHT,
        relevance_weight: float = DEFAULT_RELEVANCE_WEIGHT,
        urgency_weight: float = DEFAULT_URGENCY_WEIGHT,
    ):
        self._analyzer = analyzer or DefaultContentAnalyzer()
        self._novelty_weight = novelty_weight
        self._relevance_weight = relevance_weight
        self._urgency_weight = urgency_weight
        self._observation_cache: dict[str, AttentionScore] = {}
        self._history: list[Observation] = []
        logger.debug(
            "AttentionEngine initialized: analyzer=%s weights=(n=%.2f, r=%.2f, u=%.2f)",
            type(self._analyzer).__name__, novelty_weight, relevance_weight, urgency_weight,
        )

    @property
    def analyzer(self) -> ContentAnalyzer:
        return self._analyzer

    @property
    def history(self) -> list[Observation]:
        return list(self._history)

    def score(
        self,
        observation: Observation,
        goals: list[Goal] | None = None,
    ) -> AttentionScore:
        """为单个 Observation 计算 AttentionScore。"""
        goals = goals or []

        novelty = self._analyzer.score_novelty(observation, self._history)
        relevance = self._analyzer.score_relevance(observation, goals)
        urgency = self._analyzer.score_urgency(observation)

        composite = (
            self._novelty_weight * novelty
            + self._relevance_weight * relevance
            + self._urgency_weight * urgency
        )

        score = AttentionScore(
            observation_id=observation.observation_id,
            novelty=round(novelty, 4),
            goal_relevance=round(relevance, 4),
            urgency=round(urgency, 4),
            composite=round(composite, 4),
        )

        self._observation_cache[observation.observation_id] = score
        self._history.append(observation)
        logger.info("Scored observation: id=%s composite=%.4f (n=%.4f, r=%.4f, u=%.4f)",
                      observation.observation_id, composite, novelty, relevance, urgency)
        return score

    def score_with_context(
        self,
        observation: Observation,
        context: Any = None,  # Context 类型（可选导入避免循环）
    ) -> AttentionScore:
        """以 Context 对象评分的便捷方法。

        从 Context 中提取 goals 传给 score()。
        """
        from ocos.runtime.context_manager import Context
        if isinstance(context, Context):
            return self.score(observation, goals=context.goals)
        return self.score(observation)

    def filter(
        self,
        observations: list[Observation],
        goals: list[Goal] | None = None,
        threshold: float = 0.3,
        max_results: int | None = None,
    ) -> list[tuple[Observation, AttentionScore]]:
        """批量评分并过滤低分观察。

        Returns:
            [(observation, score), ...] 按 composite 降序排列
        """
        scored = []
        for obs in observations:
            score = self.score(obs, goals=goals)
            if score.composite >= threshold:
                scored.append((obs, score))

        # 按 composite 降序
        scored.sort(key=lambda x: -x[1].composite)
        logger.info("Filter: %d/%d observations passed threshold=%.2f",
                     len(scored), len(observations), threshold)

        if max_results is not None:
            scored = scored[:max_results]

        return scored

    def get_score(self, observation_id: str) -> AttentionScore | None:
        """获取之前计算的评分（缓存）。"""
        return self._observation_cache.get(observation_id)

    def reset(self) -> None:
        """重置引擎状态（历史 + 缓存 + 分析器）。"""
        logger.info("AttentionEngine reset")
        self._observation_cache.clear()
        self._history.clear()
        if hasattr(self._analyzer, "reset_history"):
            self._analyzer.reset_history()
        if hasattr(self._analyzer, "reset"):
            self._analyzer.reset()

    def set_weights(
        self,
        novelty_weight: float | None = None,
        relevance_weight: float | None = None,
        urgency_weight: float | None = None,
    ) -> None:
        """动态调整权重（后续 B6 Adaptive Control 可调用）。"""
        if novelty_weight is not None:
            self._novelty_weight = novelty_weight
        if relevance_weight is not None:
            self._relevance_weight = relevance_weight
        if urgency_weight is not None:
            self._urgency_weight = urgency_weight
        logger.debug("Weights updated: n=%.2f r=%.2f u=%.2f",
                      self._novelty_weight, self._relevance_weight, self._urgency_weight)
