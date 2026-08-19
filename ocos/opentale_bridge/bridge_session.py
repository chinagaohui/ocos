"""Phase 59: Bridge Session — Orchestrates the full OCOS-OpenTale cycle.

Hermis acts as the intermediary:
  1. Hermes feeds context to OCOS
  2. OCOS thinks → produces OcosDecision
  3. Hermes translates decision → OpenTale ChapterBlueprint
  4. OpenTale executes (simulated in test; real via hermes tools in production)
  5. Hermes reads output → feeds back to OCOS
  6. Repeat

This file implements the simulation/verification layer. Production integration
uses the hermes_tools (web_search, terminal, etc.) to actually invoke OpenTale.
"""

from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, timezone
import uuid

from ocos.opentale_bridge.bridge_model import (
    BridgeSession, BridgePhase, OcosDecision,
    TranslationResult, FeedbackInput, RepairDecision, ContractAdjustment,
)
from ocos.opentale_bridge.decision_translator import DecisionTranslator
from ocos.opentale_bridge.feedback_loop import FeedbackLoop
from ocos.opentale_bridge.web_feeder import WebFeeder
from ocos.opentale_bridge.trend_analyzer import TrendAnalyzer


class BridgeSessionOrchestrator:
    """Orchestrates a complete OCOS-OpenTale bridge cycle.

    This is the Hermes "role" — the operator who:
      - Feeds OCOS context
      - Reads OCOS decisions
      - Translates to OpenTale instructions
      - Feeds OpenTale output back to OCOS
    """

    def __init__(self, project_name: str = "default_project"):
        self.session = BridgeSession(
            session_id=f"bridge_{uuid.uuid4().hex[:12]}",
            project_name=project_name,
        )
        self.translator = DecisionTranslator()
        self.feedback_loop = FeedbackLoop()
        self.web_feeder = WebFeeder()
        self._decision_counter = 0

    # ── Step 1: Feed OCOS ──

    def feed_context(self, context_chunks: list[str]) -> BridgeSession:
        """Step 1: Hermes feeds story context to OCOS for ingestion."""
        self.session.phase = BridgePhase.INGESTING
        self.session.context_ingested.extend(context_chunks)
        # In production: call OCOS perception layer, run nutrition protocol
        return self.session

    def feed_web_data(self, strategy: str = "writing_techniques") -> BridgeSession:
        """Feed fresh web-sourced data to OCOS via nutrition protocol."""
        self.session.phase = BridgePhase.INGESTING
        result = self.web_feeder.search_and_feed(strategy=strategy)
        self.session.context_ingested.append(
            f"[WEB_FEED] {strategy}: {result.chunks_ingested} chunks ingested, "
            f"topics: {result.topics_covered}"
        )
        return self.session

    # ── Step 2: OCOS Decides ──

    def produce_decision(self, **overrides) -> OcosDecision:
        """Step 2: OCOS thinks (simulated) and produces a writing decision.

        In production, this would call OCOS's Decision engine with the ingested
        context. Here we simulate with structured output based on context.
        """
        self.session.phase = BridgePhase.DECIDING

        contexts = " | ".join(self.session.context_ingested[-3:])  # last 3 chunks
        ch = self._decision_counter + 1

        primary = overrides.get("primary_focus",
            "character" if ch <= 2 else "relationship")
        tone = overrides.get("emotional_tone",
            "tension" if ch <= 3 else "warmth")
        pacing = overrides.get("pacing_directive",
            "accelerate" if ch <= 1 else "maintain")
        cliff = overrides.get("cliffhanger_type",
            "emotional" if ch % 2 == 1 else "plot")

        decision = OcosDecision(
            decision_id=f"d{ch:04d}_{uuid.uuid4().hex[:8]}",
            primary_focus=primary,
            emotional_tone=tone,
            pacing_directive=pacing,
            chapter_goal=f"Write chapter {ch} with focus on {primary} development",
            conflict_instruction=(
                f"Escalate {primary} conflict. "
                f"Chapter {ch} should raise stakes by 20-30%."
            ),
            character_instructions={"protagonist": f"Advance {primary} arc"},
            key_scenes=overrides.get("key_scenes",
                ["opening_hook", f"{primary}_development", "emotional_peak", "cliffhanger"]),
            word_target=overrides.get("word_target", 3000),
            pov_character=overrides.get("pov_character", ""),
            cliffhanger_type=cliff,
            confidence=overrides.get("confidence", 0.75),
            reasoning=(
                f"Based on ingested context ({len(self.session.context_ingested)} chunks), "
                f"recommending {primary}-focused chapter {ch}. "
                f"Pacing: {pacing}, Tone: {tone}. "
                f"Context hints: {contexts[:200]}"
            ),
        )

        self._decision_counter += 1
        self.session.decision = decision
        return decision

    # ── Step 3: Translate ──

    def translate(self, decision: Optional[OcosDecision] = None,
                  genre: str = "romance", chapter_number: int = 1,
                  total_chapters: int = 40) -> TranslationResult:
        """Step 3: Hermes translates OCOS decision to OpenTale blueprint."""
        self.session.phase = BridgePhase.TRANSLATING

        d = decision or self.session.decision
        if d is None:
            d = self.produce_decision()

        result = self.translator.translate(
            d, genre=genre,
            chapter_number=chapter_number or self._decision_counter,
            total_chapters=total_chapters,
        )
        self.session.translation = result
        return result

    # ── Step 4: Execute (Simulated) ──

    def execute_simulated(self, blueprint: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Step 4: Simulate OpenTale execution (test mode).

        In production, Hermes calls OpenTale's Writer via terminal/cli.
        """
        self.session.phase = BridgePhase.EXECUTING

        bp = blueprint or (
            self.session.translation.blueprint if self.session.translation else {}
        )

        chapter_num = bp.get("chapter_number", self._decision_counter)
        word_target = bp.get("word_target", 3000)
        directive = bp.get("directives", {})

        simulated_output = {
            "chapter_number": chapter_num,
            "title": bp.get("title", f"Chapter {chapter_num}"),
            "word_count": word_target,
            "chapter_text": (
                f"[SIMULATED CHAPTER {chapter_num}]\\n\\n"
                f"Writing with focus: {directive.get('chapter_goal', 'N/A')}\\n"
                f"Created by OCOS decision, translated via Hermes bridge.\\n"
                f"This is a simulated chapter for bridge verification.\\n"
            ),
            "quality_score": 0.82,
            "mechanical_score": 0.85,
            "narrative_score": 0.80,
            "arc_progress": {"protagonist": 0.1 * chapter_num},
            "conflicts_resolved": [],
            "conflicts_escalated": ["main_conflict"],
            "new_conflicts": [],
            "emotional_peaks": ["chapter_emotional_beat"],
            "reader_impact": 0.78,
            "issues": [],
            "repair_suggestions": [],
        }

        self.session.chapter_output = simulated_output
        return simulated_output

    # ── Step 5: Feedback ──

    def feedback(self, chapter_output: Optional[dict[str, Any]] = None) -> FeedbackInput:
        """Step 5: Process OpenTale output and feedback to OCOS."""
        self.session.phase = BridgePhase.FEEDBACK

        output = chapter_output or self.session.chapter_output
        if output is None:
            output = {"chapter_number": 0, "chapter_text": "[no output]"}

        fb = self.feedback_loop.process(
            chapter_output=output,
            original_decision=self.session.decision,
        )
        self.session.feedback = fb
        return fb

    # ── Full Cycle ──

    def run_full_cycle(self, context_chunks: Optional[list[str]] = None,
                       genre: str = "romance",
                       chapter_number: int = 1,
                       total_chapters: int = 40) -> BridgeSession:
        """Run a complete bridge cycle: ingest → decide → translate → execute → feedback.

        This is the Hermes operator performing one full writing cycle.
        """
        if context_chunks:
            self.feed_context(context_chunks)

        decision = self.produce_decision()
        translation = self.translate(decision, genre=genre,
                                     chapter_number=chapter_number,
                                     total_chapters=total_chapters)
        output = self.execute_simulated()
        feedback = self.feedback(output)

        self.session.cycles_completed += 1
        self.session.phase = BridgePhase.COMPLETE

        return self.session

    def run_multi_chapter(self, num_chapters: int = 3,
                          genre: str = "romance",
                          total_chapters: int = 40) -> list[BridgeSession]:
        """Run multiple bridge cycles, simulating a multi-chapter writing process.

        Each cycle: OCOS receives feedback from previous chapter, adjusts decision.
        """
        sessions = []
        for ch in range(1, num_chapters + 1):
            context = [
                f"Writing {genre} novel, chapter {ch}/{total_chapters}",
                f"Previous quality: {self.session.feedback.quality_score if self.session.feedback else 'N/A'}",
            ]
            self.run_full_cycle(
                context_chunks=context,
                genre=genre,
                chapter_number=ch,
                total_chapters=total_chapters,
            )
            sessions.append(self.session)

        return sessions

    # ═══ Repair Cycle (Phase 59-i) ═══

    def run_full_cycle_with_repair(self,
                                   context_chunks: Optional[list[str]] = None,
                                   genre: str = "romance",
                                   chapter_number: int = 1,
                                   total_chapters: int = 40,
                                   max_repair_attempts: int = 3) -> BridgeSession:
        """Run a bridge cycle WITH quality-driven repair loop.

        Flow:
          1. Write chapter (normal cycle)
          2. OCOS reads & analyzes quality
          3. If below threshold → generate RepairDecision → rewrite → go to 2
          4. Max 3 rewrites, then accept degraded or escalate to Hermes
        """
        from ocos.opentale_bridge.quality_analyzer import QualityReport
        QualityReport.MAX_REPAIR_ATTEMPTS = max_repair_attempts

        if context_chunks:
            self.feed_context(context_chunks)

        decision = self.produce_decision()
        best_output = None
        best_feedback = None
        feedback = None
        all_repairs: list[RepairDecision] = []

        for attempt in range(max_repair_attempts + 1):  # +1 = first write + N repairs
            if attempt == 0:
                # First attempt: normal write
                translation = self.translate(decision, genre=genre,
                                             chapter_number=chapter_number,
                                             total_chapters=total_chapters)
                output = self.execute_simulated()
                feedback = self.feedback(output)
            else:
                # Repair attempt: rewrite with adjusted guidance
                repair = all_repairs[-1]
                # Adjust the simulated output to be slightly different on retry
                output = self._execute_simulated_repair(
                    previous_output=best_output,
                    repair_decision=repair,
                    attempt=attempt,
                    chapter_number=chapter_number,
                )
                feedback = self.feedback(output)
                feedback.repair_attempt = attempt
                feedback.repair_decision = repair

            # Track best
            if best_output is None or (feedback.ocos_analysis and
                    feedback.ocos_analysis.get("ocos_overall", 0) >
                    (best_feedback.ocos_analysis.get("ocos_overall", 0) if best_feedback and best_feedback.ocos_analysis else 0)):
                best_output = output
                best_feedback = feedback

            # Check if repair needed
            repair_decision = self.feedback_loop.evaluate_and_repair(
                feedback, original_decision=decision)
            if repair_decision is None:
                # No repair needed — quality is good enough!
                break

            all_repairs.append(repair_decision)

            if repair_decision.is_last_attempt:
                # Last attempt — accept whatever we have (best)
                if best_feedback:
                    feedback = best_feedback
                feedback.issues.append(
                    f"DEGRADED_ACCEPT: {max_repair_attempts} repair attempts exhausted, "
                    f"best score={best_feedback.ocos_analysis.get('ocos_overall', 'N/A') if best_feedback and best_feedback.ocos_analysis else 'N/A'}. "
                    f"Escalate to Hermes for manual review."
                )
                break

        self.session.feedback = best_feedback or feedback
        self.session.cycles_completed += 1
        self.session.phase = BridgePhase.COMPLETE

        return self.session

    def _execute_simulated_repair(self,
                                   previous_output: Optional[dict] = None,
                                   repair_decision: Optional[RepairDecision] = None,
                                   attempt: int = 1,
                                   chapter_number: int = 1) -> dict:
        """Simulate a repair rewrite — improved version of the chapter."""
        base = previous_output or self.session.translation_result or {}
        blueprint = base.get("blueprint", {})
        original_text = base.get("chapter_text", base.get("content", ""))

        # Simulate improvement: each repair attempt slightly bumps quality
        improvement = min(0.12 * attempt, 0.35)  # diminishing returns
        new_quality = min(0.95, base.get("quality_score", 0.7) + improvement)
        new_narrative = min(0.95, base.get("narrative_score", 0.7) + improvement * 0.8)
        new_mechanical = min(0.95, base.get("mechanical_score", 0.7) + improvement * 0.5)

        # Slightly expand text on rewrites
        word_count = int(base.get("word_count", len(str(original_text))) * (1.0 + 0.1 * attempt))
        repaired_text = (original_text
                         + f"\n\n[Repair pass {attempt}: "
                         + ", ".join(repair_decision.adjusted_instructions if repair_decision else [])
                         + "]")

        return {
            "chapter_number": chapter_number,
            "title": base.get("title", f"Chapter {chapter_number} (repair {attempt})"),
            "chapter_text": repaired_text,
            "content": repaired_text,
            "word_count": word_count,
            "quality_score": new_quality,
            "narrative_score": new_narrative,
            "mechanical_score": new_mechanical,
            "arc_progress": base.get("arc_progress", {}),
            "emotional_peaks": base.get("emotional_peaks", []),
            "conflicts_resolved": base.get("conflicts_resolved", []),
            "conflicts_escalated": base.get("conflicts_escalated", []),
            "new_conflicts": base.get("new_conflicts", []),
            "genre": base.get("genre", "romance"),
            "repair_attempt": attempt,
            "blueprint": blueprint,
        }

    # ═══ Contract-Level Adjustment (Phase 59-j) ═══

    def apply_contract_adjustment(
        self,
        adjustment: ContractAdjustment,
        contract_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Apply an engine-level adjustment to OpenTale's NarrativeContract.

        Step 6 in the cross-chapter feedback loop: OCOS detected systemic
        trends → generated a ContractAdjustment → this writes the patch
        to narrative_contract.json so OpenTale's next chapters use the
        corrected parameters.

        In production, this file is at: projects/<id>/narrative_contract.json
        For verification, we only simulate the merge.

        Returns the merged contract dict (simulated).
        """
        # Base contract (simulated — in production, read from disk)
        base_contract = {
            "primary_driver": "relationship",
            "chapter_focus": {"relationship": 6, "plot": 2, "world": 0.5, "mystery": 0.5, "character": 1},
            "conflict_priority": {"interpersonal": 7, "external": 2, "internal": 1},
            "scene_distribution": {"action": 1, "interpersonal": 6, "reflection": 2, "exposition": 1},
            "reveal_strategy": "gradual",
            "emotion_curve": "oscillation",
            "reader_expectation": {"tension": 0.5, "novelty": 0.15, "closure": 0.2, "ambiguity": 0.15},
            "confidence": "rule_based",
            "cliffhanger_type": "emotional",
            "release_pattern": "gentle",
        }

        patch = adjustment.to_contract_patch()

        # Merge: patch overrides only
        merged = dict(base_contract)
        merged.update(patch)
        merged["_last_adjusted"] = adjustment.generated_at
        merged["_adjustment_reason"] = adjustment.reason

        # In production: write merged to contract_path
        # if contract_path:
        #     import json
        #     with open(contract_path, 'w') as f:
        #         json.dump(merged, f, indent=2, ensure_ascii=False)

        self.session.role_notes = (
            self.session.role_notes or ""
        ) + f"\n[CONTRACT_ADJUSTED] {adjustment.adjustment_id}: {adjustment.reason}"

        return merged

    def run_multi_chapter_with_trend_watch(
        self,
        num_chapters: int = 5,
        genre: str = "romance",
        total_chapters: int = 40,
        trend_check_interval: int = 3,
    ) -> dict[str, Any]:
        """Run multiple chapters WITH contract-level trend watching.

        Every trend_check_interval chapters, OCOS scans the accumulated
        feedback for systemic trends. If found, it adjusts the
        NarrativeContract before continuing.

        This is the full engine-level self-improvement loop:
          Write + Analyze → Detect Trends → Adjust Contract → Write more
        """
        adjustments_applied: list[dict] = []
        trend_log: list[dict] = []

        for ch in range(1, num_chapters + 1):
            context = [
                f"Writing {genre} novel, chapter {ch}/{total_chapters}",
                f"Previous quality: {self.session.feedback.quality_score if self.session.feedback else 'N/A'}",
            ]
            self.run_full_cycle(
                context_chunks=context,
                genre=genre,
                chapter_number=ch,
                total_chapters=total_chapters,
            )

            # Periodic trend check
            if ch % trend_check_interval == 0 and ch >= 3:
                trends = self.feedback_loop.analyze_cross_chapter_trends()
                trend_log.append({"chapter": ch, "trends": trends})

                if trends:
                    # Reconstruct TrendSignal from dicts
                    trend_signals = []
                    for td in trends:
                        from ocos.opentale_bridge.trend_analyzer import TrendSignal
                        ts = TrendSignal(
                            trend_id=td["trend_id"],
                            description=td.get("description", ""),
                            confidence=td.get("confidence", 0),
                            affected_dimensions=td.get("affected_dimensions", []),
                            evidence=td.get("evidence", []),
                            severity=td.get("severity", "warn"),
                        )
                        trend_signals.append(ts)

                    adjustment = self.translator.translate_adjustment(
                        trend_signals,
                        adjustment_id=f"ocos-trend-ch{ch}-{uuid.uuid4().hex[:6]}",
                    )

                    if not adjustment.is_empty():
                        merged = self.apply_contract_adjustment(adjustment)
                        adjustments_applied.append(adjustment.to_dict())

        return {
            "chapters_written": num_chapters,
            "adjustments_applied": len(adjustments_applied),
            "adjustments": adjustments_applied,
            "trend_log": trend_log,
            "final_contract": adjustments_applied[-1]["contract_patch"] if adjustments_applied else None,
        }
