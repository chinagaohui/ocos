"""Phase 59: OCOS-OpenTale Bridge — Core Types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
from datetime import datetime, timezone


# ── Bridge Session State ──

class BridgePhase(Enum):
    """States of a bridge session cycle."""
    IDLE = "idle"
    INGESTING = "ingesting"        # OCOS is digesting context/feedback
    DECIDING = "deciding"          # OCOS is producing a Decision
    TRANSLATING = "translating"    # Decision → OpenTale Blueprint
    EXECUTING = "executing"         # OpenTale is writing
    FEEDBACK = "feedback"          # Output → OCOS feedback loop
    COMPLETE = "complete"


# ── OCOS Decision (the brain's output) ──

@dataclass
class OcosDecision:
    """A structured writing decision produced by OCOS after thinking.

    This is what the "brain" outputs. The Translator converts it to OpenTale's language.
    """
    decision_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Strategic
    primary_focus: str = ""            # "relationship" | "plot" | "character" | "world"
    emotional_tone: str = ""           # "tension" | "warmth" | "melancholy" | "suspense"
    pacing_directive: str = ""         # "accelerate" | "decelerate" | "maintain"

    # Tactical
    chapter_goal: str = ""             # What this chapter should accomplish
    conflict_instruction: str = ""     # How to escalate/resolve conflict
    character_instructions: dict[str, str] = field(default_factory=dict)  # char → goal
    key_scenes: list[str] = field(default_factory=list)  # Must-include scene types

    # Constraints
    word_target: int = 3000
    pov_character: str = ""
    cliffhanger_type: str = ""         # "emotional" | "plot" | "revelation" | "none"
    forbidden_elements: list[str] = field(default_factory=list)

    # Meta
    confidence: float = 0.7
    reasoning: str = ""                # Why OCOS made this decision

    # Trace Identity（Phase R1，R1.1 契约）
    correlation_id: str = ""           # 跨系统根（OpenTale 生成，OCOS 原样传播）
    agent_run_id: str = ""             # 本次 Agent 执行身份（OCOS 生成）
    generation_request_id: str = ""    # 本次生成请求身份（OpenTale 生成）


# ── Translation Result (OCOS → OpenTale) ──

@dataclass
class TranslationResult:
    """Result of translating an OCOS Decision into OpenTale's ChapterBlueprint."""
    success: bool
    blueprint: dict[str, Any] = field(default_factory=dict)
    translation_notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── Feedback Input (OpenTale → OCOS) ──

@dataclass
class FeedbackInput:
    """OpenTale chapter output, fed back to OCOS for learning."""
    source: str                             # "open tale"
    chapter_number: int
    chapter_title: str = ""
    total_words: int = 0

    # Quality signals from OpenTale's evaluators
    quality_score: float = 0.0             # 0-1
    mechanical_score: float = 0.0
    narrative_score: float = 0.0

    # Structural feedback
    arcs_advanced: dict[str, float] = field(default_factory=dict)  # char → progress
    conflicts_resolved: list[str] = field(default_factory=list)
    conflicts_escalated: list[str] = field(default_factory=list)
    new_conflicts: list[str] = field(default_factory=list)

    # Emotional feedback
    emotional_peaks: list[str] = field(default_factory=list)
    reader_impact_estimate: float = 0.0

    # Issues detected
    issues: list[str] = field(default_factory=list)
    repair_suggestions: list[str] = field(default_factory=list)

    # Full chapter text (for OCOS to read/learn)
    chapter_text: str = ""

    # OCOS 自己的质量分析 (Phase 59-g)
    ocos_analysis: Optional[dict[str, Any]] = None

    # Repair tracking (Phase 59-i)
    repair_attempt: int = 0
    repair_decision: Optional["RepairDecision"] = None


@dataclass
class RepairDecision:
    """OCOS's decision to request a chapter rewrite. (Phase 59-i)"""
    chapter_number: int
    attempt: int                          # 第几次重写 (1-indexed)
    max_attempts: int = 3                 # QualityReport.MAX_REPAIR_ATTEMPTS

    # Why repair
    overall_score: float = 0.0
    failing_dimensions: list[str] = field(default_factory=list)
    repair_guidance: dict[str, Any] = field(default_factory=dict)

    # Adjusted OCOS decision (modified for repair)
    adjusted_focus: Optional[str] = None  # e.g. "emotional_curve" instead of "plot"
    adjusted_tone: Optional[str] = None
    adjusted_instructions: list[str] = field(default_factory=list)

    @property
    def is_last_attempt(self) -> bool:
        return self.attempt >= self.max_attempts

    def to_dict(self) -> dict:
        return {
            "type": "repair_decision",
            "chapter": self.chapter_number,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "is_last_attempt": self.is_last_attempt,
            "overall_score": self.overall_score,
            "failing_dimensions": self.failing_dimensions,
            "repair_guidance": self.repair_guidance,
            "adjusted_focus": self.adjusted_focus,
            "adjusted_tone": self.adjusted_tone,
            "adjusted_instructions": self.adjusted_instructions,
        }


@dataclass
class ContractAdjustment:
    """Patch to OpenTale's NarrativeContract — the engine-level control plane.

    When OCOS detects systemic quality trends across multiple chapters,
    it generates a ContractAdjustment instead of a per-chapter RepairDecision.
    (Phase 59-j)
    """
    adjustment_id: str                    # unique ID for tracking
    triggered_by: list[str] = field(default_factory=list)  # trend_ids that triggered this

    # Which narrative_contract.json fields to change
    chapter_focus_patch: dict[str, float] = field(default_factory=dict)
    scene_distribution_patch: dict[str, float] = field(default_factory=dict)
    emotion_curve_override: Optional[str] = None
    conflict_priority_patch: dict[str, float] = field(default_factory=dict)
    reveal_strategy_override: Optional[str] = None
    emotional_resonance_target: Optional[float] = None
    cliffhanger_type_override: Optional[str] = None
    release_pattern_override: Optional[str] = None
    confidence_override: Optional[str] = None
    pov_policy_tightening: bool = False

    # Metadata
    reason: str = ""
    generated_at: str = ""
    severity: str = "warn"               # info | warn | critical

    def is_empty(self) -> bool:
        """True if no actual adjustments were generated."""
        return (
            not self.chapter_focus_patch
            and not self.scene_distribution_patch
            and self.emotion_curve_override is None
            and not self.conflict_priority_patch
            and self.reveal_strategy_override is None
            and self.emotional_resonance_target is None
            and self.cliffhanger_type_override is None
            and self.release_pattern_override is None
            and self.confidence_override is None
            and not self.pov_policy_tightening
        )

    def to_contract_patch(self) -> dict[str, Any]:
        """Generate a mergeable patch for narrative_contract.json."""
        patch: dict[str, Any] = {"_adjustment_id": self.adjustment_id, "_reason": self.reason}
        if self.chapter_focus_patch:
            patch["chapter_focus"] = self.chapter_focus_patch
        if self.scene_distribution_patch:
            patch["scene_distribution"] = self.scene_distribution_patch
        if self.emotion_curve_override:
            patch["emotion_curve"] = self.emotion_curve_override
        if self.conflict_priority_patch:
            patch["conflict_priority"] = self.conflict_priority_patch
        if self.reveal_strategy_override:
            patch["reveal_strategy"] = self.reveal_strategy_override
        if self.emotional_resonance_target is not None:
            patch["emotional_resonance"] = {
                "type": "density",
                "target": self.emotional_resonance_target,
            }
        if self.cliffhanger_type_override:
            patch["cliffhanger_type"] = self.cliffhanger_type_override
        if self.release_pattern_override:
            patch["release_pattern"] = self.release_pattern_override
        if self.confidence_override:
            patch["confidence"] = self.confidence_override
        if self.pov_policy_tightening:
            patch["pov_policy"] = {"type": "dual", "switching_rule": "chapter_boundary"}
        return patch

    def to_dict(self) -> dict[str, Any]:
        return {
            "adjustment_id": self.adjustment_id,
            "triggered_by": self.triggered_by,
            "contract_patch": self.to_contract_patch(),
            "reason": self.reason,
            "severity": self.severity,
            "generated_at": self.generated_at,
        }


# ── Bridge Session ──

@dataclass
class BridgeSession:
    """A complete bridge session — one cycle of think→write→feedback."""
    session_id: str
    project_name: str = ""
    phase: BridgePhase = BridgePhase.IDLE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Input: what Hermes fed to OCOS
    context_ingested: list[str] = field(default_factory=list)  # chunks of context

    # OCOS Decision
    decision: Optional[OcosDecision] = None

    # Translation
    translation: Optional[TranslationResult] = None

    # OpenTale execution
    chapter_output: Optional[dict] = None
    role_notes: Optional[str] = None

    # Feedback
    feedback: Optional[FeedbackInput] = None

    # Cycle stats
    cycles_completed: int = 0
    total_elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project_name": self.project_name,
            "phase": self.phase.value,
            "decision": self.decision.__dict__ if self.decision else None,
            "translation_success": self.translation.success if self.translation else None,
            "cycles_completed": self.cycles_completed,
            "total_elapsed_s": self.total_elapsed_seconds,
        }


# ── Web Feed Result ──

@dataclass
class WebFeedResult:
    """Result of searching web and feeding fresh data to OCOS."""
    queries_used: list[str] = field(default_factory=list)
    total_chunks_found: int = 0
    chunks_ingested: int = 0
    topics_covered: list[str] = field(default_factory=list)
    nutrition_report: Any = None  # Phase 58.2 NutritionReport
    errors: list[str] = field(default_factory=list)
