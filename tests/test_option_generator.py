"""OCOS option_generator 决策选项生成测试。"""

import pytest

from ocos.decision.option_generator import OptionGenerator
from ocos.decision.decision_types import DecisionContext, OptionType


class TestOptionGenerator:
    @pytest.fixture
    def generator(self):
        return OptionGenerator()

    def test_generate_empty_context(self, generator):
        ctx = DecisionContext(context_id="c1")
        opts = generator.generate(ctx)
        # 至少有一个 defer 基线
        assert len(opts) >= 1
        assert opts[0].option_type == OptionType.DEFER

    def test_generate_with_wisdom_hints(self, generator):
        ctx = DecisionContext(
            context_id="c2",
            wisdom_hints=["always check inputs", "validate before acting"],
        )
        opts = generator.generate(ctx)
        # defer + 2 wisdom hints = 3
        assert len(opts) == 3
        assert opts[0].option_type == OptionType.DEFER
        assert opts[1].source == "wisdom_suggested"
        assert opts[2].source == "wisdom_suggested"

    def test_generate_investigate_when_both_goal_and_world(self, generator):
        ctx = DecisionContext(
            context_id="c3",
            goal_summary="write a novel",
            world_snapshot="current market trend",
        )
        opts = generator.generate(ctx)
        types = {o.option_type for o in opts}
        assert OptionType.INVESTIGATE in types

    def test_generate_no_investigate_without_world(self, generator):
        ctx = DecisionContext(
            context_id="c4",
            goal_summary="write a novel",
            # no world_snapshot
        )
        opts = generator.generate(ctx)
        types = {o.option_type for o in opts}
        assert OptionType.INVESTIGATE not in types

    def test_max_options_cap(self, generator):
        generator.max_options = 3
        ctx = DecisionContext(
            context_id="c5",
            wisdom_hints=["h1", "h2", "h3", "h4"],
            goal_summary="g",
            world_snapshot="w",
        )
        opts = generator.generate(ctx)
        assert len(opts) <= 3

    def test_defer_option_defaults(self, generator):
        ctx = DecisionContext(context_id="c6")
        opts = generator.generate(ctx)
        defer = opts[0]
        assert defer.option_type == OptionType.DEFER
        assert defer.confidence == 1.0
        assert defer.risk_score == 0.0
        assert defer.description == "推迟决策，等待更多信息"

    def test_wisdom_option_defaults(self, generator):
        ctx = DecisionContext(
            context_id="c7",
            wisdom_hints=["test hint"],
        )
        opts = generator.generate(ctx)
        wisdom_opt = opts[1]
        assert wisdom_opt.source == "wisdom_suggested"
        assert wisdom_opt.confidence == 0.7
        assert wisdom_opt.risk_score == 0.3
        assert wisdom_opt.option_type == OptionType.DIRECT_ACTION

    def test_investigate_option_defaults(self, generator):
        ctx = DecisionContext(
            context_id="c8",
            goal_summary="write novel",
            world_snapshot="trend",
        )
        opts = generator.generate(ctx)
        investigate_opts = [o for o in opts if o.option_type == OptionType.INVESTIGATE]
        assert len(investigate_opts) == 1
        inv = investigate_opts[0]
        assert inv.confidence == 0.5
        assert inv.risk_score == 0.2
        assert "写" in inv.description or "investigate" in inv.description.lower() or "调查" in inv.description

    def test_custom_max_options(self):
        gen = OptionGenerator(max_options=5)
        assert gen.max_options == 5

    def test_option_ids_unique(self, generator):
        ctx = DecisionContext(
            context_id="c9",
            wisdom_hints=["h1", "h2"],
            goal_summary="g",
            world_snapshot="w",
        )
        opts = generator.generate(ctx)
        ids = [o.option_id for o in opts]
        assert len(ids) == len(set(ids))
