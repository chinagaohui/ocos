"""Phase R: ContinuousLearning — 持续学习闭环。"""

from .manager import (
    ContinuousLearning,
    FeedbackType,
    LearningSignalType,
    FeedbackRecord,
    PreferenceEntry,
    LearningResult,
    LearningCycleStats,
    PreferenceModel,
)

__all__ = [
    "ContinuousLearning",
    "FeedbackType",
    "LearningSignalType",
    "FeedbackRecord",
    "PreferenceEntry",
    "LearningResult",
    "LearningCycleStats",
    "PreferenceModel",
]
