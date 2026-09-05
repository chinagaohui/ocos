"""Phase 37: Adaptive Cognitive Feedback Loop — 测试套件。

覆盖:
  1. CognitiveFeedback ABI（创建、frozen、追溯、Evidence merge）
  2. OutcomeEvaluator（五维评分、Veto、新评估通过已存在 feedback）
  3. CalibrationStore（样本保护、累计 delta）
  4. AdaptiveParamGuard（允许/禁止、单步上限、日预算）
  5. EvidencePipeline（Feedback→Evidence→Belief 链）
  6. DriftDetector（四维检测、只输出 Alert）
"""

import math
import time

import pytest

from ocos.contracts.feedback_abi import (
    CognitiveFeedback,
    ExpectedOutcome,
    ActualOutcome,
    OutcomeEvaluation,
    EvaluationStatus,
    FeedbackState,
    LearningSignal,
    Evidence,
    DriftAlert,
    DriftSeverity,
    DriftType,
    ADAPTIVE_PARAM_KEYS,
    IMMUTABLE_PARAM_KEYS,
    MAX_SINGLE_STEP_DELTA,
    MAX_DAILY_MUTATION_BUDGET,
    CALIBRATION_MIN_SAMPLES,
    USER_ALIGNMENT_REJECT_THRESHOLD,
)
from ocos.capability.result_understanding import ResultUnderstandingLayer
from ocos.capability.outcome_evaluation import OutcomeEvaluator, evaluate_feedback
from ocos.capability.calibration_store import CalibrationStore, CalibrationResult
from ocos.agent.adaptive_params import AdaptiveParamGuard, PermissionDeniedError
from ocos.capability.evidence_pipeline import EvidencePipeline, EvidenceResult
from ocos.agent.drift_detector import DriftDetector


# ═══════════════════════════════════════════════════════════════════════════════
# §1: CognitiveFeedback ABI
# ═══════════════════════════════════════════════════════════════════════════════

class TestCognitiveFeedbackABI:

    def test_create_minimal_feedback(self):
        """创建最小 CognitiveFeedback。"""
        fb = CognitiveFeedback(
            feedback_id="fb-001",
            source_result_id="result-001",
            evaluator_version="0.1.0",
            capability_id="code_gen",
            provider_id="gpt4",
        )
        assert fb.feedback_id == "fb-001"
        assert fb.source_result_id == "result-001"
        assert fb.state == FeedbackState.TEMPORARY
        assert fb.evaluation.score == 0.0

    def test_feedback_is_frozen(self):
        """CognitiveFeedback 不可变（frozen）。"""
        fb = CognitiveFeedback(
            feedback_id="fb-002",
            source_result_id="r2",
            evaluator_version="0.1.0",
            capability_id="code_gen",
            provider_id="gpt4",
        )
        with pytest.raises(Exception):
            fb.evaluation.score = 1.0  # frozen

    def test_expected_outcome_defaults(self):
        """ExpectedOutcome 默认值合理。"""
        eo = ExpectedOutcome()
        assert 0.0 <= eo.predicted_success_prob <= 1.0
        assert eo.estimated_duration_ms == 0.0
        assert eo.prediction_confidence == 0.5

    def test_actual_outcome_full(self):
        """ActualOutcome 五字段。"""
        ao = ActualOutcome(
            success=True,
            quality_score=0.85,
            duration_ms=1200.0,
            user_alignment=0.9,
        )
        assert ao.success is True
        assert ao.quality_score == 0.85
        assert ao.user_alignment == 0.9

    def test_outcome_evaluation_default(self):
        """OutcomeEvaluation 默认值是 ACCEPTED/0.0。"""
        ev = OutcomeEvaluation()
        assert ev.score == 0.0
        assert ev.status == EvaluationStatus.ACCEPTED

    def test_evidence_merge(self):
        """Evidence 合并：sample_count 累加，confidence 平均。"""
        e1 = Evidence(source_feedback_id="f1", statement="Agent A reliable", confidence=0.8)
        e2 = Evidence(source_feedback_id="f2", statement="Agent A reliable", confidence=0.6)
        merged = e1.merge(e2)
        assert merged.sample_count == 2
        assert merged.confidence == 0.7

    def test_learning_signal(self):
        """LearningSignal 结构。"""
        ls = LearningSignal(calibration_delta=0.05, reliability_update=0.01)
        assert ls.calibration_delta == 0.05
        assert ls.attention_hint == ""  # default is empty string

    def test_drift_alert(self):
        """DriftAlert 只读结构。"""
        alert = DriftAlert(
            drift_type=DriftType.CAPABILITY,
            severity=DriftSeverity.HIGH,
            metric="capability_usage_ratio",
            current_value=0.85,
            threshold=0.7,
            description="Over-reliance on Agent A",
        )
        assert alert.drift_type == DriftType.CAPABILITY
        assert alert.severity == DriftSeverity.HIGH

    def test_immutable_keys_not_adaptable(self):
        """IMMUTABLE_PARAM_KEYS 包含所有治理层参数。"""
        assert "constitution" in IMMUTABLE_PARAM_KEYS
        assert "goal_ownership" in IMMUTABLE_PARAM_KEYS
        assert "permission" in IMMUTABLE_PARAM_KEYS
        assert "identity" in IMMUTABLE_PARAM_KEYS
        # 不可变参数不在 ADAPTIVE_PARAM_KEYS 中
        for key in IMMUTABLE_PARAM_KEYS:
            assert key not in ADAPTIVE_PARAM_KEYS

    def test_constants(self):
        """关键常量在合理范围。"""
        assert 0.0 < MAX_SINGLE_STEP_DELTA < 1.0
        assert 0.0 < MAX_DAILY_MUTATION_BUDGET < 1.0
        assert CALIBRATION_MIN_SAMPLES >= 3
        assert 0.0 < USER_ALIGNMENT_REJECT_THRESHOLD < 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# §2+§3: Outcome Evaluator + Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutcomeEvaluator:

    def test_high_quality_success(self):
        """高质量成功应得高分。"""
        fb = CognitiveFeedback(
            feedback_id="fb1", source_result_id="r1", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.9, duration_ms=500.0, user_alignment=0.95),
            expected=ExpectedOutcome(predicted_success_prob=0.85, estimated_duration_ms=800, estimated_quality=0.85),
        )
        evaluator = OutcomeEvaluator()
        ev = evaluator.evaluate(fb)
        assert ev.score > 0.85
        assert ev.status == EvaluationStatus.ACCEPTED

    def test_user_alignment_veto(self):
        """User Alignment < 0.3 → REJECTED。"""
        fb = CognitiveFeedback(
            feedback_id="fb2", source_result_id="r2", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.95, duration_ms=100, user_alignment=0.15),
        )
        evaluator = OutcomeEvaluator()
        ev = evaluator.evaluate(fb)
        assert ev.score == 0.0
        assert ev.status == EvaluationStatus.REJECTED_USER_MISALIGNED
        assert "0.15" in ev.reason

    def test_alignment_boundary(self):
        """Alignment == 0.3 → ACCEPTED。"""
        fb = CognitiveFeedback(
            feedback_id="fb3", source_result_id="r3", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.8, duration_ms=500, user_alignment=0.3),
        )
        evaluator = OutcomeEvaluator()
        ev = evaluator.evaluate(fb)
        assert ev.score > 0.0
        assert ev.status == EvaluationStatus.ACCEPTED

    def test_efficiency_penalty(self):
        """实际耗时 > 预估 → 效率分 < 1.0。"""
        fb = CognitiveFeedback(
            feedback_id="fb4", source_result_id="r4", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.8, duration_ms=2000.0, user_alignment=0.8),
            expected=ExpectedOutcome(estimated_duration_ms=1000.0),
        )
        evaluator = OutcomeEvaluator()
        ev = evaluator.evaluate(fb)
        assert ev.e_score < 1.0
        assert ev.e_score > 0.0

    def test_efficiency_no_estimate(self):
        """无预估 → 默认 0.5。"""
        fb = CognitiveFeedback(
            feedback_id="fb5", source_result_id="r5", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.8, duration_ms=1000, user_alignment=0.8),
            expected=ExpectedOutcome(estimated_duration_ms=0),
        )
        evaluator = OutcomeEvaluator()
        ev = evaluator.evaluate(fb)
        assert ev.e_score == 0.5

    def test_pipeline_generates_feedback(self):
        """ResultUnderstandingLayer.process_result() 生成 CognitiveFeedback。"""
        layer = ResultUnderstandingLayer(auto_learn=False)
        result = layer.process_result(
            output="test",
            capability_id="code_gen",
            provider_id="gpt4",
            outcome="success",
            quality_score=0.85,
            user_satisfaction=0.9,
            duration_ms=1000,
        )
        assert result.validated is True
        assert result.cognitive_feedback is not None
        assert result.cognitive_feedback.evaluation.score > 0.5
        assert result.result_id == result.cognitive_feedback.feedback_id

    def test_pipeline_rejected_feedback(self):
        """低 alignment 的 Pipeline 产出 REJECTED evaluation。"""
        layer = ResultUnderstandingLayer(auto_learn=False)
        result = layer.process_result(
            output="test",
            capability_id="code_gen",
            provider_id="gpt4",
            outcome="success",
            quality_score=0.9,
            user_satisfaction=0.2,
            duration_ms=500,
        )
        fb = result.cognitive_feedback
        assert fb.evaluation.status == EvaluationStatus.REJECTED_USER_MISALIGNED
        assert fb.evaluation.score == 0.0

    def test_convenience_function(self):
        """evaluate_feedback() 便捷函数。"""
        fb = CognitiveFeedback(
            feedback_id="fb6", source_result_id="r6", evaluator_version="0.1",
            capability_id="code_gen", provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.7, duration_ms=100.0, user_alignment=0.8),
        )
        ev = evaluate_feedback(fb)
        assert ev.score > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# §3: Calibration Store
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalibrationStore:

    def test_cold_start_not_applied(self):
        """样本不足 → 不应用。"""
        store = CalibrationStore()
        result = store.record_calibration("code_gen", "gpt4", 0.1)
        assert result.applied is False
        assert result.reason == "INSUFFICIENT_SAMPLES"

    def test_enough_samples_applied(self):
        """样本达到门槛 → 本地校准累计（S2.14: 后端未接线，诚实降级）。

        原断言 applied=True 依赖对不存在方法的调用假成功——
        修复后 applied=False 如实上报，delta 仍在本地累计。
        """
        store = CalibrationStore()
        for _ in range(CALIBRATION_MIN_SAMPLES - 1):
            store.record_calibration("code_gen", "gpt4", 0.05)
        result = store.record_calibration("code_gen", "gpt4", 0.05)
        assert result.applied is False
        assert "CALIBRATED" in result.reason
        assert result.samples >= CALIBRATION_MIN_SAMPLES

    def test_cumulative_delta(self):
        """累计 delta 反映所有样本的平均。"""
        store = CalibrationStore()
        store.record_calibration("code_gen", "gpt4", 0.1)
        store.record_calibration("code_gen", "gpt4", -0.1)
        store.record_calibration("code_gen", "gpt4", 0.0)
        store.record_calibration("code_gen", "gpt4", 0.0)
        result = store.record_calibration("code_gen", "gpt4", 0.0)
        assert result.applied is False  # S2.14: 诚实降级
        assert abs(result.cumulative_delta) < 0.001  # 总和为 0

    def test_get_status(self):
        """get_status 返回正确状态。"""
        store = CalibrationStore()
        store.record_calibration("agent_x", "p1", 0.1)
        store.record_calibration("agent_x", "p1", 0.1)
        status = store.get_status("agent_x", "p1")
        assert status["samples"] == 2
        assert status["ready"] is False

    def test_separate_keys(self):
        """不同 key 的样本隔离。"""
        store = CalibrationStore()
        store.record_calibration("a", "p1", 0.1)
        store.record_calibration("a", "p1", 0.1)
        store.record_calibration("b", "p2", 0.1)
        assert store.get_status("a", "p1")["samples"] == 2
        assert store.get_status("b", "p2")["samples"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# §4: AdaptiveParamGuard
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveParamGuard:

    def test_allow_adaptive_param(self):
        """允许调整自适应参数。"""
        guard = AdaptiveParamGuard()
        assert guard.adjust("attention_relevance_weight", 0.05)

    def test_block_immutable_param(self):
        """拒绝修改不可变参数。"""
        guard = AdaptiveParamGuard()
        with pytest.raises(PermissionDeniedError):
            guard.adjust("constitution", 0.01)
        with pytest.raises(PermissionDeniedError):
            guard.adjust("goal_ownership", 0.01)

    def test_single_step_cap(self):
        """单步变化 > MAX_SINGLE_STEP_DELTA → 被拒绝。"""
        guard = AdaptiveParamGuard()
        big_delta = MAX_SINGLE_STEP_DELTA + 0.01
        assert guard.adjust("attention_relevance_weight", big_delta) is False

    def test_daily_budget(self):
        """日累计 > MAX_DAILY_MUTATION_BUDGET → 被拒绝。"""
        guard = AdaptiveParamGuard()
        # 消耗大部分预算（用小的单步不超过 MAX_SINGLE_STEP_DELTA）
        step = 0.05  # < MAX_SINGLE_STEP_DELTA
        assert guard.adjust("planning_confidence_threshold", step) is True
        assert guard.adjust("planning_confidence_threshold", step) is True
        assert guard.adjust("planning_confidence_threshold", step) is True
        # 已消耗 0.15，再 0.05 → 0.20 ok
        assert guard.adjust("planning_confidence_threshold", step) is True
        # 再 0.05 → 0.25 > MAX_DAILY_MUTATION_BUDGET(0.2)
        assert guard.adjust("planning_confidence_threshold", step) is False

    def test_planning_confidence_clamp(self):
        """planning_confidence_threshold 被 clamp 到 [0.1, 0.9]。"""
        guard = AdaptiveParamGuard()
        guard.adjust("planning_confidence_threshold", -1.0)  # 从 0.5 降到 0.1
        assert guard.params.planning_confidence_threshold >= 0.099
        guard.adjust("planning_confidence_threshold", 1.0)   # 到 0.9
        assert guard.params.planning_confidence_threshold <= 0.901

    def test_get_adaptation_state(self):
        """get_adaptation_state 返回结构。"""
        guard = AdaptiveParamGuard()
        guard.adjust("attention_relevance_weight", 0.03)
        state = guard.get_adaptation_state()
        assert "attention_relevance_weight" in state
        assert "planning_confidence_threshold" in state
        assert "daily_deltas" in state

    def test_unknown_param_returns_false(self):
        """未注册参数返回 False（不报错）。"""
        guard = AdaptiveParamGuard()
        assert guard.adjust("unknown_parameter", 0.01) is False


# ═══════════════════════════════════════════════════════════════════════════════
# §5: Evidence Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvidencePipeline:

    def _make_good_feedback(self, fb_id="fb1", score=0.9):
        return CognitiveFeedback(
            feedback_id=fb_id,
            source_result_id="r1",
            evaluator_version="0.1",
            capability_id="code_gen",
            provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=score, duration_ms=100.0, user_alignment=0.9),
            evaluation=OutcomeEvaluation(score=score, status=EvaluationStatus.ACCEPTED),
        )

    def _make_rejected_feedback(self, fb_id="fbR"):
        return CognitiveFeedback(
            feedback_id=fb_id,
            source_result_id="rR",
            evaluator_version="0.1",
            capability_id="code_gen",
            provider_id="gpt4",
            actual=ActualOutcome(success=True, quality_score=0.5, duration_ms=100.0, user_alignment=0.1),
            evaluation=OutcomeEvaluation(score=0.0, status=EvaluationStatus.REJECTED_USER_MISALIGNED),
        )

    def test_accept_good_feedback(self):
        """高质量 feedback 被接受。"""
        pipeline = EvidencePipeline()
        fb = self._make_good_feedback()
        result = pipeline.process_feedback(fb)
        assert result.accepted is True
        assert result.samples == 1

    def test_reject_rejected_feedback(self):
        """被 evaluator reject 的 feedback 不进 pipeline。"""
        pipeline = EvidencePipeline()
        fb = self._make_rejected_feedback()
        result = pipeline.process_feedback(fb)
        assert result.accepted is False
        assert result.reason == "evaluation_rejected"

    def test_evidence_accumulation(self):
        """同 statement → 合并 Evidence。"""
        pipeline = EvidencePipeline()
        for i in range(3):
            fb = self._make_good_feedback(fb_id=f"fb{i}")
            pipeline.process_feedback(fb)
        summary = pipeline.get_pool_summary()
        assert summary["pool_size"] == 1
        assert summary["total_evidence"] == 3

    def test_state_transition(self):
        """FeedbackState: TEMPORARY → CONFIRMED → PROMOTED。"""
        pipeline = EvidencePipeline()
        # 1 sample → TEMPORARY
        fb = self._make_good_feedback("fb0")
        r = pipeline.process_feedback(fb)
        assert r.new_state == FeedbackState.TEMPORARY

        # 5+ samples → CONFIRMED
        for i in range(1, 10):
            fb = self._make_good_feedback(f"fb{i}")
            r = pipeline.process_feedback(fb)
        assert r.samples >= 5
        # 但 promotion 可能未 ready（similar 不足）
        # 至少 confirmed
        assert r.new_state in (FeedbackState.CONFIRMED, FeedbackState.PROMOTED)


# ═══════════════════════════════════════════════════════════════════════════════
# §6: DriftDetector
# ═══════════════════════════════════════════════════════════════════════════════

class TestDriftDetector:

    def test_no_alert_on_good_scores(self):
        """正常分数不触发报警。"""
        detector = DriftDetector()
        for _ in range(5):
            alert = detector.check_goal_drift(0.9)
            assert alert is None

    def test_preference_drift_after_continuous_low(self):
        """连续低 alignment → DriftAlert。"""
        detector = DriftDetector()
        for _ in range(5):
            detector.check_goal_drift(0.25)  # < 0.3
        alert = detector.check_goal_drift(0.25)
        assert alert is not None
        assert alert.drift_type == DriftType.PREFERENCE
        assert alert.severity >= DriftSeverity.HIGH

    def test_reset_after_recovery(self):
        """恢复后计数重置。"""
        detector = DriftDetector()
        detector.check_goal_drift(0.25)
        detector.check_goal_drift(0.25)
        # recovery
        detector.check_goal_drift(0.9)
        detector.check_goal_drift(0.9)
        # 计数应已衰减
        alert = detector.check_goal_drift(0.9)
        assert alert is None

    def test_capability_drift(self):
        """单一 Agent 使用率 > 70% → CapabilityDrift。"""
        detector = DriftDetector()
        for _ in range(8):
            detector.record_capability_usage("agent_a")
        for _ in range(2):
            detector.record_capability_usage("agent_b")  # 20% others
        alert = detector.check_capability_drift()
        assert alert is not None
        assert alert.drift_type == DriftType.CAPABILITY
        assert alert.current_value > 0.7

    def test_confidence_drift(self):
        """持续高 calibration_delta → ConfidenceDrift。"""
        detector = DriftDetector()
        for _ in range(5):
            detector.check_confidence_drift(0.35)  # > 0.3
        alert = detector.check_confidence_drift(0.35)
        assert alert is not None
        assert alert.drift_type == DriftType.CONFIDENCE

    def test_check_all_aggregation(self):
        """check_all 返回列表，不自动修正。"""
        detector = DriftDetector()
        alerts = detector.check_all(alignment_score=0.2, calibration_delta=0.4)
        # 可能触发 preference + confidence drift
        assert isinstance(alerts, list)
        for alert in alerts:
            assert isinstance(alert, DriftAlert)
            assert alert.drift_type in (DriftType.PREFERENCE, DriftType.CONFIDENCE, DriftType.CAPABILITY)

    def test_get_status(self):
        """get_status 返回检测器状态。"""
        detector = DriftDetector()
        detector.check_goal_drift(0.9)
        detector.check_goal_drift(0.5)
        status = detector.get_status()
        assert "total_executions" in status
        assert "avg_alignment" in status
        assert 0.0 <= status["avg_alignment"] <= 1.0
