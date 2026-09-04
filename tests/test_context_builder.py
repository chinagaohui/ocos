"""OCOS decision/context_builder 测试。"""

import pytest
from ocos.decision.context_builder import ContextBuilder
from ocos.decision.decision_types import DecisionContext


class TestContextBuilder:
    def test_empty_build(self):
        builder = ContextBuilder()
        ctx = builder.build(tick_id=1)
        assert isinstance(ctx, DecisionContext)
        assert ctx.tick_id == 1
        assert ctx.goal_summary == ""
        assert ctx.self_summary == ""

    def test_set_goal_context(self):
        builder = ContextBuilder()
        builder.set_goal_context("Write a novel chapter")
        ctx = builder.build()
        assert ctx.goal_summary == "Write a novel chapter"

    def test_set_self_context(self):
        builder = ContextBuilder()
        builder.set_self_context("Level 3 agent")
        ctx = builder.build()
        assert ctx.self_summary == "Level 3 agent"

    def test_add_wisdom(self):
        builder = ContextBuilder()
        builder.add_wisdom("Always verify inputs")
        builder.add_wisdom("Prefer deterministic over LLM")
        ctx = builder.build()
        assert len(ctx.wisdom_hints) == 2

    def test_add_wisdom_skips_empty(self):
        builder = ContextBuilder()
        builder.add_wisdom("")
        builder.add_wisdom("   ")
        ctx = builder.build()
        assert len(ctx.wisdom_hints) == 0

    def test_set_world_context(self):
        builder = ContextBuilder()
        builder.set_world_context("User preferences loaded")
        ctx = builder.build()
        assert ctx.world_snapshot == "User preferences loaded"

    def test_add_constraint(self):
        builder = ContextBuilder()
        builder.add_constraint("No external API calls")
        ctx = builder.build()
        assert "No external API calls" in ctx.constraints

    def test_add_constraint_skips_empty(self):
        builder = ContextBuilder()
        builder.add_constraint("")
        ctx = builder.build()
        assert len(ctx.constraints) == 0

    def test_full_build(self):
        builder = ContextBuilder()
        builder.set_goal_context("Write chapter 5")
        builder.set_self_context("Senior developer")
        builder.add_wisdom("Be concise")
        builder.set_world_context("Deadline tomorrow")
        builder.add_constraint("Max 5000 words")
        ctx = builder.build(tick_id=42)
        assert ctx.tick_id == 42
        assert ctx.goal_summary == "Write chapter 5"
        assert ctx.self_summary == "Senior developer"
        assert ctx.world_snapshot == "Deadline tomorrow"
        assert "Max 5000 words" in ctx.constraints

    def test_reset(self):
        builder = ContextBuilder()
        builder.set_goal_context("Test goal")
        builder.set_self_context("Test self")
        builder.reset()
        ctx = builder.build()
        assert ctx.goal_summary == ""
        assert ctx.self_summary == ""