"""Phase 39.5 Attention Module — 认知焦点选择层。

Attention 不是任务排序器。它是 OCOS 的认知资源分配系统：
    "当前 OCOS 正在关注什么？"

核心约束 (Phase 38 Attention Boundary):
    - 可调焦点/权重，禁止创建 Goal/改 UserGoal/改 Identity
    - Attention ≠ Desire, Focus ≠ Goal, Observation ≠ Obligation

模块:
    attention_types  — FocusType, AttentionState, AttentionCandidate, InertiaPolicy, AttentionTrace
    candidate_selector — CandidateCollector (候选项收集)
    scoring         — AttentionScoringEngine (评分 + 惯性控制)
"""

from __future__ import annotations

from .attention_types import (
    AttentionCandidate,
    AttentionScoringWeights,
    AttentionState,
    AttentionTrace,
    FocusSelectionResult,
    FocusType,
    InertiaPolicy,
)
from .candidate_selector import CandidateCollector
from .scoring import AttentionScoringEngine

__all__ = [
    # Types
    "FocusType",
    "AttentionState",
    "AttentionCandidate",
    "AttentionScoringWeights",
    "InertiaPolicy",
    "AttentionTrace",
    "FocusSelectionResult",
    # Engine
    "CandidateCollector",
    "AttentionScoringEngine",
]
