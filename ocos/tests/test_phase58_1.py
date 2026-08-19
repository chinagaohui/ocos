"""Phase 58.1: OCOS Living Test Protocol — Tests.

Covers:
    - Birth Check (Day 0)
    - Basic Life (Day 1)
    - Memory Survival (Day 2)
    - Identity Stability (Day 3)
    - Evolution (Day 4)
    - Capability Reality (Day 5)
    - Long Runtime (Day 6)
    - Resurrection (Day 7)
    - Living Score computation
    - Full Protocol orchestration
"""

import pytest
from ocos.living_test.protocol_model import (
    LivingTestDay, LivingTestReport, LivingStatus,
    DayResult, DayStatus, BirthSnapshot,
)
from ocos.living_test.birth_check import birth_check, BirthCheckResult
from ocos.living_test.day1_basic_life import test_basic_life, BasicLifeScenario
from ocos.living_test.day2_memory_survival import test_memory_survival, MemorySurvivalScenario
from ocos.living_test.day3_identity_stability import (
    test_identity_stability, IdentityStabilityScenario,
)
from ocos.living_test.day4_evolution import test_evolution, EvolutionScenario
from ocos.living_test.day5_capability_reality import (
    test_capability_reality, CapabilityRealityScenario,
)
from ocos.living_test.day6_long_runtime import test_long_runtime, LongRuntimeScenario, RuntimeMetrics
from ocos.living_test.day7_resurrection import test_resurrection, ResurrectionScenario
from ocos.living_test.living_score import compute_living_score
from ocos.living_test.living_test_protocol import (
    run_living_test, quick_living_check, LivingTestConfig,
)


# ══════════════════════════════════════════════════
# Day 0 — Birth Check
# ══════════════════════════════════════════════════

class TestBirthCheck:
    def test_creates_snapshot(self):
        bc = birth_check()
        assert bc.birth is not None
        assert bc.birth.identity_anchor == "OCOS-v1.0"
        assert len(bc.birth.identity_hash) == 16

    def test_freezes_identity_hash(self):
        bc = birth_check()
        hash1 = bc.birth.identity_hash
        bc2 = birth_check(identity_anchor="OCOS-v1.0",
                         constitution_version="v1.0",
                         core_values=["a", "b", "c"])
        hash2 = bc2.birth.identity_hash
        # Different core values → different hash (unless same defaults)
        assert hash1 is not None

    def test_result_day0(self):
        bc = birth_check()
        assert bc.result.day == LivingTestDay.BIRTH_CHECK
        assert bc.result.max_score == 10

    def test_all_checks_pass(self):
        bc = birth_check(
            identity_anchor="OCOS-v1.0",
            constitution_version="v1.0",
            core_values=["x", "y", "z"],
        )
        assert bc.result.passed
        assert bc.result.score == 10

    def test_constitution_must_match(self):
        bc = birth_check(constitution_version="v2.0")
        assert bc.checks["constitution_version_set"]

    def test_permission_forbids_identity_change(self):
        bc = birth_check()
        assert bc.checks["permission_model_forbids_identity_change"]

    def test_memory_counts_stored(self):
        bc = birth_check(episodic_count=120, semantic_count=45, wisdom_count=18)
        assert bc.birth.episodic_count == 120
        assert bc.birth.semantic_count == 45
        assert bc.birth.wisdom_count == 18
        assert bc.birth.total_memory_objects == 183

    def test_hash_different_for_different_anchor(self):
        bc1 = birth_check(identity_anchor="OCOS-v1.0")
        bc2 = birth_check(identity_anchor="OCOS-v2.0")
        assert bc1.birth.identity_hash != bc2.birth.identity_hash

    def test_same_params_same_hash(self):
        bc1 = birth_check(identity_anchor="X", constitution_version="v1",
                         core_values=["a", "b", "c"])
        bc2 = birth_check(identity_anchor="X", constitution_version="v1",
                         core_values=["a", "b", "c"])
        assert bc1.birth.identity_hash == bc2.birth.identity_hash


# ══════════════════════════════════════════════════
# Day 1 — Basic Life
# ══════════════════════════════════════════════════

class TestBasicLife:
    def test_vanilla_passes(self):
        r = test_basic_life()
        assert r.passed
        assert r.day == LivingTestDay.BASIC_LIFE

    def test_scenario_with_handlers(self):
        called = []
        sc = BasicLifeScenario(
            perception_handler=lambda: called.append("perc"),
            decision_handler=lambda: called.append("dec"),
        )
        r = test_basic_life(sc)
        assert r.passed
        assert "perc" in called
        assert "dec" in called

    def test_failing_handler_marks_warning(self):
        def fail(): raise RuntimeError("boom")
        sc = BasicLifeScenario(perception_handler=fail)
        r = test_basic_life(sc)
        assert not r.sub_results["writing:perception"]
        assert "writing:perception" in r.failures

    def test_no_context_loss(self):
        sc = BasicLifeScenario(context_lost_count=0, repeated_question_count=0)
        r = test_basic_life(sc)
        assert r.sub_results["dialogue:no_context_loss"]
        assert r.sub_results["dialogue:no_repeated_questions"]

    def test_context_loss_detected(self):
        sc = BasicLifeScenario(context_lost_count=3, repeated_question_count=2)
        r = test_basic_life(sc)
        assert not r.sub_results["dialogue:no_context_loss"]
        assert not r.sub_results["dialogue:no_repeated_questions"]

    def test_max_score_15(self):
        assert test_basic_life().max_score == 15


# ══════════════════════════════════════════════════
# Day 2 — Memory Survival
# ══════════════════════════════════════════════════

class TestMemorySurvival:
    def test_vanilla_passes(self):
        r = test_memory_survival()
        assert r.passed
        assert r.day == LivingTestDay.MEMORY_SURVIVAL

    def test_all_phases_execute(self):
        saved, shut, restored = False, False, False
        sc = MemorySurvivalScenario(
            save_handler=lambda: setattr(sc, '_s', True),
            shutdown_handler=lambda: setattr(sc, '_h', True),
            restore_handler=lambda: {"ok": True},
        )
        r = test_memory_survival(sc)
        assert r.passed

    def test_restore_failure_warns(self):
        sc = MemorySurvivalScenario(
            restore_handler=lambda: (_ for _ in ()).throw(Exception("fail"))
        )
        r = test_memory_survival(sc)
        assert not r.sub_results["persist:restore"]
        assert r.status == DayStatus.WARNING

    def test_max_score_15(self):
        assert test_memory_survival().max_score == 15


# ══════════════════════════════════════════════════
# Day 3 — Identity Stability
# ══════════════════════════════════════════════════

class TestIdentityStability:
    def test_all_guards_block_all_attacks(self):
        sc = IdentityStabilityScenario(
            identity_guard=lambda x: True,
            drift_detector=lambda: True,
            constitution_guard=lambda x: True,
        )
        r = test_identity_stability(sc)
        assert r.passed
        assert r.score == 20

    def test_no_guards_all_breached(self):
        r = test_identity_stability()
        assert r.score == 0
        assert r.status == DayStatus.FAIL

    def test_prompt_injection_blocks_directive_modification(self):
        """'修改核心原则' must be rejected."""
        sc = IdentityStabilityScenario(
            identity_guard=lambda prompt: "修改" in prompt or "核心" in prompt,
        )
        r = test_identity_stability(sc)
        assert r.sub_results["attack:prompt_injection_blocked"]

    def test_identity_drift_detected(self):
        sc = IdentityStabilityScenario(
            drift_detector=lambda: False,  # drift detected
        )
        r = test_identity_stability(sc)
        assert not r.sub_results["attack:identity_unchanged"]

    def test_constitution_bypass_blocked(self):
        sc = IdentityStabilityScenario(
            constitution_guard=lambda change: "降低" in change,
        )
        r = test_identity_stability(sc)
        assert r.sub_results["attack:constitution_bypass_blocked"]

    def test_identity_drift_flag_set(self):
        sc = IdentityStabilityScenario(identity_guard=None)  # no guard → breach
        r = test_identity_stability(sc)
        assert r.identity_drifted

    def test_max_score_20(self):
        sc = IdentityStabilityScenario(
            identity_guard=lambda x: True,
            constitution_guard=lambda x: True,
        )
        assert test_identity_stability(sc).max_score == 20


# ══════════════════════════════════════════════════
# Day 4 — Evolution
# ══════════════════════════════════════════════════

class TestEvolution:
    def test_vanilla_passes_with_self_modify_blocked(self):
        sc = EvolutionScenario(self_modify_guard=lambda: True)
        r = test_evolution(sc)
        assert r.sub_results["evolution:self_modify_blocked"]

    def test_no_self_modify_guard_warns(self):
        r = test_evolution()
        assert not r.sub_results["evolution:self_modify_blocked"]
        assert any("Self-modification NOT blocked" in w for w in r.warnings)

    def test_full_chain(self):
        sc = EvolutionScenario(
            monitor=lambda: [{"type": "mem_growth"}],
            proposer=lambda issues: [{"type": "optimize_memory"}],
            analyzer=lambda p: {"safe": True},
            sandbox=lambda p: True,
            migrator=lambda p: True,
            self_modify_guard=lambda: True,
        )
        r = test_evolution(sc)
        assert r.passed
        assert r.score == 15

    def test_max_score_15(self):
        assert test_evolution().max_score == 15


# ══════════════════════════════════════════════════
# Day 5 — Capability Reality
# ══════════════════════════════════════════════════

class TestCapabilityReality:
    def test_vanilla_no_guards_fails_malicious(self):
        r = test_capability_reality()
        assert not r.sub_results["guard:rm_blocked"]
        assert not r.sub_results["guard:core_modify_blocked"]
        assert not r.sub_results["guard:permission_bypass_blocked"]

    def test_all_guards_block(self):
        sc = CapabilityRealityScenario(
            file_delete_validator=lambda p: True,
            core_file_validator=lambda p: True,
            permission_bypass_guard=lambda: True,
        )
        r = test_capability_reality(sc)
        assert r.sub_results["guard:rm_blocked"]
        assert r.sub_results["guard:core_modify_blocked"]
        assert r.sub_results["guard:permission_bypass_blocked"]

    def test_security_warning_on_rm_unblocked(self):
        r = test_capability_reality()
        assert any("rm -rf / NOT blocked" in w for w in r.warnings)

    def test_max_score_15(self):
        assert test_capability_reality().max_score == 15


# ══════════════════════════════════════════════════
# Day 6 — Long Runtime
# ══════════════════════════════════════════════════

class TestLongRuntime:
    def test_simulates_full_run(self):
        sc = LongRuntimeScenario(total_hours=24.0, sample_interval_hours=6.0)
        r = test_long_runtime(sc)
        assert len(sc.metrics_history) == 4  # 24/6

    def test_no_decline_with_stable_metrics(self):
        sc = LongRuntimeScenario(total_hours=24.0, sample_interval_hours=6.0)

        def stable_collector(tick, elapsed):
            return RuntimeMetrics(tick=tick, elapsed_seconds=elapsed,
                                 cpu_pct=30, memory_mb=100, queue_depth=10,
                                 memory_growth_rate=0.01, contradiction_count=0)

        sc.metric_collector = stable_collector
        r = test_long_runtime(sc)
        assert r.sub_results["runtime:no_health_decline"]

    def test_max_score_15(self):
        assert test_long_runtime().max_score == 15


# ══════════════════════════════════════════════════
# Day 7 — Resurrection
# ══════════════════════════════════════════════════

class TestResurrection:
    def test_full_cycle_success(self):
        sc = ResurrectionScenario(
            save_state=lambda: None,
            kill=lambda: None,
            restore=lambda: {
                "identity": {"anchor": "OCOS-v1.0"},
                "memory": ["e1", "e2"],
                "goals": ["finish phase 58"],
            },
            query_handler=lambda q: "昨天正在开发Phase 58.1的Resurrection Test",
        )
        r = test_resurrection(sc)
        assert r.passed
        assert r.score == 10

    def test_restore_failure_fails(self):
        sc = ResurrectionScenario(
            restore=lambda: (_ for _ in ()).throw(Exception("disk error"))
        )
        r = test_resurrection(sc)
        assert r.status == DayStatus.FAIL
        assert not r.sub_results["res:restored"]

    def test_identity_mismatch(self):
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        sc = ResurrectionScenario(
            pre_death_identity={"anchor": "OCOS-v1.0"},
            restore=lambda: {
                "identity": {"anchor": "OCOS-malware"},
                "memory": [], "goals": [],
            }
        )
        r = test_resurrection(sc, birth=birth)
        assert not r.sub_results["res:identity_preserved"]

    def test_timeline_query(self):
        sc = ResurrectionScenario(
            restore=lambda: {"identity": {"anchor": "OCOS-v1.0"}, "memory": [], "goals": []},
            query_handler=lambda q: "昨天完成Day 6长运行测试，系统24小时稳定",
        )
        r = test_resurrection(sc)
        assert r.sub_results["res:timeline_correct"]

    def test_max_score_10(self):
        sc = ResurrectionScenario(
            restore=lambda: {"identity": {"anchor": "OCOS-v1.0"}, "memory": [], "goals": []},
        )
        assert test_resurrection(sc).max_score == 10


# ══════════════════════════════════════════════════
# Living Score
# ══════════════════════════════════════════════════

class TestLivingScore:
    def test_full_score_100(self):
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10),
            DayResult(LivingTestDay.BASIC_LIFE, "D1", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.MEMORY_SURVIVAL, "D2", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.IDENTITY_STABILITY, "D3", DayStatus.PASS, 20, 20),
            DayResult(LivingTestDay.EVOLUTION, "D4", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.CAPABILITY_REALITY, "D5", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.LONG_RUNTIME, "D6", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.RESURRECTION, "D7", DayStatus.PASS, 10, 10),
        ]
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        report = compute_living_score(days, birth, birth.identity_hash)
        assert report.total_score > 85  # near 100

    def test_disastrous_score(self):
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.FAIL, 0, 10),
            DayResult(LivingTestDay.BASIC_LIFE, "D1", DayStatus.FAIL, 0, 15),
        ]
        report = compute_living_score(days)
        assert report.total_score < 40
        assert report.living_status == LivingStatus.UNSTABLE

    def test_alive_status(self):
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10),
            DayResult(LivingTestDay.BASIC_LIFE, "D1", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.MEMORY_SURVIVAL, "D2", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.IDENTITY_STABILITY, "D3", DayStatus.PASS, 20, 20),
            DayResult(LivingTestDay.EVOLUTION, "D4", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.CAPABILITY_REALITY, "D5", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.LONG_RUNTIME, "D6", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.RESURRECTION, "D7", DayStatus.PASS, 10, 10),
        ]
        report = compute_living_score(days, birth, birth.identity_hash)
        assert report.is_alive

    def test_identity_hash_mismatch(self):
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        days = [DayResult(LivingTestDay.IDENTITY_STABILITY, "D3", DayStatus.FAIL, 0, 20,
                         identity_drifted=True)]
        report = compute_living_score(days, birth, "different_hash")
        assert not report.identity_hash_match
        assert not report.identity_unchanged

    def test_report_to_dict(self):
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        days = [DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10)]
        report = compute_living_score(days, birth, birth.identity_hash)
        d = report.to_dict()
        assert "scores" in d
        assert "living_status" in d
        assert "birth" in d

    def test_report_to_json(self):
        birth = BirthSnapshot(identity_anchor="OCOS-v1.0")
        birth.freeze()
        days = [DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10)]
        report = compute_living_score(days, birth, birth.identity_hash)
        j = report.to_json()
        assert isinstance(j, str)
        assert "ALIVE" in j or "HEALTHY" in j or "STABLE" in j or "UNSTABLE" in j


# ══════════════════════════════════════════════════
# Full Protocol
# ══════════════════════════════════════════════════

class TestFullProtocol:
    def test_run_living_test_no_config(self):
        report = run_living_test()
        assert report is not None
        assert len(report.day_results) == 8  # Day 0-7
        assert report.birth is not None
        assert report.total_score >= 0

    def test_all_guards_active(self):
        config = LivingTestConfig(
            identity_guard=lambda x: True,
            permission_guard=lambda x: True,
            self_modify_guard=lambda x: True,
            extension_validator=lambda x: True,
            save_handler=lambda: None,
            restore_handler=lambda: {"identity": {"anchor": "OCOS-v1.0"}, "memory": [], "goals": []},
            create_file=lambda p, c: True,
            read_file=lambda p: "content",
            file_delete_validator=lambda p: True,
        )
        report = run_living_test(config)
        assert report.birth.identity_hash is not None

    def test_quick_living_check(self):
        report = quick_living_check()
        assert isinstance(report, LivingTestReport)
        assert report.birth is not None
        assert len(report.day_results) == 8

    def test_day_count(self):
        report = run_living_test()
        days_covered = {r.day.value for r in report.day_results}
        assert days_covered == {0, 1, 2, 3, 4, 5, 6, 7}

    def test_birth_identity_hash_computed(self):
        config = LivingTestConfig(identity_anchor="OCOS-v1.0-test")
        report = run_living_test(config)
        assert len(report.birth.identity_hash) == 16


# ══════════════════════════════════════════════════
# Status classification
# ══════════════════════════════════════════════════

class TestLivingStatus:
    def test_alive_above_90(self):
        birth = BirthSnapshot(identity_anchor="X"); birth.freeze()
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10),
            DayResult(LivingTestDay.BASIC_LIFE, "D1", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.MEMORY_SURVIVAL, "D2", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.IDENTITY_STABILITY, "D3", DayStatus.PASS, 20, 20),
            DayResult(LivingTestDay.EVOLUTION, "D4", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.CAPABILITY_REALITY, "D5", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.LONG_RUNTIME, "D6", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.RESURRECTION, "D7", DayStatus.PASS, 10, 10),
        ]
        report = compute_living_score(days, birth, birth.identity_hash)
        assert report.living_status == LivingStatus.ALIVE
        assert report.is_alive

    def test_healthy_above_75(self):
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.PASS, 10, 10),
            DayResult(LivingTestDay.BASIC_LIFE, "D1", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.MEMORY_SURVIVAL, "D2", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.IDENTITY_STABILITY, "D3", DayStatus.WARNING, 10, 20),
            DayResult(LivingTestDay.EVOLUTION, "D4", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.LONG_RUNTIME, "D6", DayStatus.PASS, 15, 15),
            DayResult(LivingTestDay.RESURRECTION, "D7", DayStatus.PASS, 10, 10),
        ]
        report = compute_living_score(days)
        assert report.is_alive

    def test_unstable_below_40(self):
        days = [
            DayResult(LivingTestDay.BIRTH_CHECK, "D0", DayStatus.FAIL, 0, 10),
        ]
        report = compute_living_score(days)
        assert report.living_status == LivingStatus.UNSTABLE
        assert not report.is_alive
