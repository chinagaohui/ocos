"""Phase 59: OCOS Decision → OpenTale ChapterBlueprint Translator.

Converts structured OCOS cognitive decisions into OpenTale's ChapterBlueprint format.
Pure rule-based — no LLM calls. Respects OpenTale's NarrativeContract architecture.
"""

from __future__ import annotations

from typing import Any

from ocos.opentale_bridge.bridge_model import (
    OcosDecision, TranslationResult, ContractAdjustment,
)
from ocos.opentale_bridge.trend_analyzer import TrendSignal


class DecisionTranslator:
    """Translates OCOS Decisions into OpenTale ChapterBlueprint dicts.

    The translator acts as the "Hermes" intermediary, converting the brain's
    abstract decisions into concrete writing instructions for the hand (OpenTale).
    """

    # ── Focus → Narrative Strategy ──

    FOCUS_TO_PRIMARY_DRIVER = {
        "relationship": "relationship",
        "plot": "truth",
        "character": "power",
        "world": "mystery",
        "action": "truth",
        "introspection": "power",
    }

    # ── Pacing → Rhythm Configuration ──

    PACING_TO_RHYTHM = {
        "accelerate": {"scene_length": "short", "sentence_style": "crisp", "paragraph_density": "sparse"},
        "decelerate": {"scene_length": "long", "sentence_style": "flowing", "paragraph_density": "dense"},
        "maintain":   {"scene_length": "medium", "sentence_style": "balanced", "paragraph_density": "medium"},
    }

    # ── Tone → Emotional Curve ──

    TONE_TO_EMOTION_CURVE = {
        "tension":    "ratchet",
        "warmth":     "resonance",
        "melancholy": "catharsis",
        "suspense":   "oscillation",
        "joy":        "resonance",
        "anger":      "ratchet",
        "fear":       "oscillation",
    }

    # ── Cliffhanger → Ending Type ──

    CLIFFHANGER_TO_ENDING = {
        "emotional":  {"type": "emotional", "release_pattern": "gentle"},
        "plot":       {"type": "plot", "release_pattern": "abrupt"},
        "revelation": {"type": "revelation", "release_pattern": "delayed"},
        "none":       {"type": "resolution", "release_pattern": "complete"},
    }

    def translate(self, decision: OcosDecision, genre: str = "romance",
                  chapter_number: int = 1, total_chapters: int = 40) -> TranslationResult:
        """Convert an OCOS Decision into an OpenTale ChapterBlueprint dict.

        Args:
            decision: OCOS's cognitive decision
            genre: target genre for the blueprint
            chapter_number: which chapter
            total_chapters: total planned chapters

        Returns:
            TranslationResult with the blueprint dict ready for OpenTale's Writer.
        """
        notes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Validate
        if not decision.primary_focus:
            errors.append("primary_focus is empty — using default 'relationship'")
            decision.primary_focus = "relationship"
        if not decision.emotional_tone:
            warnings.append("emotional_tone not set — defaulting to 'tension'")
            decision.emotional_tone = "tension"
        if not decision.pacing_directive:
            decision.pacing_directive = "maintain"

        # ── Core Blueprint Fields ──
        blueprint: dict[str, Any] = {
            "chapter_number": chapter_number,
            "title": decision.chapter_goal[:40] if decision.chapter_goal else f"Chapter {chapter_number}",
            "genre": genre,
            "word_target": decision.word_target or 3000,

            # Chapter position context
            "chapter_position": {
                "current": chapter_number,
                "total": total_chapters,
                "phase": self._determine_phase(chapter_number, total_chapters),
            },
        }

        # ── Narrative Strategy (NarrativeContract-aligned) ──
        blueprint["narrative_strategy"] = {
            "primary_driver": self.FOCUS_TO_PRIMARY_DRIVER.get(
                decision.primary_focus, "relationship"),
            "chapter_focus": {
                "relationship": 6 if decision.primary_focus == "relationship" else 2,
                "plot": 2,
                "world": 1,
                "character": 1,
            },
            "conflict_priority": {
                "interpersonal": 7,
                "external": 2,
                "internal": 1,
            },
            "scene_distribution": {
                "action": 1,
                "interpersonal": 6 if decision.primary_focus == "relationship" else 3,
                "reflection": 2,
                "exposition": 1,
            },
            "pov_policy": {
                "type": "single" if not decision.pov_character else "dual",
                "primary": decision.pov_character or "protagonist",
                "switching_rule": "chapter_boundary",
            },
        }
        notes.append("narrative_strategy derived from primary_focus")

        # ── Rhythm Profile ──
        blueprint["rhythm_profile"] = self.PACING_TO_RHYTHM.get(
            decision.pacing_directive, self.PACING_TO_RHYTHM["maintain"])
        blueprint["rhythm_profile"]["pacing_directive"] = decision.pacing_directive

        # ── Emotion Curve ──
        blueprint["emotion_curve"] = self.TONE_TO_EMOTION_CURVE.get(
            decision.emotional_tone, "oscillation")

        # ── Cliffhanger ──
        end_cfg = self.CLIFFHANGER_TO_ENDING.get(
            decision.cliffhanger_type or "emotional",
            self.CLIFFHANGER_TO_ENDING["emotional"])
        blueprint["cliffhanger"] = end_cfg

        # ── Conflict Target ──
        blueprint["conflict_target"] = {
            "type": "interpersonal",
            "goal": decision.conflict_instruction or "Advance the central relationship conflict",
            "intensity": 0.7,
        }

        # ── Scene Blueprints ──
        blueprint["scenes"] = self._build_scenes(decision)

        # ── Character Instructions ──
        blueprint["character_instructions"] = decision.character_instructions or {}

        # ── Key Directives (from decision.reasoning) ──
        blueprint["directives"] = {
            "chapter_goal": decision.chapter_goal or f"Write chapter {chapter_number}",
            "forbidden": decision.forbidden_elements,
            "key_themes": decision.key_scenes,
            "reasoning": decision.reasoning[:500] if decision.reasoning else "",
        }

        # ── OCOS Metadata ──
        blueprint["_ocos_metadata"] = {
            "decision_id": decision.decision_id,
            "confidence": decision.confidence,
            "timestamp": decision.timestamp,
        }

        return TranslationResult(
            success=len(errors) == 0,
            blueprint=blueprint,
            translation_notes=notes,
            warnings=warnings,
            errors=errors,
        )

    def _determine_phase(self, chapter: int, total: int) -> str:
        ratio = chapter / max(total, 1)
        if ratio <= 0.15:
            return "setup"
        elif ratio <= 0.25:
            return "inciting"
        elif ratio <= 0.50:
            return "rising_action"
        elif ratio <= 0.75:
            return "climax_approach"
        elif ratio <= 0.90:
            return "climax"
        else:
            return "resolution"

    def _build_scenes(self, decision: OcosDecision) -> list[dict]:
        """Build scene blueprints from OCOS decision."""
        default_scenes = [
            {"type": "opening", "goal": "Establish chapter mood and POV", "word_budget": 500},
            {"type": "development", "goal": decision.chapter_goal or "Advance the story", "word_budget": 1500},
            {"type": "climax", "goal": "Chapter emotional or plot peak", "word_budget": 700},
            {"type": "resolution", "goal": "Close chapter, set cliffhanger", "word_budget": 300},
        ]

        # If OCOS specified key scenes, override defaults
        if decision.key_scenes:
            result = []
            for i, scene_type in enumerate(decision.key_scenes[:4]):
                result.append({
                    "type": scene_type,
                    "goal": f"Execute {scene_type} scene",
                    "word_budget": decision.word_target // max(len(decision.key_scenes), 1),
                })
            return result

        return default_scenes

    # ═══ Phase 59-j: Trend → Contract Adjustment ═══

    # Mapping: trend_id → contract adjustment strategy
    TREND_TO_CONTRACT_RULE: dict[str, dict[str, Any]] = {
        "quality_decay": {
            "action": "confidence_override",
            "value": "llm_driven",
            "reason": "System decay — enable LLM-driven variance to escape local minima",
        },
        "chronic_emotional_curve": {
            "action": "emotion_curve+resonance",
            "curve": "oscillation",
            "resonance_delta": 0.1,
            "reason": "Emotional flatness — switch to oscillation curve, raise resonance target",
        },
        "monotone_emotional": {
            "action": "emotion_curve_override",
            "curve": "catharsis",
            "reason": "Monotone emotional curve — switch to catharsis for larger swings",
        },
        "chronic_character_coherence": {
            "action": "chapter_focus+character",
            "focus_delta": {"character": 1},
            "pov_tighten": True,
            "reason": "Character inconsistency — increase character focus, tighten POV",
        },
        "chronic_genre_compliance": {
            "action": "scene_distribution+genre",
            "scene_delta": {"action": -0.5, "interpersonal": 1, "reflection": 0.5},
            "reason": "Genre drift — shift scenes toward interpersonal, add reflection",
        },
        "chronic_narrative_density": {
            "action": "scene_distribution",
            "scene_delta": {"reflection": 1},
            "reason": "Narrative too thin — increase reflection scene weight",
        },
        "chronic_language_quality": {
            "action": "confidence_override",
            "value": "llm_driven",
            "reason": "Prose quality low — switch to LLM-driven mode for richer language",
        },
        "dialogue_imbalance": {
            "action": "scene_distribution",
            "scene_delta": {"reflection": 1, "interpersonal": -1},
            "reason": "Dialogue-heavy — shift toward reflection and action",
        },
        "genre_drift": {
            "action": "scene_distribution+genre",
            "scene_delta": {"action": -1, "interpersonal": 2, "reflection": 0.5},
            "reason": "Genre identity fading — boost genre-typical scene patterns",
        },
    }

    def translate_adjustment(
        self,
        trends: list[TrendSignal],
        adjustment_id: str = "",
    ) -> ContractAdjustment:
        """Convert cross-chapter TrendSignals into a ContractAdjustment.

        This is the engine-level counterpart of translate(). Instead of
        creating a ChapterBlueprint for one chapter, it patches OpenTale's
        NarrativeContract to fix systemic quality issues.

        Args:
            trends: TrendSignals from TrendAnalyzer.analyze()
            adjustment_id: Unique ID (auto-generated if empty)

        Returns:
            ContractAdjustment ready to be written to narrative_contract.json.
        """
        from ocos.opentale_bridge.ocos_activation import activate
        activate("A2_contract_adjustment")
        import time

        adj = ContractAdjustment(
            adjustment_id=adjustment_id or f"ocos-adj-{int(time.time())}",
            triggered_by=[t.trend_id for t in trends],
            generated_at=str(int(time.time())),
        )

        if not trends:
            adj.reason = "No trends detected — no adjustment needed"
            return adj

        # Apply rules for each trend
        rules_applied: list[str] = []
        for trend in trends:
            rule = self.TREND_TO_CONTRACT_RULE.get(trend.trend_id)
            if not rule:
                continue

            action = rule["action"]
            rules_applied.append(f"{trend.trend_id}→{action}")

            if action == "confidence_override":
                adj.confidence_override = rule["value"]

            elif action == "emotion_curve+resonance":
                adj.emotion_curve_override = rule["curve"]
                adj.emotional_resonance_target = min(0.85, 0.6 + rule.get("resonance_delta", 0.1))

            elif action == "emotion_curve_override":
                adj.emotion_curve_override = rule["curve"]

            elif action == "chapter_focus+character":
                delta = rule.get("focus_delta", {})
                adj.chapter_focus_patch.update(delta)
                if rule.get("pov_tighten"):
                    adj.pov_policy_tightening = True

            elif action == "scene_distribution+genre":
                delta = rule.get("scene_delta", {})
                adj.scene_distribution_patch.update(delta)

            elif action == "scene_distribution":
                delta = rule.get("scene_delta", {})
                adj.scene_distribution_patch.update(delta)

        # Severity: take the max from all trends
        severities = {"info": 0, "warn": 1, "critical": 2}
        max_sev = "info"
        for t in trends:
            if severities.get(t.severity, 0) > severities.get(max_sev, 0):
                max_sev = t.severity
        adj.severity = max_sev

        adj.reason = "; ".join(rules_applied) if rules_applied else "No applicable rules found"
        return adj
