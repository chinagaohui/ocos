"""T31–T35: Calibration Engine Boundary Tests

验证 CALIBRATION_ENGINE_CONTRACT.md 中的五项约束。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.phase10.conftest import (
    CalibrationEngine,
    CalibrationEvent,
    CalibrationReason,
    ContractViolation,
    ExperienceStore,
    make_experience,
)


@pytest.fixture
def store() -> ExperienceStore:
    return ExperienceStore()


@pytest.fixture
def engine(store: ExperienceStore) -> CalibrationEngine:
    return CalibrationEngine(store)


@pytest.fixture
def saved_experience(store: ExperienceStore) -> str:
    record = make_experience(
        experience_id="exp-cal",
        outcome="success",
        raw_confidence=0.8,
        calibrated_confidence=0.8,
    )
    store.save(record)
    return "exp-cal"


# ===================================================================
# T31 — Confidence Decrease Only (Auto)
# ===================================================================

class TestT31_ConfidenceDecreaseOnly:
    """T31: 自动校准只能降低 confidence，不能升高。"""

    def test_time_decay_decreases(self, engine: CalibrationEngine, saved_experience: str):
        result = engine.apply_time_decay(saved_experience, decay_rate=0.1)
        assert result.delta < 0
        assert result.new_confidence < result.old_confidence

    def test_scope_mismatch_decreases(self, engine: CalibrationEngine, saved_experience: str):
        result = engine.apply_scope_mismatch_penalty(
            saved_experience, penalty=0.2,
        )
        assert result.delta < 0
        assert result.new_confidence < result.old_confidence

    def test_auto_increase_raises(self):
        """尝试创建 delta>0 的自动校准事件 → ContractViolation。"""
        with pytest.raises(ContractViolation) as exc:
            CalibrationEvent(
                experience_id="exp-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                old_confidence=0.5,
                new_confidence=0.7,
                delta=0.2,
                reason=CalibrationReason.TIME_DECAY.value,
                source="engine",
                actor="calibration_engine",
            )
        assert "AUTO_INCREASE_VIOLATION" in str(exc.value)

    def test_auto_no_op_raises(self):
        """delta=0 → ContractViolation(NO_OP_CALIBRATION)。"""
        with pytest.raises(ContractViolation) as exc:
            CalibrationEvent(
                experience_id="exp-1",
                timestamp=datetime.now(timezone.utc).isoformat(),
                old_confidence=0.5,
                new_confidence=0.5,
                delta=0.0,
                reason=CalibrationReason.TIME_DECAY.value,
                source="engine",
                actor="engine",
            )
        assert "NO_OP_CALIBRATION" in str(exc.value)


# ===================================================================
# T32 — No Automatic Increase Methods
# ===================================================================

class TestT32_NoAutoIncreaseMethods:
    """T32: CalibrationEngine 不提供自动增加方法。"""

    def test_no_auto_increase_method(self):
        engine = CalibrationEngine(ExperienceStore())
        # 不应当存在这些方法
        assert not hasattr(engine, "auto_increase")
        assert not hasattr(engine, "success_bonus")
        assert not hasattr(engine, "increase_if_correct")

    def test_only_decrease_methods_exist(self, engine: CalibrationEngine):
        """engine 只暴露减少方法 + manual_adjustment。"""
        expected_methods = {"apply_time_decay", "apply_scope_mismatch_penalty",
                            "apply_manual_adjustment", "get_calibration_history"}
        actual = {m for m in dir(engine) if m.startswith("apply_") or m == "get_calibration_history"}
        # 只能有预期的方法
        actual_public = {m for m in actual if not m.startswith("_")}
        assert actual_public == expected_methods, (
            f"不应存在额外方法: {actual_public - expected_methods}"
        )


# ===================================================================
# T33 — Calibration Event Provenance
# ===================================================================

class TestT33_CalibrationProvenance:
    """T33: 校准事件必须包含 9 个字段的 provenance。"""

    REQUIRED_FIELDS = {
        "experience_id", "timestamp", "old_confidence",
        "new_confidence", "delta", "reason", "source",
        "actor", "metadata",
    }

    def test_provenance_has_all_fields(self, engine: CalibrationEngine, saved_experience: str):
        result = engine.apply_time_decay(saved_experience)
        event_dict = {
            "experience_id": result.experience_id,
            "timestamp": result.timestamp,
            "old_confidence": result.old_confidence,
            "new_confidence": result.new_confidence,
            "delta": result.delta,
            "reason": result.reason,
            "source": result.source,
            "actor": result.actor,
            "metadata": result.metadata,
        }
        missing = self.REQUIRED_FIELDS - set(event_dict.keys())
        assert not missing, f"缺失 provenance 字段: {missing}"

    def test_calibration_event_dataclass_completeness(self):
        """CalibrationEvent 作为 dataclass 包含全部 9 字段。"""
        event = CalibrationEvent(
            experience_id="e1",
            timestamp="2025-01-01T00:00:00",
            old_confidence=0.8,
            new_confidence=0.7,
            delta=-0.1,
            reason="time_decay",
            source="engine",
            actor="calibration_engine",
        )
        for field in self.REQUIRED_FIELDS:
            assert hasattr(event, field), f"CalibrationEvent 缺少 {field}"

    def test_provenance_stored_in_store(self, engine: CalibrationEngine, saved_experience: str):
        engine.apply_time_decay(saved_experience, decay_rate=0.1)
        history = engine.get_calibration_history(saved_experience)
        assert len(history) == 1
        event = history[0]
        missing = self.REQUIRED_FIELDS - set(event.keys())
        assert not missing, f"Store 中的 provenance 缺失字段: {missing}"


# ===================================================================
# T34 — No Authority Escalation
# ===================================================================

class TestT34_NoAuthorityEscalation:
    """T34: 校准后 confidence 即使接近 1.0，authority flag 仍为 False。"""

    def test_high_confidence_no_rule_escalation(self, store: ExperienceStore):
        """confidence=0.95 不改变 is_rule。"""
        record = make_experience(
            experience_id="exp-high",
            source="observation",
            outcome="success",
            raw_confidence=0.95,
            calibrated_confidence=0.95,
        )
        assert record.is_rule is False
        assert record.is_decision is False
        assert record.is_obligation is False

    def test_manual_adjustment_to_high_still_no_authority(
        self, engine: CalibrationEngine, saved_experience: str,
    ):
        """手动调高到 0.99 也不产生 authority。"""
        result = engine.apply_manual_adjustment(
            saved_experience, new_confidence=0.99,
        )
        assert result.new_confidence == 0.99
        # 验证 Store 中的记录仍无 authority
        record = engine._store.get(saved_experience)
        assert record is not None
        assert record.is_rule is False
        assert record.is_decision is False
        assert record.is_obligation is False

    def test_calibration_engine_runtime_assertion(self, engine: CalibrationEngine):
        """_validate_no_authority_escalation 通过正常输入不报错。"""
        record = make_experience()
        engine._validate_no_authority_escalation(record)  # 不应抛异常

    def test_calibration_applied_lower_still_no_authority(
        self, engine: CalibrationEngine, saved_experience: str,
    ):
        engine.apply_time_decay(saved_experience, decay_rate=0.3)
        record = engine._store.get(saved_experience)
        assert record is not None
        assert record.is_rule is False


# ===================================================================
# T35 — No Winner Bias
# ===================================================================

class TestT35_NoWinnerBias:
    """T35: success 和 failure 的校准衰减速率一致。"""

    def test_success_decay_rate(self, store: ExperienceStore, engine: CalibrationEngine):
        id_s = "exp-s"
        store.save(make_experience(
            experience_id=id_s,
            outcome="success",
            calibrated_confidence=0.8,
        ))
        r1 = engine.apply_time_decay(id_s, decay_rate=0.1)
        assert r1.delta == pytest.approx(-0.1)
        assert r1.new_confidence == pytest.approx(0.7)

    def test_failure_decay_rate(self, store: ExperienceStore, engine: CalibrationEngine):
        id_f = "exp-f"
        store.save(make_experience(
            experience_id=id_f,
            outcome="failure",
            calibrated_confidence=0.8,
        ))
        r1 = engine.apply_time_decay(id_f, decay_rate=0.1)
        assert r1.delta == pytest.approx(-0.1)
        assert r1.new_confidence == pytest.approx(0.7)

    def test_both_success_failure_decay_identical(self, store: ExperienceStore, engine: CalibrationEngine):
        """success 和 failure 经历同样衰减后 confidence 下降相同。"""
        id_s = "exp-s"
        id_f = "exp-f"
        store.save(make_experience(
            experience_id=id_s, outcome="success", calibrated_confidence=0.8,
        ))
        store.save(make_experience(
            experience_id=id_f, outcome="failure", calibrated_confidence=0.8,
        ))
        rs = engine.apply_time_decay(id_s, decay_rate=0.15)
        rf = engine.apply_time_decay(id_f, decay_rate=0.15)
        assert rs.delta == rf.delta
        assert rs.new_confidence == rf.new_confidence

    def test_scope_mismatch_not_outcome_based(self, store: ExperienceStore, engine: CalibrationEngine):
        id_s = "exp-ss"
        id_f = "exp-ff"
        store.save(make_experience(
            experience_id=id_s, outcome="success", calibrated_confidence=0.8,
        ))
        store.save(make_experience(
            experience_id=id_f, outcome="failure", calibrated_confidence=0.8,
        ))
        rs = engine.apply_scope_mismatch_penalty(id_s, penalty=0.2)
        rf = engine.apply_scope_mismatch_penalty(id_f, penalty=0.2)
        # 相同的 penalty → 相同的 delta（不因 outcome 不同而不同）
        assert rs.delta == rf.delta
