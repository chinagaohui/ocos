"""Phase 52: SemanticExtractor + ObservationBuilder.

SemanticExtractor: 从 Observation 中提取意义
    - 意图识别 (intent)
    - 领域识别 (domain)
    - 实体提取 (entities)
    - 情感分析 (sentiment)
    - 优先级提示 (priority_hint)

ObservationBuilder: 组装 Observation
    - 创建结构化 Observation
    - 合并多条 Observation
    - 创建异常 Observation
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SemanticFragment, SensorModality,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SemanticExtractor
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SemanticExtractor:
    """语义提取器 — 从原始 Observation 提取结构化语义。

    不负责验证 (交给 PerceptionValidator)。
    不负责决策 (交给 Decision Layer)。
    只负责: Observation → SemanticFragment。
    """

    # 意图关键词映射
    intent_patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "develop": ["开发", "写", "实现", "build", "create", "implement", "coding", "代码"],
        "analyze": ["分析", "审计", "检查", "review", "analyze", "audit", "inspect"],
        "learn": ["学习", "了解", "研究", "learn", "study", "research"],
        "fix": ["修复", "改", "修", "fix", "repair", "patch", "correct"],
        "plan": ["计划", "规划", "设计", "plan", "design", "schedule"],
        "inquire": ["查询", "找", "搜索", "search", "find", "lookup", "look for"],
    })

    # 领域关键词映射
    domain_patterns: dict[str, list[str]] = field(default_factory=lambda: {
        "software_engineering": ["代码", "系统", "架构", "API", "数据库", "缓存"],
        "data_analysis": ["分析", "数据", "统计", "图表"],
        "narrative": ["故事", "叙事", "角色", "情节"],
        "system_health": ["状态", "健康", "错误", "性能"],
    })

    # 情感关键词
    sentiment_words: dict[str, list[str]] = field(default_factory=lambda: {
        "positive": ["好", "成功", "完成", "优秀", "感谢"],
        "negative": ["失败", "错误", "问题", "需要修复", "慢"],
        "urgent": ["紧急", "马上", "立即", "asep", "urgent"],
    })

    def extract(self, obs: Observation) -> SemanticFragment | None:
        """从 Observation 提取语义片段。"""
        if obs.modality != SensorModality.TEXT:
            return None

        text = str(obs.content) if obs.content else ""
        if not text.strip():
            return None

        return SemanticFragment(
            text=text,
            intent=self._detect_intent(text),
            domain=self._detect_domain(text),
            entities=self._extract_entities(text),
            sentiment=self._detect_sentiment(text),
            priority_hint=self._detect_priority_hint(text),
            confidence=obs.confidence,
            source_observation_id=obs.id,
        )

    def _detect_intent(self, text: str) -> str:
        """关键词检测意图。"""
        scores: dict[str, int] = {}
        for intent, keywords in self.intent_patterns.items():
            scores[intent] = sum(1 for kw in keywords if kw in text)
        if not any(scores.values()):
            return "unknown"
        return max(scores, key=scores.get)  # type: ignore

    def _detect_domain(self, text: str) -> str:
        scores: dict[str, int] = {}
        for domain, keywords in self.domain_patterns.items():
            scores[domain] = sum(1 for kw in keywords if kw in text)
        if not any(scores.values()):
            return "general"
        return max(scores, key=scores.get)  # type: ignore

    def _extract_entities(self, text: str) -> list[str]:
        """简单实体提取: 引号内文本 + 专有名词。"""
        entities: list[str] = []
        # 引号内文本
        quoted = re.findall(r'["""]([^"»"]+)["\u201d"]', text)
        entities.extend(quoted)
        # 反引号内
        backticked = re.findall(r'`([^`]+)`', text)
        entities.extend(backticked)
        return entities[:10]  # limit

    def _detect_sentiment(self, text: str) -> str:
        scores: dict[str, int] = {}
        for sentiment, words in self.sentiment_words.items():
            scores[sentiment] = sum(1 for w in words if w in text)
        if scores.get("urgent", 0) > 0:
            return "urgent"
        pos = scores.get("positive", 0)
        neg = scores.get("negative", 0)
        if pos > neg:
            return "positive"
        elif neg > pos:
            return "negative"
        return "neutral"

    def _detect_priority_hint(self, text: str) -> str:
        if any(w in text for w in ["紧急", "马上", "立即", "asep", "urgent"]):
            return "urgent"
        if any(w in text for w in ["重要", "关键", "核心", "critical"]):
            return "high"
        return "normal"


# ═══════════════════════════════════════════════════════════════════════════════
# ObservationBuilder
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ObservationBuilder:
    """Observation 工厂 — 创建结构化 Observation。

    用于:
        - 内部事件转 Observation
        - 异常包装为 Observation
        - 多 Observation 合并
    """

    def from_raw(self, content: Any, modality: SensorModality,
                 source: str = "internal", confidence: float = 0.9) -> Observation:
        return Observation(
            modality=modality,
            type=ObservationType.RAW,
            content=content,
            confidence=confidence,
            source_sensor=source,
        )

    def from_anomaly(self, anomaly_type: str, detail: Any,
                     source: str = "internal") -> Observation:
        return Observation(
            modality=SensorModality.EVENT,
            type=ObservationType.ANOMALY,
            content={"type": anomaly_type, "detail": detail},
            confidence=0.8,
            source_sensor=source,
        )

    def from_change(self, change_desc: str, old_value: Any, new_value: Any,
                    source: str = "internal") -> Observation:
        return Observation(
            modality=SensorModality.EVENT,
            type=ObservationType.CHANGE,
            content={"description": change_desc, "old": old_value, "new": new_value},
            confidence=0.95,
            source_sensor=source,
        )

    def merge(self, observations: list[Observation]) -> Observation:
        """合并多条 Observation 为一条。"""
        contents = [o.content for o in observations]
        avg_confidence = (
            sum(o.confidence for o in observations) / len(observations)
            if observations else 0.0
        )
        return Observation(
            modality=observations[0].modality if observations else SensorModality.UNKNOWN,
            type=ObservationType.STRUCTURED,
            content={"merged": contents, "count": len(observations)},
            confidence=avg_confidence,
            source_sensor="merger",
        )


__all__ = ["SemanticExtractor", "ObservationBuilder"]
