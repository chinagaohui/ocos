"""OCOS value_model 价值评估测试。"""

import pytest

from ocos.decision.value_model import ValueModel
from ocos.decision.decision_types import DecisionOption, OptionType, ValueDimension


class TestValueModel:
    @pytest.fixture
    def model(self):
        return ValueModel()

    def test_default_weights_sum_to_one(self, model):
        total = sum(model.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_safety_weight_highest(self, model):
        assert model.weights[ValueDimension.SAFETY] == 0.25
        assert model.weights[ValueDimension.ALIGNMENT] == 0.20
        assert model.weights[ValueDimension.RELIABILITY] == 0.20

    def test_evaluate_basic(self, model):
        opt = DecisionOption(
            option_id="o1",
            description="investigate",
            option_type=OptionType.INVESTIGATE,
            confidence=0.8,
            risk_score=0.2,
            value_score=0.6,
            source="generated",
        )
        ve = model.evaluate(opt)
        assert ve.option_id == "o1"
        assert ve.dimensions[ValueDimension.RELIABILITY] == 0.8
        assert ve.dimensions[ValueDimension.SAFETY] == 0.8  # 1 - 0.2
        assert ve.dimensions[ValueDimension.ALIGNMENT] == 0.6
        assert ve.overall_score > 0

    def test_evaluate_direct_action(self, model):
        opt = DecisionOption(
            option_id="o2",
            description="direct",
            option_type=OptionType.DIRECT_ACTION,
            confidence=0.9,
            risk_score=0.1,
            value_score=0.7,
            source="generated",
        )
        ve = model.evaluate(opt)
        # direct_action: efficiency=0.7, learning=0.6
        assert ve.dimensions[ValueDimension.EFFICIENCY] == 0.7
        assert ve.dimensions[ValueDimension.LEARNING] == 0.6

    def test_evaluate_do_nothing(self, model):
        opt = DecisionOption(
            option_id="o3",
            description="wait",
            option_type=OptionType.DO_NOTHING,
            confidence=0.5,
            risk_score=0.3,
            value_score=0.4,
            source="generated",
        )
        ve = model.evaluate(opt)
        # do_nothing: efficiency=0.6, learning=0.0
        assert ve.dimensions[ValueDimension.EFFICIENCY] == 0.6
        assert ve.dimensions[ValueDimension.LEARNING] == 0.0

    def test_evaluate_investigate(self, model):
        opt = DecisionOption(
            option_id="o4",
            description="investigate",
            option_type=OptionType.INVESTIGATE,
            confidence=0.7,
            risk_score=0.2,
            value_score=0.5,
            source="generated",
        )
        ve = model.evaluate(opt)
        # investigate: efficiency=0.4, learning=0.8
        assert ve.dimensions[ValueDimension.EFFICIENCY] == 0.4
        assert ve.dimensions[ValueDimension.LEARNING] == 0.8

    def test_evaluate_all(self, model):
        opts = [
            DecisionOption(option_id=f"o{i}", description="d",
                          confidence=0.5, risk_score=0.3, value_score=0.4,
                          source="generated")
            for i in range(3)
        ]
        results = model.evaluate_all(opts)
        assert len(results) == 3
        assert all(r.option_id.startswith("o") for r in results)

    def test_novelty_for_do_nothing(self, model):
        """DO_NOTHING 的新颖性最低。"""
        opt = DecisionOption(
            option_id="o5",
            description="nothing",
            option_type=OptionType.DO_NOTHING,
            confidence=0.5,
            risk_score=0.3,
            value_score=0.4,
            source="generated",
        )
        ve = model.evaluate(opt)
        # do_nothing: novelty should be lowest
        assert ve.dimensions[ValueDimension.NOVELTY] <= 0.3

    def test_custom_weights(self):
        model = ValueModel(weights={
            ValueDimension.SAFETY: 0.5,
            ValueDimension.ALIGNMENT: 0.3,
            ValueDimension.RELIABILITY: 0.2,
        })
        assert model.weights[ValueDimension.SAFETY] == 0.5
