"""Phase O: Attention — 注意力焦点管理。"""

from .attention_types import (
    AttentionCandidate,
    AttentionScoringWeights,
    AttentionState,
    AttentionTrace,
    FocusSelectionResult,
    FocusType,
    InertiaPolicy,
)
from .focus import (
    AttentionFocus,
    FocusState,
    create_attention_focus,
)
from .candidate_selector import CandidateCollector
from .scoring import AttentionScoringEngine

__all__ = [
    "AttentionCandidate",
    "AttentionFocus",
    "AttentionScoringWeights",
    "AttentionState",
    "AttentionTrace",
    "CandidateCollector",
    "FocusState",
    "FocusType",
    "InertiaPolicy",
    "create_attention_focus",
    "AttentionScoringEngine",
]
