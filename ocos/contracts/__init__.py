"""OCOS Contracts — ABI definitions that all layers agree on.

Phase 35: Attention ABI — frozen cognitive control protocol.
Phase 36: Executive Attention Binding — extended with AttentionRecommendation, DecisionDigest.
Phase 37: Adaptive Cognitive Feedback Loop — CognitiveFeedback, Evidence, DriftAlert.
"""

from ocos.contracts.attention_abi import (
    AttentionReport,
    AttentionRecommendation,
    FocusChange,
    DecisionDigest,
    DecisionType,
    AttentionDecision,
    ALLOW_PLANNING,
    DEFER_PLANNING,
    EXECUTION_ALLOW,
    EXECUTION_BLOCK_ATTENTION,
    FORBIDDEN_DECISION_REASONS,
)
from ocos.contracts.feedback_abi import (
    CognitiveFeedback,
    ExpectedOutcome,
    ActualOutcome,
    OutcomeEvaluation,
    EvaluationStatus,
    LearningSignal,
    FeedbackState,
    Evidence,
    DriftAlert,
    DriftSeverity,
    DriftType,
    ADAPTIVE_PARAM_KEYS,
    IMMUTABLE_PARAM_KEYS,
    MAX_SINGLE_STEP_DELTA,
    MAX_DAILY_MUTATION_BUDGET,
    CALIBRATION_MIN_SAMPLES,
    USER_ALIGNMENT_REJECT_THRESHOLD,
)

__all__ = [
    # Attention (Phase 35/36)
    "AttentionReport",
    "AttentionRecommendation",
    "FocusChange",
    "DecisionDigest",
    "DecisionType",
    "AttentionDecision",
    "ALLOW_PLANNING",
    "DEFER_PLANNING",
    "EXECUTION_ALLOW",
    "EXECUTION_BLOCK_ATTENTION",
    "FORBIDDEN_DECISION_REASONS",
    # Feedback (Phase 37)
    "CognitiveFeedback",
    "ExpectedOutcome",
    "ActualOutcome",
    "OutcomeEvaluation",
    "EvaluationStatus",
    "LearningSignal",
    "FeedbackState",
    "Evidence",
    "DriftAlert",
    "DriftSeverity",
    "DriftType",
    "ADAPTIVE_PARAM_KEYS",
    "IMMUTABLE_PARAM_KEYS",
    "MAX_SINGLE_STEP_DELTA",
    "MAX_DAILY_MUTATION_BUDGET",
    "CALIBRATION_MIN_SAMPLES",
    "USER_ALIGNMENT_REJECT_THRESHOLD",
]
