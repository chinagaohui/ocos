"""T8–T13: Data Contract Boundary Tests

验证 ExperienceRecord 创建时的类型约束强制执行。
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import pytest

from tests.phase10.conftest import (
    ContractViolation,
    ExperienceRecord,
    OutcomeType,
    SourceType,
    make_experience,
)


# ===================================================================
# T8 — ExperienceRecord Creation
# ===================================================================

class TestT8_ExperienceRecordCreation:
    """T8: 创建合法的 ExperienceRecord（验证合约可接受正常输入）。"""

    def test_minimal_creation(self):
        """合法输入：创建最基本的 ExperienceRecord。"""
        record = make_experience()
        assert record.experience_id == "exp-test-001"
        assert record.source == "observation"
        assert record.hypothesis == "Test_Strategy"
        assert record.outcome == "success"
        assert 0 <= record.raw_confidence <= 1.0
        assert 0 <= record.calibrated_confidence <= 1.0
        assert record.is_rule is False
        assert record.is_decision is False
        assert record.is_obligation is False

    def test_full_fields_creation(self):
        """合法输入：所有字段填满。"""
        record = ExperienceRecord(
            experience_id="exp-999",
            source="user_feedback",
            hypothesis="Full_Test",
            outcome="partial",
            raw_confidence=0.5,
            calibrated_confidence=0.45,
            scope="domain:writing:outline",
            limitations=["小样本", "仅适用于小说"],
            metadata={"user_rating": 4},
        )
        assert record.experience_id == "exp-999"
        assert record.limitations == ["小样本", "仅适用于小说"]
        assert record.metadata == {"user_rating": 4}

    def test_timestamp_auto_generated(self):
        """timestamp 会自动生成 ISO 格式字符串。"""
        record = make_experience()
        assert bool(re.match(r"\d{4}-\d{2}-\d{2}T", record.timestamp))


# ===================================================================
# T9 — is_rule=False Enforcement
# ===================================================================

class TestT9_IsRuleEnforcement:
    """T9: is_rule=True 必须被 ContractViolation 拒绝。"""

    def test_is_rule_true_raises(self):
        """is_rule=True → ContractViolation(AUTHORITY_FLAG_VIOLATION)。"""
        with pytest.raises(ContractViolation) as exc:
            ExperienceRecord(
                experience_id="exp-bad",
                source="observation",
                hypothesis="Bad",
                outcome="failure",
                raw_confidence=0.5,
                calibrated_confidence=0.5,
                scope="domain:test:cond",
                is_rule=True,
            )
        assert "AUTHORITY_FLAG_VIOLATION" in str(exc.value)

    def test_is_rule_false_accepted(self):
        """is_rule=False (默认) 正常通过。"""
        record = make_experience(is_rule=False)
        assert record.is_rule is False

    def test_is_rule_implicitly_false(self):
        """不传 is_rule 默认 False。"""
        record = make_experience()
        assert record.is_rule is False


# ===================================================================
# T10 — is_decision & is_obligation Enforcement
# ===================================================================

class TestT10_AuthorityFlagsEnforcement:
    """T10: is_decision=True / is_obligation=True 必须失败。"""

    def test_is_decision_true_raises(self):
        with pytest.raises(ContractViolation) as exc:
            make_experience(is_decision=True)
        assert "AUTHORITY_FLAG_VIOLATION" in str(exc.value)

    def test_is_obligation_true_raises(self):
        with pytest.raises(ContractViolation) as exc:
            make_experience(is_obligation=True)
        assert "AUTHORITY_FLAG_VIOLATION" in str(exc.value)

    def test_all_authority_flags_false_accepted(self):
        """所有 authority flag=False 正常。"""
        record = make_experience(
            is_rule=False, is_decision=False, is_obligation=False,
        )
        assert record.is_rule is False
        assert record.is_decision is False
        assert record.is_obligation is False

    def test_mixed_authority_flags(self):
        """混合 flag：部分 False 部分 True 仍失败。"""
        with pytest.raises(ContractViolation):
            make_experience(is_rule=False, is_decision=False, is_obligation=True)


# ===================================================================
# T11 — Historical Failure ≠ Veto
# ===================================================================

class TestT11_HistoricalFailureNotVeto:
    """T11: 即使 100 次历史失败，仍可以创建 ExperienceRecord 和提出假设。

    对应 ABI §4.4 Exploration Preservation Test。
    """

    def test_100_failures_not_obligation(self):
        """100 次 failure 仍可创建记录（失败历史不产生阻止义务）。"""
        for i in range(100):
            record = make_experience(
                experience_id=f"exp-fail-{i:03d}",
                source="observation",
                hypothesis="Strategy_X",
                outcome="failure",
                raw_confidence=0.9,
                calibrated_confidence=0.9,
                scope="domain:code_review:python",
            )
            # 合约不能因为历史失败而阻止记录创建
            assert record.outcome == "failure"
            assert record.is_obligation is False  # 没有阻止义务

    def test_failure_history_does_not_force_block(self):
        """失败历史 → 新 Hypothesis 仍然合法可创建。"""
        # 这个测试验证的是"创建假设的能力"不被经验影响
        for i in range(100):
            make_experience(
                experience_id=f"exp-block-{i:03d}",
                hypothesis="Always_Failing_Strategy",
                outcome="failure",
                raw_confidence=0.95,
            )
        # 新假设仍然可以创建（创建本身不会因历史失败被合约阻止）
        new_hypothesis = make_experience(
            experience_id="exp-new-hypothesis",
            hypothesis="Same_Failing_Strategy",
            outcome="success",
            raw_confidence=0.1,  # 低 confidence 但仍然合法
        )
        assert new_hypothesis.hypothesis == "Same_Failing_Strategy"


# ===================================================================
# T12 — Confidence Range [0, 1]
# ===================================================================

class TestT12_ConfidenceRange:
    """T12: raw_confidence 和 calibrated_confidence 必须在 [0, 1]。"""

    @pytest.mark.parametrize("field", ["raw_confidence", "calibrated_confidence"])
    @pytest.mark.parametrize("bad_value", [-0.1, -1.0, 1.001, 2.0, -0.01])
    def test_out_of_range_raises(self, field: str, bad_value: float):
        """<0 或 >1 → ContractViolation(CONFIDENCE_RANGE)。"""
        kwargs = {field: bad_value}
        with pytest.raises(ContractViolation) as exc:
            make_experience(**kwargs)
        assert "CONFIDENCE_RANGE" in str(exc.value)

    @pytest.mark.parametrize("field", ["raw_confidence", "calibrated_confidence"])
    @pytest.mark.parametrize("good_value", [0.0, 0.5, 1.0, 0.333, 0.99])
    def test_boundary_values_accepted(self, field: str, good_value: float):
        """边界值 0.0 和 1.0 以及中间值合法。"""
        kwargs = {field: good_value}
        record = make_experience(**kwargs)
        assert getattr(record, field) == good_value


# ===================================================================
# T13 — Source Validation（含 Simulation 置信度封顶）
# ===================================================================

class TestT13_SourceValidation:
    """T13: source 枚举验证 + simulation 来源置信度上限 0.5。"""

    @pytest.mark.parametrize("invalid_source", ["invalid", "prediction", "history", ""])
    def test_invalid_source_raises(self, invalid_source: str):
        """无效 source → ContractViolation(INVALID_SOURCE)。"""
        with pytest.raises(ContractViolation) as exc:
            make_experience(source=invalid_source)
        assert "INVALID_SOURCE" in str(exc.value)

    @pytest.mark.parametrize("valid_source", [
        "observation", "decision", "simulation", "user_feedback",
    ])
    def test_valid_source_accepted(self, valid_source: str):
        """所有 valid source 正常通过。"""
        confidence = 0.4 if valid_source == "simulation" else 0.8
        record = make_experience(source=valid_source, calibrated_confidence=confidence)
        assert record.source == valid_source

    def test_simulation_confidence_cap(self):
        """simulation + calibrated_confidence > 0.5 → ContractViolation。

        对应 ABI §2.5: 模拟来源的 confidence 上限 0.5。
        """
        with pytest.raises(ContractViolation) as exc:
            make_experience(source="simulation", calibrated_confidence=0.6)
        assert "SIMULATION_CONFIDENCE_CAP" in str(exc.value)

    def test_simulation_confidence_at_cap(self):
        """simulation + calibrated_confidence=0.5 合法（边界值）。"""
        record = make_experience(
            source="simulation",
            raw_confidence=0.5,
            calibrated_confidence=0.5,
        )
        assert record.source == "simulation"
        assert record.calibrated_confidence == 0.5

    def test_simulation_confidence_below_cap(self):
        """simulation + calibrated_confidence<0.5 合法。"""
        record = make_experience(
            source="simulation",
            raw_confidence=0.3,
            calibrated_confidence=0.3,
        )
        assert record.calibrated_confidence == 0.3
