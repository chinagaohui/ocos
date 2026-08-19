"""Phase 59-j: TrendAnalyzer — cross-chapter trend detection for engine-level adjustment.

Watches the last N chapters and detects systemic quality issues that
single-chapter repair can't fix. When a trend is found, it recommends
adjustments to the NarrativeContract — OpenTale's control plane.

Pipeline:
    OCOS QualityReports (N chapters) → TrendAnalyzer → TrendSignals
    TrendSignal → DecisionTranslator → ContractAdjustment
    ContractAdjustment → narrative_contract.json patch
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ═══ TrendSignal ═══

@dataclass
class TrendSignal:
    """A detected systemic pattern across multiple chapters."""

    trend_id: str                          # e.g. "emotional_decay_trend"
    description: str                       # Human-readable diagnosis
    confidence: float                      # 0.0-1.0, how sure OCOS is

    # Which dimensions are affected
    affected_dimensions: list[str] = field(default_factory=list)

    # The evidence: chapter numbers + scores that triggered this
    evidence: list[dict[str, Any]] = field(default_factory=list)

    # The recommended adjustment (filled by DecisionTranslator)
    severity: str = "info"                 # info | warn | critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "trend_id": self.trend_id,
            "description": self.description,
            "confidence": self.confidence,
            "affected_dimensions": self.affected_dimensions,
            "evidence": self.evidence,
            "severity": self.severity,
        }


# ═══ TrendAnalyzer ═══

class TrendAnalyzer:
    """Analyzes cross-chapter quality trends for OCOS.

    Pure rules, no LLM. Exchanges quality data for systemic insights.
    """

    # Configuration
    MIN_CHAPTERS_FOR_TREND = 3             # Need at least this many chapters
    WINDOW_SIZE = 5                        # Look at last N chapters
    TREND_THRESHOLD = 0.5                  # Score below this = concerning
    DECAY_THRESHOLD = -0.05                # Per-chapter score drop = decaying
    CONSECUTIVE_FAIL_THRESHOLD = 3         # Consecutive chapters below threshold → trend

    def __init__(self):
        self._analysis_count: int = 0

    def analyze(self, chapter_reports: list[dict[str, Any]],
                window_size: int | None = None) -> list[TrendSignal]:
        from ocos.opentale_bridge.ocos_activation import activate
        activate("A1_trend_analyzer")
        activate("C2_trend_data")
        """Analyze a sequence of chapter quality reports for systemic trends.

        Args:
            chapter_reports: List of dicts, each with:
                - chapter_number: int
                - ocos_overall: float
                - ocos_dimensions: {dim_name: {score: float, ...}}
            window_size: How many chapters to consider (default: WINDOW_SIZE)

        Returns:
            List of TrendSignal, may be empty.
        """
        self._analysis_count += 1
        w = window_size or self.WINDOW_SIZE
        window = chapter_reports[-w:] if len(chapter_reports) > w else chapter_reports

        if len(window) < self.MIN_CHAPTERS_FOR_TREND:
            return []

        trends: list[TrendSignal] = []

        # ── Trend 1: Decaying overall quality ──
        t_decay = self._detect_decay(window)
        if t_decay:
            trends.append(t_decay)

        # ── Trend 2: Chronic dimension failure ──
        for dim_name in ["narrative_density", "character_coherence",
                          "emotional_curve", "genre_compliance", "language_quality"]:
            t_dim = self._detect_chronic_dimension(window, dim_name)
            if t_dim:
                trends.append(t_dim)

        # ── Trend 3: Monotone emotional curve ──
        t_emotion = self._detect_monotone_emotional(window)
        if t_emotion:
            trends.append(t_emotion)

        # ── Trend 4: Dialogue imbalance ──
        t_dialogue = self._detect_dialogue_imbalance(window)
        if t_dialogue:
            trends.append(t_dialogue)

        # ── Trend 5: Genre compliance decay ──
        t_genre = self._detect_genre_drift(window)
        if t_genre:
            trends.append(t_genre)

        # Sort by confidence descending
        trends.sort(key=lambda t: t.confidence, reverse=True)
        return trends

    # ═══ Detection rules ═══

    def _detect_decay(self, window: list[dict]) -> Optional[TrendSignal]:
        """Detect if overall scores are trending downward."""
        scores = [r.get("ocos_overall", 0) for r in window]
        if len(scores) < 3:
            return None

        # Linear trend: compute slope roughly
        x = list(range(len(scores)))
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(scores) / n
        num = sum((x[i] - mean_x) * (scores[i] - mean_y) for i in range(n))
        den = sum((xi - mean_x) ** 2 for xi in x)
        slope = num / den if den != 0 else 0

        if slope < self.DECAY_THRESHOLD:
            severity = "critical" if slope <= -0.1 else "warn"
            return TrendSignal(
                trend_id="quality_decay",
                description=f"Overall quality declining ({slope:.3f}/chapter) across {len(window)} chapters. "
                            f"From {scores[0]:.2f} → {scores[-1]:.2f}.",
                confidence=min(0.9, abs(slope) * 5),
                affected_dimensions=["all"],
                evidence=[{"chapter": r["chapter"], "ocos_overall": r.get("ocos_overall")}
                          for r in window],
                severity=severity,
            )
        return None

    def _detect_chronic_dimension(self, window: list[dict],
                                   dim_name: str) -> Optional[TrendSignal]:
        """Detect if a specific dimension is consistently below threshold."""
        scores = []
        for r in window:
            dims = r.get("ocos_dimensions", {})
            if dim_name in dims:
                scores.append((r["chapter"], dims[dim_name].get("score", 0)))

        below = [(ch, s) for ch, s in scores if s < self.TREND_THRESHOLD]
        if len(below) >= self.CONSECUTIVE_FAIL_THRESHOLD:
            # Check if the last N are all below (consecutive at the tail)
            tail_scores = scores[-self.CONSECUTIVE_FAIL_THRESHOLD:]
            all_tail_low = all(s < self.TREND_THRESHOLD for _, s in tail_scores)
            if all_tail_low or len(below) >= len(scores) * 0.7:
                avg = sum(s for _, s in below) / len(below)
                return TrendSignal(
                    trend_id=f"chronic_{dim_name}",
                    description=f"{dim_name} chronically low: {len(below)}/{len(window)} chapters "
                                f"below {self.TREND_THRESHOLD} (avg={avg:.2f})",
                    confidence=min(0.95, len(below) / len(window) + 0.3),
                    affected_dimensions=[dim_name],
                    evidence=[{"chapter": ch, "score": s} for ch, s in below],
                    severity="critical" if len(below) >= 4 else "warn",
                )
        return None

    def _detect_monotone_emotional(self, window: list[dict]) -> Optional[TrendSignal]:
        """Detect if emotional_curve scores are consistently flat."""
        scores = []
        for r in window:
            dims = r.get("ocos_dimensions", {})
            ec = dims.get("emotional_curve", {})
            scores.append(ec.get("score", 0))

        if len(scores) < 3:
            return None

        variance = self._variance(scores)
        mean_score = sum(scores) / len(scores)

        # Low variance + median-range scores = monotone, not terrible but boring
        if variance < 0.02 and 0.3 < mean_score < 0.7:
            return TrendSignal(
                trend_id="monotone_emotional",
                description=f"Emotional curve is flat (variance={variance:.4f}) over {len(window)} chapters. "
                            f"Mean={mean_score:.2f} — consistent but lacks peaks.",
                confidence=0.7,
                affected_dimensions=["emotional_curve"],
                evidence=[{"chapter": r["chapter"], "score": dims.get("emotional_curve", {}).get("score")}
                          for r in window if (dims := r.get("ocos_dimensions", {}))],
                severity="warn",
            )
        return None

    def _detect_dialogue_imbalance(self, window: list[dict]) -> Optional[TrendSignal]:
        """Detect if dialogue ratio is too high or too low across chapters."""
        dialogue_ratios = []
        for r in window:
            dims = r.get("ocos_dimensions", {})
            nd = dims.get("narrative_density", {})
            # We can't get dialogue_ratio directly from ocos_dimensions,
            # but we can check if narrative_density concerns mention dialogue
            concerns = nd.get("concerns", [])
            for c in concerns:
                if "对白" in str(c):
                    dialogue_ratios.append({"chapter": r["chapter"], "concern": c})

        if len(dialogue_ratios) >= 2:
            return TrendSignal(
                trend_id="dialogue_imbalance",
                description=f"Dialogue imbalance detected in {len(dialogue_ratios)} chapters. "
                            f"See concerns: {[d['concern'][:50] for d in dialogue_ratios[:3]]}",
                confidence=0.65,
                affected_dimensions=["narrative_density"],
                evidence=dialogue_ratios,
                severity="warn",
            )
        return None

    def _detect_genre_drift(self, window: list[dict]) -> Optional[TrendSignal]:
        """Detect if genre_compliance scores are steadily dropping."""
        scores = []
        for r in window:
            dims = r.get("ocos_dimensions", {})
            gc = dims.get("genre_compliance", {})
            scores.append((r["chapter"], gc.get("score", 0)))

        low_count = sum(1 for _, s in scores if s < self.TREND_THRESHOLD)
        if low_count >= self.CONSECUTIVE_FAIL_THRESHOLD:
            return TrendSignal(
                trend_id="genre_drift",
                description=f"Genre compliance fading: {low_count}/{len(window)} chapters "
                            f"below {self.TREND_THRESHOLD}",
                confidence=min(0.9, low_count / len(window) + 0.3),
                affected_dimensions=["genre_compliance"],
                evidence=[{"chapter": ch, "score": s} for ch, s in scores if s < self.TREND_THRESHOLD],
                severity="critical" if low_count >= 4 else "warn",
            )
        return None

    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((v - mean) ** 2 for v in values) / len(values)
