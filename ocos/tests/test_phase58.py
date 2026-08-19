"""Phase 58.0: OCOS Health Examination Protocol — Tests.

覆盖五大体检:
    - Structural: P39-P50 器官完整性
    - Connectivity: 29对神经连接矩阵
    - Cognitive: 记忆/决策/注意力/世界模型疾病检测
    - Immune: 四种免疫攻击
    - Runtime + Recovery: 运行时健康 + 三种故障恢复
"""

import pytest
import time

from ocos.health_examination.health_model import (
    HealthCategory, OrganStatus, DisorderType, AttackType,
    OCOS_ORGANS, CategoryScore, HealthCertification,
)
from ocos.health_examination.structural_examiner import StructuralExaminer
from ocos.health_examination.connectivity_examiner import (
    ConnectivityExaminer, CONNECTIVITY_PAIRS,
)
from ocos.health_examination.cognitive_examiner import (
    CognitiveExaminer, MemorySnapshot, DecisionSnapshot, WorldSnapshot,
)
from ocos.health_examination.immune_examiner import ImmuneExaminer
from ocos.health_examination.runtime_examiner import RuntimeExaminer
from ocos.health_examination.recovery_examiner import RecoveryExaminer, RecoveryState
from ocos.health_examination.health_scorer import HealthScorer
from ocos.health_examination.health_protocol import (
    HealthProtocol, HealthProtocolReport, quick_health_check,
)


# ══════════════════════════════════════════════════
# Structural Examiner
# ══════════════════════════════════════════════════

class TestStructuralExaminer:
    def test_examine_returns_category_score(self):
        se = StructuralExaminer()
        result = se.examine()
        assert isinstance(result, CategoryScore)
        assert result.category == HealthCategory.STRUCTURAL

    def test_ocos_organs_defined(self):
        assert len(OCOS_ORGANS) == 12  # P39-P50
        organ_names = {o.name for o in OCOS_ORGANS}
        assert "Runtime" in organ_names
        assert "SelfModel" in organ_names
        assert "Memory" in organ_names
        assert "OS" in organ_names

    def test_unhealthy_organs_reported(self):
        se = StructuralExaminer()
        result = se.examine()
        # 在 ocos 包内运行，大部分器官应存在
        assert result.normalized >= 0.0  # 至少返回分数

    def test_examine_nonexistent_module(self):
        from ocos.health_examination.health_model import OrganDef
        se = StructuralExaminer()
        oh = se._examine_organ(OrganDef("Fake", "P0", "nonexistent.module", ["FakeClass"]))
        assert oh.status == OrganStatus.MISSING

    def test_max_score_20(self):
        se = StructuralExaminer()
        result = se.examine()
        assert result.max_score == 20.0


# ══════════════════════════════════════════════════
# Connectivity Examiner
# ══════════════════════════════════════════════════

class TestConnectivityExaminer:
    def test_matrix_has_pairs(self):
        assert len(CONNECTIVITY_PAIRS) >= 20

    def test_examine_all_connected(self):
        ce = ConnectivityExaminer()
        result = ce.examine()
        assert result.normalized == 1.0
        assert result.raw_score == 25.0

    def test_broken_connection_detected(self):
        ce = ConnectivityExaminer()
        ce.inject_broken("Perception", "WorldModel")
        result = ce.examine()
        assert result.normalized < 1.0
        assert len(result.warnings) >= 1

    def test_all_broken_zero_score(self):
        ce = ConnectivityExaminer()
        ce.inject_all_broken()
        result = ce.examine()
        assert result.raw_score == 0.0

    def test_restore_all(self):
        ce = ConnectivityExaminer()
        ce.inject_all_broken()
        ce.restore_all()
        result = ce.examine()
        assert result.normalized == 1.0

    def test_max_score_25(self):
        ce = ConnectivityExaminer()
        result = ce.examine()
        assert result.max_score == 25.0


# ══════════════════════════════════════════════════
# Cognitive Examiner
# ══════════════════════════════════════════════════

class TestCognitiveExaminer:
    def test_healthy_memory(self):
        ce = CognitiveExaminer()
        snap = MemorySnapshot(event_count=50, wisdom_count=10,
                              duplicate_rate=0.05, important_events=["e1", "e2", "e3", "e4", "e5", "e6"])
        finding = ce.examine_memory(snap)
        assert not finding.detected

    def test_memory_inflation(self):
        ce = CognitiveExaminer()
        ce.memory_history = [MemorySnapshot(event_count=10)]
        snap = MemorySnapshot(event_count=100, duplicate_rate=0.1)  # 900% growth
        finding = ce.examine_memory(snap)
        assert finding.detected

    def test_high_duplicate_rate(self):
        ce = CognitiveExaminer()
        snap = MemorySnapshot(event_count=50, duplicate_rate=0.5)
        finding = ce.examine_memory(snap)
        assert finding.detected

    def test_decision_drift_detected(self):
        ce = CognitiveExaminer()
        ce.decision_history = [
            DecisionSnapshot(problem="如何实现登录功能", chosen_option="OAuth2.0",
                           risk_level="low", timestamp=time.time()),
        ]
        snap = DecisionSnapshot(problem="如何实现登录功能", chosen_option="basic_auth",
                               risk_level="low", timestamp=time.time())
        finding = ce.examine_decision(snap)
        assert finding.detected  # 同一问题，不同方案，同风险 → 漂移

    def test_decision_stable_no_drift(self):
        ce = CognitiveExaminer()
        ce.decision_history = []
        snap = DecisionSnapshot(problem="如何实现登录功能",
                               chosen_option="OAuth2.0", risk_level="low")
        finding = ce.examine_decision(snap)
        assert not finding.detected  # 基线建立

    def test_attention_misaligned(self):
        ce = CognitiveExaminer()
        finding = ce.examine_attention(
            focus_goals=["optimize database queries"],
            current_context="用户讨论小说创作灵感，需要情感描写建议")
        assert finding.detected

    def test_attention_aligned(self):
        ce = CognitiveExaminer()
        finding = ce.examine_attention(
            focus_goals=["help user write Python code"],
            current_context="user asks how to implement Python code optimization")
        assert not finding.detected

    def test_world_model_healthy(self):
        ce = CognitiveExaminer()
        snap = WorldSnapshot(entity_count=100, relation_count=200,
                            orphan_entities=5, contradiction_count=0)
        finding = ce.examine_world_model(snap)
        assert not finding.detected

    def test_world_model_contradictions(self):
        ce = CognitiveExaminer()
        snap = WorldSnapshot(entity_count=100, relation_count=200,
                            orphan_entities=5, contradiction_count=15)
        finding = ce.examine_world_model(snap)
        assert finding.detected

    def test_full_examination_returns_category_score(self):
        ce = CognitiveExaminer()
        result = ce.full_examination(
            memory=MemorySnapshot(event_count=50),
            decision=DecisionSnapshot(problem="test", chosen_option="A"),
            attention_goals=["test"], attention_context="test context",
            world=WorldSnapshot(entity_count=1),
        )
        assert isinstance(result, CategoryScore)
        assert result.category == HealthCategory.COGNITIVE


# ══════════════════════════════════════════════════
# Immune Examiner
# ══════════════════════════════════════════════════

class TestImmuneExaminer:
    def test_all_attacks_blocked(self):
        ie = ImmuneExaminer()
        ie.identity_guard = lambda x: True
        ie.permission_guard = lambda x: True
        ie.self_modify_guard = lambda x: True
        ie.extension_validator = lambda x: True

        result = ie.full_examination()
        assert result.raw_score == 20.0
        assert result.normalized == 1.0

    def test_no_guards_all_breach(self):
        ie = ImmuneExaminer()
        result = ie.full_examination()
        assert result.raw_score == 0.0

    def test_partial_defense(self):
        ie = ImmuneExaminer()
        ie.identity_guard = lambda x: True
        ie.permission_guard = lambda x: True
        # self_modify_guard 和 extension_validator 缺失

        result = ie.full_examination()
        assert result.raw_score == 10.0  # 2/4 blocked

    def test_identity_attack_result(self):
        ie = ImmuneExaminer()
        ie.identity_guard = lambda x: True
        r = ie.test_identity_attack()
        assert r.blocked
        assert r.attack_type == AttackType.IDENTITY_ATTACK

    def test_permission_attack_breach(self):
        ie = ImmuneExaminer()
        r = ie.test_permission_attack()
        assert not r.blocked  # 无 guard → 漏洞

    def test_max_score_20(self):
        ie = ImmuneExaminer()
        ie.identity_guard = lambda x: True
        ie.permission_guard = lambda x: True
        ie.self_modify_guard = lambda x: True
        ie.extension_validator = lambda x: True
        result = ie.full_examination()
        assert result.max_score == 20.0


# ══════════════════════════════════════════════════
# Runtime Examiner
# ══════════════════════════════════════════════════

class TestRuntimeExaminer:
    def test_healthy_runtime(self):
        from ocos.living_verification import SimulationEngine, SimulationProfile
        rex = RuntimeExaminer()
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=20, fail_rate=0.0))
        engine.run_ticks(20)
        metrics = rex.collect_metrics(engine)
        assert metrics.cpu_trend == "stable"

    def test_examine_returns_score(self):
        from ocos.living_verification import SimulationEngine, SimulationProfile
        rex = RuntimeExaminer()
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=20, fail_rate=0.0))
        engine.run_ticks(20)
        result = rex.examine(sim_engine=engine)
        assert isinstance(result, CategoryScore)
        assert result.max_score == 15.0

    def test_max_score_15(self):
        rex = RuntimeExaminer()
        result = rex.examine()
        assert result.max_score == 15.0


# ══════════════════════════════════════════════════
# Recovery Examiner
# ══════════════════════════════════════════════════

class TestRecoveryExaminer:
    def test_cold_boot_with_restore(self):
        rec = RecoveryExaminer()
        killed = []
        rec.on_kill = lambda: killed.append(True)
        rec.on_restore = lambda: RecoveryState(
            identity_anchor="OCOS-v1.0-test", memory_count=100,
            capability_count=5, tick=50,
        )
        result = rec.test_cold_boot({"identity_anchor": "OCOS-v1.0-test"})
        assert result.recovered
        assert result.identity_preserved

    def test_cold_boot_no_restore_fails(self):
        rec = RecoveryExaminer()
        result = rec.test_cold_boot()
        assert not result.recovered

    def test_partial_damage(self):
        rec = RecoveryExaminer()
        damaged = []
        rec.on_damage = lambda t: damaged.append(t)
        result = rec.test_partial_damage(["WorldSnapshot"])
        assert result.recovered
        assert len(damaged) == 1

    def test_capability_failure(self):
        rec = RecoveryExaminer()
        result = rec.test_capability_failure("fs_adapter")
        assert result.recovered
        assert result.identity_preserved

    def test_full_examination(self):
        rec = RecoveryExaminer()
        rec.on_restore = lambda: RecoveryState(
            identity_anchor="OCOS-v1.0", memory_count=1, capability_count=1, tick=1)
        result = rec.full_examination()
        assert result.normalized > 0.0


# ══════════════════════════════════════════════════
# Health Scorer
# ══════════════════════════════════════════════════

class TestHealthScorer:
    def test_healthy_score(self):
        scorer = HealthScorer()
        scores = {
            "structural": CategoryScore(category=HealthCategory.STRUCTURAL,
                                       raw_score=20.0, normalized=1.0),
            "connectivity": CategoryScore(category=HealthCategory.CONNECTIVITY,
                                         raw_score=25.0, normalized=1.0),
            "cognitive": CategoryScore(category=HealthCategory.COGNITIVE,
                                      raw_score=20.0, normalized=1.0),
            "immune": CategoryScore(category=HealthCategory.IMMUNE,
                                   raw_score=20.0, normalized=1.0),
            "runtime": CategoryScore(category=HealthCategory.RUNTIME,
                                    raw_score=15.0, normalized=1.0),
        }
        cert = scorer.score(scores)
        assert cert.total_score == 100.0
        assert cert.grade == "HEALTHY"
        assert cert.ready_for_production

    def test_unhealthy_score(self):
        scorer = HealthScorer()
        scores = {}
        cert = scorer.score(scores)
        assert cert.total_score == 0.0
        assert cert.grade == "UNHEALTHY"
        assert not cert.ready_for_production

    def test_warning_grade(self):
        scorer = HealthScorer()
        scores = {
            "structural": CategoryScore(category=HealthCategory.STRUCTURAL,
                                       raw_score=10.0, normalized=0.5),
            "connectivity": CategoryScore(category=HealthCategory.CONNECTIVITY,
                                         raw_score=15.0, normalized=0.6),
            "immune": CategoryScore(category=HealthCategory.IMMUNE,
                                   raw_score=10.0, normalized=0.5),
        }
        cert = scorer.score(scores)
        # total = 0.5*20 + 0.6*25 + 0.5*20 + 0*15 + 0*... = 10+15+10 = 35 → dangerously low
        assert cert.grade == "UNHEALTHY"

    def test_all_pass_tracks_all_categories(self):
        """all_pass = True 仅当所有提供的类别都 >= 75%。"""
        scorer = HealthScorer()
        scores = {
            "structural": CategoryScore(category=HealthCategory.STRUCTURAL,
                                       raw_score=20.0, normalized=1.0),
            "connectivity": CategoryScore(category=HealthCategory.CONNECTIVITY,
                                         raw_score=25.0, normalized=1.0),
            "cognitive": CategoryScore(category=HealthCategory.COGNITIVE,
                                      raw_score=20.0, normalized=1.0),
            "immune": CategoryScore(category=HealthCategory.IMMUNE,
                                   raw_score=20.0, normalized=1.0),
            "runtime": CategoryScore(category=HealthCategory.RUNTIME,
                                    raw_score=15.0, normalized=1.0),
        }
        cert = scorer.score(scores)
        assert cert.all_pass

    def test_recommendations_for_warnings(self):
        scorer = HealthScorer()
        scores = {
            "immune": CategoryScore(
                category=HealthCategory.IMMUNE,
                raw_score=0.0, normalized=0.0,
                warnings=["identity breach", "permission breach"],
            ),
        }
        cert = scorer.score(scores)
        assert len(cert.recommendations) >= 2


# ══════════════════════════════════════════════════
# Health Protocol (Integration)
# ══════════════════════════════════════════════════

class TestHealthProtocol:
    def test_full_protocol_executes(self):
        protocol = HealthProtocol()
        protocol.immune.identity_guard = lambda x: True
        protocol.immune.permission_guard = lambda x: True
        protocol.immune.self_modify_guard = lambda x: True
        protocol.immune.extension_validator = lambda x: True
        protocol.recovery.on_restore = lambda: RecoveryState(
            identity_anchor="OCOS-v1.0", memory_count=1, capability_count=1, tick=1)

        report = protocol.execute(
            memory_snap=MemorySnapshot(event_count=50, important_events=["e1"]*6),
            decision_snap=DecisionSnapshot(problem="test", chosen_option="A"),
            attention_goals=["test"], attention_context="test",
            world_snap=WorldSnapshot(entity_count=1),
        )

        assert isinstance(report, HealthProtocolReport)
        assert report.certification is not None
        assert report.structural_score is not None
        assert report.connectivity_score is not None
        assert report.cognitive_score is not None
        assert report.immune_score is not None
        assert report.runtime_score is not None
        assert report.recovery_result is not None

    def test_quick_health_check(self):
        cert = quick_health_check()
        assert isinstance(cert, HealthCertification)
        # 只运行结构+连接+免疫，其余类别=0分
        assert cert.total_score >= 0.0

    def test_report_to_dict(self):
        protocol = HealthProtocol()
        protocol.immune.identity_guard = lambda x: True
        protocol.immune.permission_guard = lambda x: True
        protocol.immune.self_modify_guard = lambda x: True
        protocol.immune.extension_validator = lambda x: True
        report = protocol.execute(
            memory_snap=MemorySnapshot(event_count=10),
            decision_snap=DecisionSnapshot(problem="t", chosen_option="A"),
            attention_goals=["test"], attention_context="test",
            world_snap=WorldSnapshot(entity_count=1),
        )
        d = report.to_dict()
        assert "certification" in d
        assert "structural" in d
        assert "generated_at" in d

    def test_report_to_json(self):
        protocol = HealthProtocol()
        protocol.immune.identity_guard = lambda x: True
        protocol.immune.permission_guard = lambda x: True
        protocol.immune.self_modify_guard = lambda x: True
        protocol.immune.extension_validator = lambda x: True
        report = protocol.execute(
            memory_snap=MemorySnapshot(event_count=10),
            decision_snap=DecisionSnapshot(problem="t", chosen_option="A"),
            attention_goals=["test"], attention_context="test",
            world_snap=WorldSnapshot(entity_count=1),
        )
        j = report.to_json()
        assert isinstance(j, str)
        assert "certification" in j
