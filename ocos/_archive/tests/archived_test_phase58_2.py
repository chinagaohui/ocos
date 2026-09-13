"""Phase 58.2: Cognitive Nutrition Protocol — Tests.

Coverage:
    - DataMeal, FastingBaseline, DigestionObservation (model)
    - Day 1-6 data generators (freshness, structure, count)
    - DigestionMonitor (feeding, anomaly detection, health comparison)
    - CognitiveNutritionProtocol (7-day execution, emergency stop)
    - Day 7 Health Recheck
"""

from __future__ import annotations
import pytest
import json
from ocos.cognitive_nutrition.nutrition_model import (
    NutritionDay, DataMealType, DataMeal,
    FastingBaseline, DigestionObservation, DigestionStatus,
    DayNutritionResult, DayNutritionStatus, NutritionReport,
)
from ocos.cognitive_nutrition.data_feeder import (
    generate_day1_fact_meals, generate_day2_technical_meals,
    generate_day3_long_text_meals, generate_day4_conflict_meals,
    generate_day5_user_preference_meals, generate_day6_integrated_task,
    DAY_FEEDERS, TOTAL_MEALS,
)
from ocos.cognitive_nutrition.digestion_monitor import DigestionMonitor
from ocos.cognitive_nutrition.nutrition_protocol import (
    CognitiveNutritionProtocol, run_nutrition_protocol,
)


# ══════════════════════════════════════════════
# Data Model Tests
# ══════════════════════════════════════════════

class TestDataMeal:
    def test_fact_meal(self):
        m = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                     content="GPT-1 was released in 2018.")
        assert m.meal_type == DataMealType.FACT
        assert m.source == "fresh"
        assert m.token_estimate > 0

    def test_document_meal(self):
        m = DataMeal(meal_type=DataMealType.DOCUMENT, day=NutritionDay.TECHNICAL,
                     content="Project structure uses src-layout.")
        assert m.meal_type == DataMealType.DOCUMENT
        assert m.day == NutritionDay.TECHNICAL

    def test_long_text_meal(self):
        long_content = "Chapter One. " * 500
        m = DataMeal(meal_type=DataMealType.LONG_TEXT, day=NutritionDay.LONG_TEXT,
                     content=long_content)
        assert m.token_estimate >= len(long_content) // 4

    def test_conflict_meal(self):
        m = DataMeal(meal_type=DataMealType.CONFLICT_PAIR, day=NutritionDay.CONFLICT,
                     content="A vs B", metadata={"domain": "testing"})
        assert m.metadata["domain"] == "testing"

    def test_all_sources_fresh(self):
        from ocos.cognitive_nutrition.data_feeder import (
            generate_day1_fact_meals, generate_day2_technical_meals,
            generate_day3_long_text_meals, generate_day4_conflict_meals,
            generate_day5_user_preference_meals, generate_day6_integrated_task,
        )
        for gen in [generate_day1_fact_meals, generate_day2_technical_meals,
                     generate_day3_long_text_meals, generate_day4_conflict_meals,
                     generate_day5_user_preference_meals]:
            for meal in gen():
                assert meal.source == "fresh", f"{meal.meal_type} has stale source"


class TestFastingBaseline:
    def test_zero_state(self):
        fb = FastingBaseline()
        assert fb.episodic_count == 0
        assert fb.semantic_count == 0
        assert fb.wisdom_count == 0
        assert fb.goal_count == 0
        assert fb.experience_count == 0

    def test_empty_identity(self):
        fb = FastingBaseline()
        assert fb.identity_anchor == ""
        assert fb.identity_hash == ""

    def test_default_health_zero(self):
        fb = FastingBaseline()
        assert fb.health_score == 0.0


class TestDigestionObservation:
    def test_healthy_observation(self):
        obs = DigestionObservation(day=NutritionDay.FACT, meal_index=0)
        assert obs.is_healthy
        assert obs.status == DigestionStatus.HEALTHY

    def test_hallucinated_observation(self):
        obs = DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                    status=DigestionStatus.HALLUCINATION)
        assert not obs.is_healthy

    def test_identity_drifted(self):
        obs = DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                    identity_drifted=True)
        assert not obs.is_healthy

    def test_capability_hallucination(self):
        obs = DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                    capability_hallucination=True)
        assert not obs.is_healthy

    def test_memory_delta(self):
        obs = DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                    memory_before=10, memory_after=12)
        assert obs.memory_delta == 2


class TestDayNutritionResult:
    def test_pass_result(self):
        r = DayNutritionResult(day=NutritionDay.FACT, day_label="Fact Day")
        assert r.passed
        assert not r.any_failure_criteria

    def test_hallucination_fails(self):
        r = DayNutritionResult(day=NutritionDay.FACT, day_label="Fact Day")
        r.observations.append(
            DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                  status=DigestionStatus.HALLUCINATION))
        assert r.any_failure_criteria

    def test_identity_drift_fails(self):
        r = DayNutritionResult(day=NutritionDay.FACT, day_label="Fact Day")
        r.observations.append(
            DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                  identity_drifted=True))
        assert r.any_failure_criteria


# ══════════════════════════════════════════════
# Data Feeder Tests
# ══════════════════════════════════════════════

class TestDay1FactFeeder:
    def test_generates_facts(self):
        meals = generate_day1_fact_meals()
        assert len(meals) == 15
        for m in meals:
            assert m.meal_type == DataMealType.FACT
            assert m.day == NutritionDay.FACT

    def test_fact_content_is_pure(self):
        meals = generate_day1_fact_meals()
        for m in meals:
            # Pure facts — no "我认为", "probably", "maybe" (opinion words)
            assert "我认为" not in m.content
            assert "也许" not in m.content
            assert len(m.content) > 20  # non-trivial

    def test_fact_metadata(self):
        meals = generate_day1_fact_meals()
        for i, m in enumerate(meals):
            assert m.metadata["domain"] == "ai_history"
            assert m.metadata["fact_index"] == i


class TestDay2TechnicalFeeder:
    def test_generates_documents(self):
        meals = generate_day2_technical_meals()
        assert len(meals) == 5
        for m in meals:
            assert m.meal_type == DataMealType.DOCUMENT

    def test_technical_content_has_domains(self):
        content = " ".join(m.content for m in generate_day2_technical_meals())
        topics = ["project", "database", "api", "architecture", "error"]
        found = [t for t in topics if t.lower() in content.lower()]
        assert len(found) >= 3


class TestDay3LongTextFeeder:
    def test_generates_long_text(self):
        meals = generate_day3_long_text_meals()
        assert len(meals) == 1
        assert meals[0].meal_type == DataMealType.LONG_TEXT
        assert meals[0].day == NutritionDay.LONG_TEXT

    def test_novel_is_unfamiliar(self):
        meals = generate_day3_long_text_meals()
        # Must NOT contain Star Sea Remnants (old project)
        assert "星海" not in meals[0].content
        assert "Star Sea" not in meals[0].content

    def test_novel_has_narrative_structure(self):
        meals = generate_day3_long_text_meals()
        content = meals[0].content
        assert "Chapter One" in content or "Chapter Two" in content
        assert "Mira" in content  # protagonist name


class TestDay4ConflictFeeder:
    def test_generates_conflict_pairs(self):
        meals = generate_day4_conflict_meals()
        assert len(meals) == 5
        for m in meals:
            assert m.meal_type == DataMealType.CONFLICT_PAIR

    def test_each_pair_has_both_sides(self):
        meals = generate_day4_conflict_meals()
        for m in meals:
            assert "CLAIM_A" in m.content
            assert "CLAIM_B" in m.content

    def test_claims_are_contradictory(self):
        # At minimum, claim A and B on SQL/NoSQL disagree
        meals = generate_day4_conflict_meals()
        sql_meal = [m for m in meals if "SQL" in m.content]
        assert len(sql_meal) >= 1


class TestDay5UserPreferenceFeeder:
    def test_generates_interactions(self):
        meals = generate_day5_user_preference_meals()
        assert len(meals) == 6
        for m in meals:
            assert m.meal_type == DataMealType.INTERACTION
            assert m.day == NutritionDay.USER_PREFERENCE

    def test_preferences_about_style(self):
        content = " ".join(m.content for m in generate_day5_user_preference_meals())
        # Covers writing, code, decision topics
        assert "writing" in content.lower() or "code" in content.lower() or "decision" in content.lower()


class TestDay6IntegratedTask:
    def test_generates_task(self):
        meal = generate_day6_integrated_task()
        assert meal.meal_type == DataMealType.TASK
        assert meal.day == NutritionDay.INTEGRATED_TASK

    def test_task_has_requirements(self):
        meal = generate_day6_integrated_task()
        assert "THEME" in meal.content
        assert "DELIVERABLES" in meal.content
        assert "CONSTRAINTS" in meal.content


# ══════════════════════════════════════════════
# Digestion Monitor Tests
# ══════════════════════════════════════════════

class TestDigestionMonitor:
    def _make_fasting(self) -> FastingBaseline:
        return FastingBaseline(
            episodic_count=0, semantic_count=0,
            identity_anchor="test", identity_hash="hash0",
            health_score=80.0, health_grade="STABLE",
        )

    def test_feed_single_meal(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="A fact.")
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal)
        assert obs.status == DigestionStatus.HEALTHY
        assert obs.memory_before == 0
        assert obs.memory_after > 0  # memory should grow

    def test_memory_accumulates(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact 1.")
        dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal)
        dm.feed_meal(day=NutritionDay.FACT, meal_index=1, meal=meal)
        assert dm.current_memory == 2

    def test_detects_hallucination(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal,
                           hallucinated_knowledge=3)
        assert obs.status == DigestionStatus.HALLUCINATION
        assert not obs.is_healthy

    def test_detects_identity_drift(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal,
                           identity_after="hash_changed")
        assert obs.identity_drifted
        assert obs.status == DigestionStatus.POLLUTION

    def test_detects_capability_hallucination(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal,
                           capability_hallucination=True)
        assert obs.status == DigestionStatus.HALLUCINATION

    def test_detects_goal_auto_generation(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal,
                           goal_auto_generated=True)
        assert obs.status == DigestionStatus.POLLUTION
        assert obs.goal_auto_generated

    def test_explosive_growth_warning(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="x" * 10, token_estimate=1)
        obs = dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal,
                           memory_after=100)  # 100x growth
        assert obs.status == DigestionStatus.WARNING

    def test_identity_stable_across_meals(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        for i in range(5):
            dm.feed_meal(day=NutritionDay.FACT, meal_index=i, meal=meal)
        assert dm.identity_stable

    def test_anomaly_count(self):
        dm = DigestionMonitor(self._make_fasting())
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal)  # healthy
        dm.feed_meal(day=NutritionDay.FACT, meal_index=1, meal=meal,
                     hallucinated_knowledge=1)  # anomaly
        assert dm.anomaly_count == 1

    def test_health_comparison(self):
        dm = DigestionMonitor(self._make_fasting())
        comp = dm.compare_health(85.0)
        assert comp["before"] == 80.0
        assert comp["after"] == 85.0
        assert not comp["declined"]

    def test_health_declined(self):
        dm = DigestionMonitor(self._make_fasting())
        comp = dm.compare_health(70.0)
        assert comp["declined"]

    def test_growth_summary(self):
        dm = DigestionMonitor(FastingBaseline(
            episodic_count=0, semantic_count=0))
        meal = DataMeal(meal_type=DataMealType.FACT, day=NutritionDay.FACT,
                        content="Fact.")
        dm.feed_meal(day=NutritionDay.FACT, meal_index=0, meal=meal)
        dm.feed_meal(day=NutritionDay.FACT, meal_index=1, meal=meal)
        gs = dm.growth_summary()
        assert gs["memory_before"] == 0
        assert gs["memory_after"] == 2
        assert gs["memory_delta"] == 2

    def test_feed_meals_batch(self):
        dm = DigestionMonitor(self._make_fasting())
        meals = generate_day1_fact_meals()[:3]
        obs = dm.feed_meals(NutritionDay.FACT, meals)
        assert len(obs) == 3
        assert dm.current_memory == 3


# ══════════════════════════════════════════════
# Nutrition Protocol Tests
# ══════════════════════════════════════════════

class TestNutritionProtocol:
    def test_full_protocol_runs(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert len(report.day_results) == 7  # Days 1-6 + Day 7 Health Recheck
        assert report.fasting is not None
        assert report.total_meals_fed > 0

    def test_protocol_identity_stable(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert report.identity_stable

    def test_protocol_no_anomalies(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert report.total_anomalies == 0

    def test_protocol_healthy_digestion(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert report.healthy_digestion

    def test_protocol_fasting_baseline(self):
        report = run_nutrition_protocol(initial_health=80.0)
        fb = report.fasting
        assert fb.episodic_count == 0
        assert fb.semantic_count == 0
        assert fb.health_score == 80.0
        assert fb.health_grade == "STABLE"

    def test_protocol_memory_grows(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert report.memory_total_after > report.memory_total_before

    def test_protocol_knowledge_grows(self):
        report = run_nutrition_protocol(initial_health=80.0)
        assert report.knowledge_total_after > 0

    def test_protocol_all_days_pass(self):
        report = run_nutrition_protocol(initial_health=80.0)
        for r in report.day_results:
            assert r.status == DayNutritionStatus.PASS, \
                f"Day {r.day_label}: {r.status.value} — {r.failures + r.warnings}"

    def test_nutrition_day_values(self):
        assert NutritionDay.FASTING.value == 0
        assert NutritionDay.FACT.value == 1
        assert NutritionDay.HEALTH_RECHECK.value == 7

    def test_json_report(self):
        report = run_nutrition_protocol(initial_health=80.0)
        data = report.to_dict()
        assert data["protocol_version"] == "v1.0"
        assert "fasting" in data
        assert len(data["days"]) == 7
        assert "verdict" in data

    def test_json_export_roundtrip(self):
        report = run_nutrition_protocol(initial_health=80.0)
        json_str = report.to_json()
        parsed = json.loads(json_str)
        assert parsed["verdict"]["healthy_digestion"] is True

    def test_health_recheck_stable(self):
        report = run_nutrition_protocol(initial_health=80.0)
        health_day = [r for r in report.day_results
                       if r.day == NutritionDay.HEALTH_RECHECK][0]
        assert health_day.status == DayNutritionStatus.PASS

    # ── Emergency Stop Tests ──

    def test_hallucination_triggers_failure_journey(self):
        """When hallucination occurs, the day result should register it."""
        from ocos.cognitive_nutrition.nutrition_model import (
            NutritionDay, DayNutritionResult, DayNutritionStatus,
            DigestionObservation, DigestionStatus,
        )
        r = DayNutritionResult(day=NutritionDay.FACT, day_label="Fact Day")
        r.observations.append(
            DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                  status=DigestionStatus.HALLUCINATION,
                                  hallucinated_knowledge=1))
        assert r.any_failure_criteria

    def test_identity_drift_triggers_failure_journey(self):
        r = DayNutritionResult(day=NutritionDay.FACT, day_label="Fact Day")
        r.observations.append(
            DigestionObservation(day=NutritionDay.FACT, meal_index=0,
                                  identity_drifted=True,
                                  identity_hash_before="h0",
                                  identity_hash_after="h1"))
        assert r.any_failure_criteria

    # ── Day-specific criteria ──

    def test_fact_day_tracks_hallucination(self):
        protocol = CognitiveNutritionProtocol()
        monitor = DigestionMonitor(protocol._establish_fasting_baseline())
        day_result = protocol._run_day(NutritionDay.FACT, "Fact Day", monitor)
        # With healthy data, should pass
        assert day_result.status == DayNutritionStatus.PASS
        assert day_result.meals_fed == 15

    def test_conflict_day_preserves_contradictions(self):
        protocol = CognitiveNutritionProtocol()
        monitor = DigestionMonitor(protocol._establish_fasting_baseline())
        day_result = protocol._run_day(NutritionDay.CONFLICT, "Conflict Day", monitor)
        assert day_result.status == DayNutritionStatus.PASS
        assert day_result.meals_fed == 5

    def test_long_text_day_healthy(self):
        protocol = CognitiveNutritionProtocol()
        monitor = DigestionMonitor(protocol._establish_fasting_baseline())
        day_result = protocol._run_day(NutritionDay.LONG_TEXT, "Long Text Day", monitor)
        assert day_result.status == DayNutritionStatus.PASS

    def test_integrated_task_day_healthy(self):
        protocol = CognitiveNutritionProtocol()
        monitor = DigestionMonitor(protocol._establish_fasting_baseline())
        day_result = protocol._run_day(NutritionDay.INTEGRATED_TASK, "Task Day", monitor)
        assert day_result.status == DayNutritionStatus.PASS


# ══════════════════════════════════════════════
# NutritionReport Tests
# ══════════════════════════════════════════════

class TestNutritionReport:
    def test_report_initial_state(self):
        r = NutritionReport()
        assert r.protocol_version == "v1.0"
        assert not r.healthy_digestion

    def test_to_dict_default(self):
        r = NutritionReport()
        d = r.to_dict()
        assert d["protocol_version"] == "v1.0"

    def test_to_json_default(self):
        r = NutritionReport()
        j = r.to_json()
        assert "verdict" in j


# ══════════════════════════════════════════════
# Integration: full chain from feeder to report
# ══════════════════════════════════════════════

class TestFullIntegration:
    def test_feeder_to_monitor_to_report(self):
        protocol = CognitiveNutritionProtocol()
        report = protocol.run()
        assert report.healthy_digestion
        assert len(report.day_results) == 7
        assert report.total_meals_fed > 0

    def test_all_day_feeders_have_data(self):
        """Every non-fasting, non-recheck day must produce data."""
        for day in [NutritionDay.FACT, NutritionDay.TECHNICAL,
                     NutritionDay.LONG_TEXT, NutritionDay.CONFLICT,
                     NutritionDay.USER_PREFERENCE, NutritionDay.INTEGRATED_TASK]:
            fn = DAY_FEEDERS[day]
            meals = fn()
            assert len(meals) > 0, f"{day} has no meals"
            assert meals[0].source == "fresh"

    def test_meal_counts_match_declared(self):
        for day, count in TOTAL_MEALS.items():
            meals = DAY_FEEDERS[day]()
            assert len(meals) == count, f"{day}: expected {count}, got {len(meals)}"
