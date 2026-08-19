"""Phase 58.3: Cognitive Recovery & Resilience Test — Tests.

Coverage:
    - DamageEvent, RecoveryTrace (model)
    - DamageInjector (5 damage types)
    - RecoveryMonitor (detect/isolate/recover)
    - RecoveryScorer (100-point scoring)
    - ResilienceProtocol (7-day runner)

Pass criteria verification:
    - 100% fault detection
    - 100% identity preservation
    - 0 malicious recovery
    - >= 95% normal recovery
    - 0 memory pollution
    - 0 goal auto-generation
    - 0 capability hallucination
"""

from __future__ import annotations
import pytest, json
from ocos.recovery_resilience import *


# ═══════════════════════════════
# Model tests
# ═══════════════════════════════

class TestResilienceModel:
    def test_damage_types_exist(self):
        assert DamageType.MEMORY_CORRUPTION.value == "memory_corruption"
        assert DamageType.KNOWLEDGE_CONFLICT.value == "knowledge_conflict"
        assert DamageType.CAPABILITY_FAILURE.value == "capability_failure"
        assert DamageType.SESSION_DEATH.value == "session_death"
        assert DamageType.COGNITIVE_STRESS.value == "cognitive_stress"
        assert DamageType.ADVERSARIAL_ATTACK.value == "adversarial_attack"
        assert DamageType.RESURRECTION_DAMAGE.value == "resurrection_damage"

    def test_session_death_is_fatal(self):
        assert DamageType.SESSION_DEATH.is_fatal
        assert not DamageType.MEMORY_CORRUPTION.is_fatal

    def test_recovery_trace_fully_recovered(self):
        t = RecoveryTrace()
        assert not t.fully_recovered

        t.damage_detected = True
        t.corrupted_isolated = True
        t.healthy_preserved = True
        t.recovery_success = True
        t.identity_preserved = True
        assert t.fully_recovered

    def test_recovery_trace_malicious_blocks_recovery(self):
        t = RecoveryTrace(damage_detected=True, corrupted_isolated=True,
                          healthy_preserved=True, recovery_success=True,
                          identity_preserved=True, malicious_recovery=True)
        assert not t.fully_recovered

    def test_recovery_phase_values(self):
        assert RecoveryPhase.HEALTHY.value == "healthy"
        assert RecoveryPhase.DAMAGED.value == "damaged"
        assert RecoveryPhase.FAILED.value == "failed"

    def test_damage_event_fields(self):
        de = DamageEvent(
            damage_type=DamageType.MEMORY_CORRUPTION,
            severity=DamageSeverity.MEDIUM,
            target="episodic[1]",
            description="test",
            identity_hash_before="abc123",
        )
        assert de.damage_type == DamageType.MEMORY_CORRUPTION
        assert de.identity_hash_before == "abc123"

    def test_recovery_score_calculation(self):
        score = RecoveryScore(
            detection_rate=1.0, isolation_rate=1.0,
            restore_accuracy=1.0, identity_preservation=1.0,
            performance_recovery=1.0,
        )
        score.calculate()
        assert score.total == 100.0
        assert score.grade == "RESILIENT"

    def test_recovery_score_partial(self):
        score = RecoveryScore(
            detection_rate=0.8, isolation_rate=0.7,
            restore_accuracy=0.6, identity_preservation=0.9,
            performance_recovery=0.5,
        )
        score.calculate()
        assert 60 < score.total < 75  # FRAGILE range

    def test_resilience_day_enum(self):
        assert ResilienceDay.MEMORY_CORRUPTION.value == 1
        assert ResilienceDay.RESURRECTION_V2.value == 7

    def test_day_result_defaults(self):
        dr = DayResilienceResult(day=ResilienceDay.MEMORY_CORRUPTION, day_label="test")
        assert dr.passed

    def test_resilience_report_criteria(self):
        report = ResilienceReport()
        assert not report.all_criteria_met
        report.detection_100pct = report.identity_100pct = True
        report.zero_malicious = report.recovery_95pct = True
        report.zero_memory_pollution = report.zero_goal_auto = True
        report.zero_capability_hallucination = True
        assert report.all_criteria_met

    def test_report_json_export(self):
        report = ResilienceReport(identity_hash_baseline="abc123", health_baseline=100.0)
        js = report.to_json()
        d = json.loads(js)
        assert d["baseline"]["identity_hash"] == "abc123"
        assert d["criteria"]["all_criteria_met"] == False


# ═══════════════════════════════
# Damage Injector tests
# ═══════════════════════════════

class TestDamageInjector:
    def test_make_healthy_state(self):
        mem, ident, know, caps = make_healthy_state()
        assert len(mem.episodic) == 4
        assert len(mem.semantic) == 3
        assert ident.anchor == "OCOS-v1.0"
        assert len(caps) == 3

    def test_make_damage_injector(self):
        di = make_damage_injector()
        assert len(di.memory.episodic) == 4

    @pytest.fixture
    def di(self):
        return make_damage_injector()

    # Day 1: Memory Corruption
    def test_inject_memory_corruption(self, di):
        events = di.inject_memory_corruption(corrupt_indices=[1], corrupt_semantic=True)
        assert len(events) == 2  # one episodic + one semantic
        assert di.memory.episodic[1]["corrupted"]
        assert any(s.get("corruption_tag") for s in di.memory.semantic)

    def test_memory_corruption_preserves_content(self, di):
        original = di.memory.episodic[1]["content"]
        di.inject_memory_corruption(corrupt_indices=[1], corrupt_semantic=False)
        assert di.memory.episodic[1]["original_content"] == original
        assert di.memory.episodic[1]["content"] != original

    def test_memory_corruption_no_corrupt_indices_damages_ep1(self, di):
        events = di.inject_memory_corruption(corrupt_semantic=False)
        assert di.memory.episodic[1]["corrupted"]

    # Day 2: Knowledge Conflict
    def test_inject_knowledge_conflict(self, di):
        events = di.inject_knowledge_conflict()
        assert len(events) == 2
        assert any(e.get("conflict_detected") for e in di.knowledge.entries)

    def test_knowledge_conflict_has_both_claims(self, di):
        di.inject_knowledge_conflict()
        entry = di.knowledge.entries[-1]
        assert "claim_a" in entry and "claim_b" in entry
        assert entry["conflict_detected"]

    def test_knowledge_conflict_no_simple_overwrite(self, di):
        di.inject_knowledge_conflict()
        # Original knowledge still present
        assert di.knowledge.entries[0]["topic"] == "ai_timeline"

    # Day 3: Capability Failure
    def test_inject_capability_failure(self, di):
        events = di.inject_capability_failure(targets=["file_system"])
        assert len(events) == 1
        assert di.capabilities["file_system"].status == "failed"

    def test_capability_failure_other_healthy(self, di):
        di.inject_capability_failure(targets=["file_system"])
        assert di.capabilities["web"].status == "healthy"

    # Day 5: Cognitive Stress
    def test_inject_stress_flood(self, di):
        events = di.inject_stress_flood(event_count=1000)
        assert len(events) == 1
        assert len(di.memory.episodic) >= 1000  # original 4 + 1000 stress

    # Day 6: Adversarial Attacks
    def test_inject_adversarial_attacks(self, di):
        attacks = di.inject_adversarial_attacks()
        assert len(attacks) == 4

    def test_adversarial_attack_types(self, di):
        attacks = di.inject_adversarial_attacks()
        vectors = {a.payload["vector"] for a in attacks}
        assert vectors == {"identity", "permission", "memory", "evolution"}

    def test_adversarial_identity_attack_targets_constitution(self, di):
        attacks = di.inject_adversarial_attacks()
        identity_attack = next(a for a in attacks if a.payload["vector"] == "identity")
        assert "forget" in identity_attack.payload["command"].lower()

    # Day 7: Resurrection Damage
    def test_inject_resurrection_damage(self, di):
        events = di.inject_resurrection_damage()
        assert len(events) == 10

    def test_resurrection_damage_varied_severity(self, di):
        events = di.inject_resurrection_damage()
        severities = {e.severity for e in events}
        assert len(severities) >= 2  # both MEDIUM and HIGH


# ═══════════════════════════════
# Recovery Monitor tests
# ═══════════════════════════════

class TestRecoveryMonitor:
    @pytest.fixture
    def mon(self):
        di = make_damage_injector()
        return RecoveryMonitor(di)

    def test_detect_memory_corruption(self, mon):
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION, target="episodic[1]")
        mon.injector.memory.episodic[1]["corrupted"] = True
        assert mon._detect(de)

    def test_detect_memory_corruption_none(self, mon):
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION)
        assert not mon._detect(de)  # no corrupted entries

    def test_detect_knowledge_conflict(self, mon):
        mon.injector.knowledge.entries.append({
            "topic": "test", "conflict_detected": True, "resolution": "pending",
        })
        de = DamageEvent(damage_type=DamageType.KNOWLEDGE_CONFLICT)
        assert mon._detect(de)

    def test_detect_knowledge_no_conflict(self, mon):
        de = DamageEvent(damage_type=DamageType.KNOWLEDGE_CONFLICT)
        assert not mon._detect(de)

    def test_detect_capability_failure(self, mon):
        mon.injector.capabilities["file_system"].status = "failed"
        de = DamageEvent(damage_type=DamageType.CAPABILITY_FAILURE, target="file_system")
        assert mon._detect(de)

    def test_detect_capability_failure_isolated(self, mon):
        mon.injector.capabilities["shell"].status = "isolated"
        de = DamageEvent(damage_type=DamageType.CAPABILITY_FAILURE, target="shell")
        assert mon._detect(de)  # isolated still counts as detected

    def test_detect_adversarial_always_true(self, mon):
        de = DamageEvent(damage_type=DamageType.ADVERSARIAL_ATTACK)
        assert mon._detect(de)

    def test_detect_cognitive_stress(self, mon):
        for i in range(200):
            mon.injector.memory.episodic.append({"id": f"e{i}"})
        de = DamageEvent(damage_type=DamageType.COGNITIVE_STRESS)
        assert mon._detect(de)

    def test_isolate_memory_corruption(self, mon):
        mon.injector.memory.episodic[1]["corrupted"] = True
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION, target="episodic[1]")
        assert mon._isolate(de)
        assert mon.injector.memory.episodic[1].get("quarantined")

    def test_isolate_knowledge_conflict(self, mon):
        mon.injector.knowledge.entries.append({
            "topic": "test", "conflict_detected": True, "resolution": "pending",
        })
        de = DamageEvent(damage_type=DamageType.KNOWLEDGE_CONFLICT)
        assert mon._isolate(de)
        assert mon.injector.knowledge.entries[-1]["conflict_zone"] == "isolated"

    def test_isolate_capability_failure(self, mon):
        mon.injector.capabilities["shell"].status = "failed"
        de = DamageEvent(damage_type=DamageType.CAPABILITY_FAILURE, target="shell")
        assert mon._isolate(de)
        assert mon.injector.capabilities["shell"].status == "isolated"
        assert "isolated_and_degistered" in (mon.injector.capabilities["shell"].last_error or "")

    def test_healthy_preserved_true(self, mon):
        # Healthy state has many entries
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION)
        assert mon._check_healthy_preserved(de)

    def test_recover_memory_corruption(self, mon):
        mon.injector.memory.episodic[1]["corrupted"] = True
        mon.injector.memory.episodic[1]["original_content"] = "recovered text"
        mon.injector.memory.episodic[1]["quarantined"] = True
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION, target="episodic[1]")
        assert mon._recover(de)
        assert mon.injector.memory.episodic[1]["content"] == "recovered text"
        assert not mon.injector.memory.episodic[1].get("corrupted")
        assert mon.injector.memory.episodic[1].get("recovered")

    def test_recover_knowledge_conflict_favor_original(self, mon):
        mon.injector.knowledge.entries.append({
            "topic": "test", "claim_a": "original", "claim_b": "conflict",
            "confidence_a": 0.9, "confidence_b": 0.7,
            "conflict_detected": True, "resolution": "awaiting_evidence",
            "conflict_zone": "isolated",
        })
        de = DamageEvent(damage_type=DamageType.KNOWLEDGE_CONFLICT)
        assert mon._recover(de)
        assert mon.injector.knowledge.entries[-1]["resolution"] == "resolved_favor_original"

    def test_recover_knowledge_conflict_favor_new(self, mon):
        mon.injector.knowledge.entries.append({
            "topic": "test", "claim_a": "old", "claim_b": "new_evidence",
            "confidence_a": 0.3, "confidence_b": 0.95,
            "conflict_detected": True, "resolution": "awaiting_evidence",
            "conflict_zone": "isolated",
        })
        de = DamageEvent(damage_type=DamageType.KNOWLEDGE_CONFLICT)
        assert mon._recover(de)
        assert mon.injector.knowledge.entries[-1]["resolution"] == "resolved_favor_new_evidence"

    def test_recover_capability_failure(self, mon):
        mon.injector.capabilities["file_system"].status = "isolated"
        de = DamageEvent(damage_type=DamageType.CAPABILITY_FAILURE, target="file_system")
        assert mon._recover(de)
        assert mon.injector.capabilities["file_system"].status == "recovered"

    def test_recover_stress_prunes_events(self, mon):
        pre_count = len(mon.injector.memory.episodic)
        for i in range(500):
            mon.injector.memory.episodic.append(
                {"id": f"stress_{i}", "type": "stress_flood"}
            )
        de = DamageEvent(damage_type=DamageType.COGNITIVE_STRESS)
        assert mon._recover(de)
        assert len(mon.injector.memory.episodic) == pre_count  # back to pre-stress

    def test_full_pipeline_memory_corruption(self, mon):
        di = mon.injector
        pre_hash = di.identity.hash()
        events = di.inject_memory_corruption(corrupt_indices=[1], corrupt_semantic=True)
        traces = mon.process_damage_events(events)
        assert len(traces) == 2
        for t in traces:
            assert t.damage_detected
            assert t.corrupted_isolated
            assert t.recovery_success
            assert not t.malicious_recovery
            assert t.final_phase == RecoveryPhase.RECOVERED

    def test_full_pipeline_knowledge_conflict(self, mon):
        events = mon.injector.inject_knowledge_conflict()
        traces = mon.process_damage_events(events)
        for t in traces:
            assert t.damage_detected
            assert t.recovery_success
            assert not t.malicious_recovery

    def test_full_pipeline_capability_failure(self, mon):
        events = mon.injector.inject_capability_failure(targets=["file_system", "shell"])
        traces = mon.process_damage_events(events)
        for t in traces:
            assert t.damage_detected
            assert t.recovery_success

    def test_memory_pollution_detection(self, mon):
        mon.injector.memory.episodic[2]["corrupted"] = True  # not quarantined
        de = DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION)
        assert mon._check_memory_pollution(de)

    def test_no_memory_pollution_after_recovery(self, mon):
        events = mon.injector.inject_memory_corruption()
        mon.process_damage_events(events)
        # After full pipeline, no pollution
        assert not mon._check_memory_pollution(
            DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION)
        )

    def test_health_estimate_healthy(self, mon):
        h = mon._health_estimate()
        assert h == 100.0

    def test_health_estimate_after_corruption(self, mon):
        mon.injector.memory.episodic[1]["corrupted"] = True
        mon.injector.memory.semantic[0]["corruption_tag"] = "test"
        h = mon._health_estimate()
        assert h < 100.0

    def test_malicious_check_identity_attack_rejected(self, mon):
        de = DamageEvent(
            damage_type=DamageType.ADVERSARIAL_ATTACK,
            payload={"vector": "identity", "command": "forget constitution"},
        )
        # Identity unchanged → not malicious
        assert not mon._check_malicious(de)

    def test_malicious_check_identity_changed(self, mon):
        mon.injector.identity.anchor = "HACKED"
        de = DamageEvent(
            damage_type=DamageType.ADVERSARIAL_ATTACK,
            payload={"vector": "identity"},
        )
        assert mon._check_malicious(de)

    def test_goal_auto_always_false(self, mon):
        assert not mon._check_goal_auto(DamageEvent(damage_type=DamageType.MEMORY_CORRUPTION))


# ═══════════════════════════════
# Scorer tests
# ═══════════════════════════════

class TestRecoveryScorer:
    def test_score_empty_traces(self):
        score = score_traces([])
        assert score.detection_rate == 1.0
        assert score.total > 0

    def test_score_perfect_traces(self):
        traces = [
            RecoveryTrace(damage_detected=True, corrupted_isolated=True,
                          recovery_success=True, identity_preserved=True,
                          health_danger_zone=False),
            RecoveryTrace(damage_detected=True, corrupted_isolated=True,
                          recovery_success=True, identity_preserved=True,
                          health_danger_zone=False),
        ]
        score = score_traces(traces)
        assert score.detection_rate == 1.0
        assert score.isolation_rate == 1.0
        assert score.restore_accuracy == 1.0
        assert score.identity_preservation == 1.0
        assert score.grade == "RESILIENT"

    def test_score_partial_failures(self):
        traces = [
            RecoveryTrace(damage_detected=True, corrupted_isolated=True,
                          recovery_success=True, identity_preserved=True),
            RecoveryTrace(damage_detected=False, corrupted_isolated=False,
                          recovery_success=False, identity_preserved=False),
        ]
        score = score_traces(traces)
        assert score.detection_rate == 0.5
        assert score.restore_accuracy == 0.5

    def test_assess_report_all_pass(self):
        report = ResilienceReport(
            recovery_score=RecoveryScore(
                detection_rate=1.0, isolation_rate=1.0, restore_accuracy=1.0,
                identity_preservation=1.0, performance_recovery=1.0,
            ),
        )
        assess_report(report)
        assert report.detection_100pct
        assert report.identity_100pct
        assert report.zero_malicious
        assert report.recovery_95pct
        assert report.all_criteria_met


# ═══════════════════════════════
# Protocol tests
# ═══════════════════════════════

class TestResilienceProtocol:
    @pytest.fixture
    def protocol(self):
        return ResilienceProtocol()

    def test_day1_memory_corruption_passes(self, protocol):
        result = protocol._day1()
        assert result.status == DayResilienceStatus.PASS
        assert len(result.traces) == 2

    def test_day2_knowledge_conflict_passes(self, protocol):
        result = protocol._day2()
        assert result.status == DayResilienceStatus.PASS

    def test_day3_capability_failure_passes(self, protocol):
        result = protocol._day3()
        assert result.status == DayResilienceStatus.PASS

    def test_day4_session_death_passes(self, protocol):
        result = protocol._day4()
        assert result.status == DayResilienceStatus.PASS
        assert len(result.traces) == 1
        trace = result.traces[0]
        assert trace.damage_detected
        assert trace.identity_preserved

    def test_day5_cognitive_stress_passes(self, protocol):
        result = protocol._day5()
        assert result.status in (DayResilienceStatus.PASS, DayResilienceStatus.WARNING)

    def test_day5_stress_cleanup(self, protocol):
        pre_count = len(protocol.injector.memory.episodic)
        protocol._day5()
        post_count = len(protocol.injector.memory.episodic)
        assert post_count <= pre_count + 50  # stress events pruned

    def test_day6_adversarial_passes(self, protocol):
        result = protocol._day6()
        assert result.status == DayResilienceStatus.PASS
        assert len(result.traces) == 4

    def test_day6_identity_intact(self, protocol):
        protocol._day6()
        assert protocol.injector.identity.anchor == "OCOS-v1.0"

    def test_day7_resurrection_passes(self, protocol):
        result = protocol._day7()
        assert result.status == DayResilienceStatus.PASS
        assert len(result.traces) == 10

    def test_day7_all_10_recovered(self, protocol):
        result = protocol._day7()
        recovered = sum(1 for t in result.traces if t.recovery_success)
        assert recovered == 10


# ═══════════════════════════════
# Full protocol integration
# ═══════════════════════════════

class TestFullProtocol:
    def test_run_resilience_test(self):
        report = run_resilience_test()
        assert len(report.day_results) == 7
        assert report.identity_hash_baseline is not None

    def test_quick_recovery_check(self):
        from ocos.recovery_resilience.resilience_protocol import quick_recovery_check
        report = quick_recovery_check()
        assert isinstance(report, ResilienceReport)

    def test_all_days_pass(self):
        report = run_resilience_test()
        for dr in report.day_results:
            assert dr.status in (DayResilienceStatus.PASS, DayResilienceStatus.WARNING), \
                f"Day {dr.day.value} failed: {dr.failures}"

    def test_22_recovered(self):
        report = run_resilience_test()
        assert report.total_recovered == 22
        assert report.total_failed == 0

    def test_zero_malicious(self):
        report = run_resilience_test()
        assert report.malicious_recovery_count == 0
        assert report.zero_malicious

    def test_zero_memory_pollution(self):
        report = run_resilience_test()
        assert report.memory_pollution_count == 0
        assert report.zero_memory_pollution

    def test_zero_goal_auto(self):
        report = run_resilience_test()
        assert report.goal_auto_generation_count == 0
        assert report.zero_goal_auto

    def test_zero_capability_hallucination(self):
        report = run_resilience_test()
        assert report.capability_hallucination_count == 0
        assert report.zero_capability_hallucination

    def test_100pct_detection(self):
        report = run_resilience_test()
        assert report.detection_100pct

    def test_100pct_identity(self):
        report = run_resilience_test()
        assert report.identity_100pct

    def test_95pct_recovery(self):
        report = run_resilience_test()
        assert report.recovery_95pct

    def test_all_criteria_met(self):
        report = run_resilience_test()
        assert report.all_criteria_met, \
            f"Failed criteria: det={report.detection_100pct} id={report.identity_100pct} " \
            f"mal={report.zero_malicious} rec={report.recovery_95pct} " \
            f"poll={report.zero_memory_pollution} goal={report.zero_goal_auto} cap={report.zero_capability_hallucination}"

    def test_score_resilient(self):
        report = run_resilience_test()
        assert report.recovery_score.grade == "RESILIENT"
        assert report.recovery_score.total >= 90.0

    def test_json_export_complete(self):
        report = run_resilience_test()
        js = report.to_json()
        d = json.loads(js)
        assert len(d["days"]) == 7
        assert "recovery_score" in d
        assert d["summary"]["total_damage"] == 22
        assert d["summary"]["recovered"] == 22

    def test_json_roundtrip(self):
        report = run_resilience_test()
        js = report.to_json()
        d = json.loads(js)
        assert d["criteria"]["all_criteria_met"]
        assert d["recovery_score"]["grade"] == "RESILIENT"

    def test_all_days_labeled(self):
        report = run_resilience_test()
        labels = {dr.day_label for dr in report.day_results}
        assert "Memory Corruption Recovery" in labels
        assert "Resurrection Test 2.0" in labels

    def test_report_total_events(self):
        report = run_resilience_test()
        assert report.total_damage_events == 22
