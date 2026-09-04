"""OCOS risk_engine 风险评估测试。"""

import pytest

from ocos.decision.risk_engine import RiskEngine
from ocos.decision.decision_types import DecisionOption, OptionType, RiskLevel


class TestRiskEngine:
    @pytest.fixture
    def engine(self):
        return RiskEngine()

    def test_low_confidence_high_risk(self, engine):
        opt = DecisionOption(
            option_id="o1",
            description="risky",
            confidence=0.2,
            risk_score=0.0,
            value_score=0.5,
            source="generated",
        )
        ra = engine.assess(opt)
        assert ra.category.name == "OPERATIONAL"
        assert ra.score == 0.8  # confidence < 0.3 → score = 0.8
        assert ra.level == RiskLevel.CRITICAL  # 0.8 >= 0.8 → CRITICAL

    def test_wisdom_suggested_medium_risk(self, engine):
        opt = DecisionOption(
            option_id="o2",
            description="wisdom",
            confidence=0.7,
            risk_score=0.0,
            value_score=0.5,
            source="wisdom_suggested",
        )
        ra = engine.assess(opt)
        assert ra.category.name == "DEPENDENCY"
        # score = 0.3 + (1 - 0.7) * 0.3 = 0.39
        assert abs(ra.score - 0.39) < 0.01

    def test_prerequisites_increase_risk(self, engine):
        opt = DecisionOption(
            option_id="o3",
            description="needs setup",
            confidence=0.8,
            risk_score=0.0,
            value_score=0.5,
            source="generated",
            prerequisites=["p1", "p2", "p3"],
        )
        ra = engine.assess(opt)
        assert ra.category.name == "RESOURCE"
        # score = min(0.8, 3 * 0.15) = 0.45
        assert abs(ra.score - 0.45) < 0.01

    def test_default_operational_risk(self, engine):
        opt = DecisionOption(
            option_id="o4",
            description="normal",
            confidence=0.8,
            risk_score=0.0,
            value_score=0.5,
            source="generated",
        )
        ra = engine.assess(opt)
        assert ra.category.name == "OPERATIONAL"
        assert abs(ra.score - 0.35) < 0.01

    def test_score_to_level_mapping(self, engine):
        assert engine._score_to_level(0.1) == RiskLevel.NEGLIGIBLE
        assert engine._score_to_level(0.3) == RiskLevel.LOW
        assert engine._score_to_level(0.5) == RiskLevel.MEDIUM
        assert engine._score_to_level(0.7) == RiskLevel.HIGH
        assert engine._score_to_level(0.9) == RiskLevel.CRITICAL

    def test_assess_all(self, engine):
        opts = [
            DecisionOption(option_id=f"o{i}", description="d", confidence=0.5,
                          risk_score=0.0, value_score=0.5, source="generated")
            for i in range(3)
        ]
        results = engine.assess_all(opts)
        assert len(results) == 3
        assert all(r.option_id.startswith("o") for r in results)

    def test_custom_threshold(self):
        engine = RiskEngine(risk_threshold=0.5)
        assert engine.risk_threshold == 0.5
