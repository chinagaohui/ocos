"""Phase 59: OpenTale Output → OCOS Feedback Loop.

Takes chapter output from OpenTale and feeds it back to OCOS for:
  - Memory updates (episodic/semantic/wisdom)
  - Belief recalibration (confidence adjustments)
  - Knowledge enrichment (world model updates)
  - Identity continuity check (is the story still on-track?)
"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timezone

from ocos.opentale_bridge.bridge_model import FeedbackInput, OcosDecision, RepairDecision
from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer, QualityReport


class FeedbackLoop:
    """Processes OpenTale chapter output and feeds it back to OCOS.

    This is the "learning from execution" step. OpenTale writes a chapter,
    we analyze it, and feed structured observations back to OCOS so it
    can adjust its mental model for the next cycle.

    Phase 59-g: Now includes OCOS's own QualityAnalyzer — OCOS actually
    reads the text and forms its own judgment, instead of just trusting
    external scores.
    """

    def __init__(self):
        self.feedback_history: list[FeedbackInput] = []
        self._chapter_count: int = 0
        self.quality_analyzer = QualityAnalyzer()

    def process(self, chapter_output: dict[str, Any],
                original_decision: Optional[OcosDecision] = None) -> FeedbackInput:
        """Process OpenTale chapter output into structured feedback for OCOS.

        Args:
            chapter_output: Raw output from OpenTale's Writer (chapter dict)
            original_decision: The OCOS decision that drove this chapter

        Returns:
            FeedbackInput ready to feed back to OCOS
        """
        self._chapter_count += 1

        chapter_num = chapter_output.get("chapter_number", self._chapter_count)
        title = chapter_output.get("title", "")
        text = chapter_output.get("chapter_text", chapter_output.get("content", ""))
        word_count = chapter_output.get("word_count", len(text))

        # Extract quality signals
        quality = chapter_output.get("quality_score", 0.0)
        mechanical = chapter_output.get("mechanical_score", 0.0)
        narrative = chapter_output.get("narrative_score", 0.0)

        # Character arc progress
        arcs = chapter_output.get("arc_progress", chapter_output.get("arcs", {}))

        # Conflicts
        resolved = chapter_output.get("conflicts_resolved", [])
        escalated = chapter_output.get("conflicts_escalated", [])
        new_confs = chapter_output.get("new_conflicts", [])

        # Emotional beats
        peaks = chapter_output.get("emotional_peaks", [])
        impact = chapter_output.get("reader_impact", quality)

        # Issues
        issues = chapter_output.get("issues", chapter_output.get("repair_needed", []))
        suggestions = chapter_output.get("repair_suggestions", [])

        # ── Identity check: is the story drifting? ──
        identity_warning = self._check_identity_drift(
            original_decision, chapter_num, quality)

        # ── OCOS 自主质量分析 (Phase 59-g) ──
        # OCOS actually reads the chapter text and forms its own judgment.
        ocos_analysis = None
        if text:
            genre = chapter_output.get("genre", "romance")
            arcs = chapter_output.get("arc_progress", chapter_output.get("arcs", {}))
            report = self.quality_analyzer.analyze(
                chapter_text=text,
                genre=genre,
                chapter_number=chapter_num,
                chapter_title=title,
                expected_arcs=arcs if isinstance(arcs, dict) else None,
                external_quality=quality if quality > 0 else None,
                external_narrative=narrative if narrative > 0 else None,
            )
            ocos_analysis = report.to_ocos_feedback()

        fb = FeedbackInput(
            source="opentale",
            chapter_number=chapter_num,
            chapter_title=title,
            total_words=word_count,
            quality_score=quality,
            mechanical_score=mechanical,
            narrative_score=narrative,
            arcs_advanced=arcs if isinstance(arcs, dict) else {},
            conflicts_resolved=resolved,
            conflicts_escalated=escalated,
            new_conflicts=new_confs,
            emotional_peaks=peaks,
            reader_impact_estimate=impact,
            issues=issues + ([identity_warning] if identity_warning else []),
            repair_suggestions=suggestions,
            chapter_text=text,
            ocos_analysis=ocos_analysis,
        )

        self.feedback_history.append(fb)
        return fb

    def _check_identity_drift(self, decision: Optional[OcosDecision],
                              chapter_num: int, quality: float) -> Optional[str]:
        """Detect if quality is dropping or identity is drifting."""
        if quality < 0.3:
            return f"IDENTITY_DRIFT: Chapter {chapter_num} quality={quality:.2f} — significant deviation from target. Consider re-anchoring."
        if quality < 0.5:
            return f"QUALITY_WARN: Chapter {chapter_num} quality={quality:.2f} — below threshold."
        return None

    def to_ocos_input(self, fb: FeedbackInput) -> dict:
        """Convert FeedbackInput to an OCOS-digestible format.

        This is the format that OCOS's Perception layer can ingest.
        """
        return {
            "type": "chapter_feedback",
            "source": "opentale",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chapter": fb.chapter_number,
            "title": fb.chapter_title,
            "quality": {
                "overall": fb.quality_score,
                "mechanical": fb.mechanical_score,
                "narrative": fb.narrative_score,
            },
            "arcs": fb.arcs_advanced,
            "conflicts": {
                "resolved": fb.conflicts_resolved,
                "escalated": fb.conflicts_escalated,
                "new": fb.new_conflicts,
            },
            "emotional_peaks": fb.emotional_peaks,
            "issues": fb.issues,
            "summary": (
                f"Chapter {fb.chapter_number} ({fb.total_words} words, "
                f"quality={fb.quality_score:.2f}). "
                f"Conflicts resolved: {len(fb.conflicts_resolved)}, "
                f"escalated: {len(fb.conflicts_escalated)}. "
                f"Issues: {len(fb.issues)}."
            ),
        }

    # ═══ Repair Loop (Phase 59-i) ═══

    def evaluate_and_repair(self, fb: FeedbackInput,
                            original_decision: Optional[OcosDecision] = None
                            ) -> Optional[RepairDecision]:
        """评估反馈是否需要重写，如果需要则生成 RepairDecision。

        Returns:
            RepairDecision if repair is needed, None otherwise.
        """
        # 已达最大尝试次数
        if fb.repair_attempt >= QualityReport.MAX_REPAIR_ATTEMPTS:
            return None  # exhausted, accept degraded

        # 没有 OCOS 分析 → 无法判断
        if not fb.ocos_analysis:
            return None

        # 重建 QualityReport 从 ocos_analysis 中抽取 needs_repair 判定
        # Since ocos_analysis is a dict from report.to_ocos_feedback(),
        # we re-run a lightweight check
        oa = fb.ocos_analysis
        overall = oa.get("ocos_overall", 1.0)
        dims = oa.get("ocos_dimensions", {})

        # needs_repair check
        if overall >= QualityReport.REPAIR_OVERALL_THRESHOLD:
            any_dim_failing = any(
                d.get("score", 1.0) < QualityReport.REPAIR_DIMENSION_THRESHOLD
                for d in dims.values()
            )
            if not any_dim_failing:
                return None  # all good

        # ── Generate repair ──
        return self.generate_repair_decision(fb, original_decision)

    def generate_repair_decision(self, fb: FeedbackInput,
                                  original_decision: Optional[OcosDecision] = None
                                  ) -> RepairDecision:
        """生成重写决策：调整后的 OCOS 参数 + 具体修复指导。"""
        oa = fb.ocos_analysis or {}
        overall = oa.get("ocos_overall", 0.0)
        dims = oa.get("ocos_dimensions", {})
        dim_min = QualityReport.REPAIR_DIMENSION_THRESHOLD

        failing = [name for name, d in dims.items() if d.get("score", 1.0) < dim_min]

        # Build repair guidance
        guidance: dict[str, Any] = {
            "repair_reason": "quality_below_threshold",
            "overall_score": overall,
            "threshold": QualityReport.REPAIR_OVERALL_THRESHOLD,
            "failing_dimensions": failing,
            "dimension_guidance": {},
            "preserve": [],
        }
        for dim_name in failing:
            guidance["dimension_guidance"][dim_name] = {
                "current_score": dims[dim_name]["score"],
                "threshold": dim_min,
                "concerns": dims[dim_name].get("concerns", []),
                "suggestions": QualityReport._repair_suggestions_for(dim_name),
            }

        # Adjusted OCOS parameters
        adjusted_focus = None
        adjusted_tone = None
        adjusted_instructions: list[str] = []

        if original_decision:
            if failing:
                # Shift focus to the weakest dimension
                adjusted_focus = f"repair_{failing[0]}"
                adjusted_instructions.append(f"Focus on fixing {failing[0]}: {', '.join(dims[failing[0]].get('concerns', ['needs improvement']))}")

            if "emotional_curve" in failing:
                adjusted_tone = "heightened_emotional"
                adjusted_instructions.append("Increase emotional intensity — more peaks, more variance")
            elif "genre_compliance" in failing:
                adjusted_tone = original_decision.emotional_tone
                adjusted_instructions.append("Ensure genre compliance: add genre-required elements")

            # Preserve what's working
            if "character_coherence" not in failing:
                adjusted_instructions.append("Preserve character profiles — they're solid")
            if "narrative_density" not in failing:
                adjusted_instructions.append("Keep current scene structure — it works")

        repair = RepairDecision(
            chapter_number=fb.chapter_number,
            attempt=fb.repair_attempt + 1,
            max_attempts=QualityReport.MAX_REPAIR_ATTEMPTS,
            overall_score=overall,
            failing_dimensions=failing,
            repair_guidance=guidance,
            adjusted_focus=adjusted_focus,
            adjusted_tone=adjusted_tone,
            adjusted_instructions=adjusted_instructions,
        )

        # Update the feedback input
        fb.repair_decision = repair

        return repair

    # ═══ Cross-Chapter Trend Analysis (Phase 59-j) ═══

    def analyze_cross_chapter_trends(self) -> list[dict[str, Any]]:
        """Analyze all accumulated feedback for systemic trends.

        Returns a list of TrendSignal dicts that can be passed to
        DecisionTranslator.translate_adjustment().
        """
        if len(self.feedback_history) < 3:
            return []

        from ocos.opentale_bridge.trend_analyzer import TrendAnalyzer

        analyzer = TrendAnalyzer()
        chapter_reports = []
        for fb in self.feedback_history:
            oa = fb.ocos_analysis or {}
            chapter_reports.append({
                "chapter": fb.chapter_number,
                "ocos_overall": oa.get("ocos_overall", fb.quality_score),
                "ocos_dimensions": oa.get("ocos_dimensions", {}),
            })

        trends = analyzer.analyze(chapter_reports)
        return [t.to_dict() for t in trends]
