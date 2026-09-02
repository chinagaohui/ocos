"""Phase R: ContinuousLearning — 持续学习闭环。

整合现有学习基础设施：
- LearningEngine: 模型学习（已有）
- LessonsLearned: 行为教训归纳（已有）
- ExperienceProfile: 经验特征投影（已有）
- MetaCognition: 元认知（已有）

新增能力：
- FeedbackLearning: 从用户反馈中学习偏好
- PreferenceModel: 用户偏好建模
- LearningCycle: 学习周期管理（收集→归纳→更新→应用）
- LearningReport: 学习报告生成

职责：
  - 从交互数据中提取学习信号
  - 更新用户偏好模型
  - 调整输出策略（风格/频率/优先级）
  - 生成学习报告和趋势分析
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """反馈类型。"""
    POSITIVE = auto()      # 用户认可
    NEGATIVE = auto()      # 用户否定
    CORRECTION = auto()    # 用户纠正
    PREFERENCE = auto()    # 用户偏好表达


class LearningSignalType(Enum):
    """学习信号类型。"""
    PREFERENCE = auto()
    BEHAVIORAL = auto()
    KNOWLEDGE = auto()
    STYLE = auto()
    FREQUENCY = auto()


@dataclass
class FeedbackRecord:
    """反馈记录。"""
    feedback_id: str
    feedback_type: FeedbackType
    target_message: str          # 被评价的消息内容（前50字符）
    signal: str                  # 具体反馈内容
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    is_corrected: bool = False   # 是否已被修正


@dataclass
class PreferenceEntry:
    """单条偏好记录。"""
    key: str                     # 如 "output_style" / "frequency"
    value: Any
    confidence: float = 0.5      # [0, 1] 置信度
    source_count: int = 1        # 支持该偏好的反馈数
    last_updated: float = field(default_factory=time.time)


@dataclass
class LearningResult:
    """学习结果。"""
    success: bool
    signal_type: LearningSignalType
    description: str
    preferences_updated: list[str] = field(default_factory=list)
    confidence_change: float = 0.0


@dataclass
class LearningCycleStats:
    """学习周期统计。"""
    total_feedbacks: int = 0
    positive_count: int = 0
    negative_count: int = 0
    corrections_count: int = 0
    preferences_learned: int = 0
    learning_rate: float = 0.5
    last_learning_time: Optional[float] = None
    sessions_analyzed: int = 0


class PreferenceModel:
    """用户偏好模型。

    从反馈中学习并维护用户偏好。
    """

    def __init__(self) -> None:
        self._preferences: dict[str, PreferenceEntry] = {}
        self._history: list[FeedbackRecord] = []
        self._max_history = 1000

    @property
    def preference_count(self) -> int:
        return len(self._preferences)

    def add_feedback(self, record: FeedbackRecord) -> None:
        """添加反馈并尝试更新偏好。"""
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # 提取偏好
        self._extract_preference(record)

    def _extract_preference(self, record: FeedbackRecord) -> None:
        """从反馈中提取偏好。"""
        ctx = record.context
        signal = record.signal.lower()

        # 基于反馈类型提取
        if record.feedback_type == FeedbackType.POSITIVE:
            # 正向反馈 → 强化当前偏好
            for key in ["style", "tone", "length", "frequency"]:
                if key in signal:
                    self._update_preference(key, signal, confidence=0.6)

        elif record.feedback_type == FeedbackType.NEGATIVE:
            # 负向反馈 → 降低当前偏好或转向
            for key in ["style", "tone", "length", "frequency"]:
                if key in signal:
                    self._update_preference(key, f"not_{signal}", confidence=0.4)

        elif record.feedback_type == FeedbackType.PREFERENCE:
            # 直接偏好表达
            if "like" in signal or "prefer" in signal or "want" in signal:
                self._update_preference("general", signal, confidence=0.8)

        # 上下文中的结构化偏好
        for key, value in ctx.items():
            if isinstance(value, (str, int, float, bool)):
                self._update_preference(key, str(value), confidence=0.7)

    def _update_preference(self, key: str, value: Any, confidence: float) -> None:
        """更新单条偏好。"""
        if key in self._preferences:
            entry = self._preferences[key]
            # 加权平均更新置信度
            entry.confidence = 0.7 * entry.confidence + 0.3 * confidence
            entry.source_count += 1
            entry.last_updated = time.time()
        else:
            self._preferences[key] = PreferenceEntry(
                key=key,
                value=value,
                confidence=confidence,
                source_count=1,
            )

    def get_preference(self, key: str) -> Optional[Any]:
        """获取偏好值。"""
        entry = self._preferences.get(key)
        return entry.value if entry else None

    def get_all_preferences(self) -> dict[str, Any]:
        """获取所有偏好。"""
        return {k: v.value for k, v in self._preferences.items()}

    def get_confidence(self, key: str) -> float:
        """获取偏好置信度。"""
        entry = self._preferences.get(key)
        return entry.confidence if entry else 0.0

    def get_recommendation(self, domain: str) -> Optional[Any]:
        """获取某领域的推荐值。"""
        # 精确匹配
        if domain in self._preferences:
            return self._preferences[domain].value
        # 前缀匹配
        for key, entry in self._preferences.items():
            if key.startswith(domain):
                return entry.value
        return None

    def update_from_feedback(self, feedback: FeedbackRecord) -> LearningResult:
        """从反馈更新，返回学习结果。"""
        before = len(self._preferences)
        self.add_feedback(feedback)
        after = len(self._preferences)

        updated_keys = [k for k, v in self._preferences.items() if v.last_updated >= feedback.timestamp - 0.1]

        return LearningResult(
            success=True,
            signal_type=LearningSignalType.PREFERENCE,
            description=f"Updated {len(updated_keys)} preferences from feedback",
            preferences_updated=updated_keys,
            confidence_change=sum(v.confidence for k, v in self._preferences.items()) / max(1, len(self._preferences)) - 0.5,
        )


class ContinuousLearning:
    """Phase R: 持续学习管理器。

    整合反馈学习、偏好建模、学习周期管理。
    """

    def __init__(self) -> None:
        self._preference_model = PreferenceModel()
        self._stats = LearningCycleStats()
        self._learning_history: list[dict[str, Any]] = []
        self._max_history = 500
        self._started_at = time.time()

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def stats(self) -> LearningCycleStats:
        return self._stats

    @property
    def preference_count(self) -> int:
        return self._preference_model.preference_count

    def record_feedback(
        self,
        feedback_type: FeedbackType,
        signal: str,
        target_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> FeedbackRecord:
        """记录一条反馈。"""
        import uuid
        record = FeedbackRecord(
            feedback_id=f"FB-{uuid.uuid4().hex[:8]}",
            feedback_type=feedback_type,
            target_message=target_message[:50],
            signal=signal,
            context=context or {},
        )
        self._preference_model.add_feedback(record)
        self._stats.total_feedbacks += 1

        if feedback_type == FeedbackType.POSITIVE:
            self._stats.positive_count += 1
        elif feedback_type == FeedbackType.NEGATIVE:
            self._stats.negative_count += 1
        elif feedback_type == FeedbackType.CORRECTION:
            self._stats.corrections_count += 1

        self._record_learning(record)
        return record

    def learn_from_interaction(
        self,
        interaction_type: str,
        user_response: str,
        ai_output: str,
    ) -> LearningResult:
        """从交互中学习用户偏好。"""
        # 分析用户响应
        response_lower = user_response.lower()

        # 判断反馈类型
        if any(w in response_lower for w in ["good", "great", "perfect", "thanks", "yes", "correct"]):
            feedback_type = FeedbackType.POSITIVE
            signal = f"positive:{interaction_type}"
        elif any(w in response_lower for w in ["bad", "wrong", "no", "incorrect", "fix", "wrong"]):
            feedback_type = FeedbackType.NEGATIVE
            signal = f"negative:{interaction_type}"
        elif any(w in response_lower for w in ["prefer", "like", "want", "i like", "i prefer"]):
            feedback_type = FeedbackType.PREFERENCE
            signal = user_response
        else:
            feedback_type = FeedbackType.CORRECTION
            signal = user_response

        record = self.record_feedback(
            feedback_type=feedback_type,
            signal=signal,
            target_message=ai_output[:100],
            context={"interaction_type": interaction_type, "user_response": user_response},
        )

        return self._preference_model.update_from_feedback(record)

    def get_preferences(self) -> dict[str, Any]:
        """获取当前学习到的偏好。"""
        return self._preference_model.get_all_preferences()

    def get_recommendation(self, domain: str) -> Optional[Any]:
        """获取某领域的推荐值。"""
        return self._preference_model.get_recommendation(domain)

    def get_stats(self) -> dict[str, Any]:
        """获取学习统计。"""
        total = self._stats.positive_count + self._stats.negative_count
        return {
            "total_feedbacks": self._stats.total_feedbacks,
            "positive_ratio": self._stats.positive_count / total if total > 0 else 0.0,
            "correction_rate": self._stats.corrections_count / total if total > 0 else 0.0,
            "preference_count": self._preference_model.preference_count,
            "learning_rate": self._stats.learning_rate,
            "uptime_seconds": time.time() - self._started_at,
            "recent_learnings": self._learning_history[-5:],
        }

    def generate_learning_report(self) -> str:
        """生成学习报告。"""
        lines = [
            "=" * 50,
            "持续学习报告",
            "=" * 50,
            f"总反馈数: {self._stats.total_feedbacks}",
            f"  正向: {self._stats.positive_count}",
            f"  负向: {self._stats.negative_count}",
            f"  纠正: {self._stats.corrections_count}",
            f"已学偏好数: {self._preference_model.preference_count}",
            "",
            "偏好详情:",
        ]
        for key, entry in self._preference_model._preferences.items():
            lines.append(f"  {key}: {entry.value} (置信度={entry.confidence:.2f}, 来源={entry.source_count})")
        lines.append("")
        lines.append(f"学习时长: {time.time() - self._started_at:.1f}秒")
        lines.append("=" * 50)
        return "\n".join(lines)

    # ── Internal ────────────────────────────────────────────────────────

    def _record_learning(self, record: FeedbackRecord) -> None:
        """记录学习历史。"""
        self._learning_history.append({
            "timestamp": datetime.fromtimestamp(record.timestamp, tz=timezone.utc).isoformat(),
            "type": record.feedback_type.name,
            "signal": record.signal[:80],
            "target": record.target_message,
        })
        if len(self._learning_history) > self._max_history:
            self._learning_history = self._learning_history[-self._max_history:]
