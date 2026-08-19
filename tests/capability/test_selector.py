"""Phase 23 — Gate 23-03: Capability Selector 测试。

验证:
  23-009: Intent 正确映射到 SkillGraph
  23-010: 多个候选时正确排序
  23-011: 无匹配时优雅降级
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.capability.models import SkillGraph, Skill
from ocos.capability.selector import CapabilitySelector, SelectorResult


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def empty_selector() -> CapabilitySelector:
    """无注册 Graph 的选择器。"""
    return CapabilitySelector()


@pytest.fixture
def populated_selector() -> CapabilitySelector:
    """含多个 Graph 的选择器。"""
    graphs = [
        SkillGraph(
            id="problem_solving",
            name="Problem Solving",
            description="Analyze and solve technical problems",
            metadata={"tags": ["solve", "analyze", "reasoning"]},
        ),
        SkillGraph(
            id="planning",
            name="Planning Strategy",
            description="Create strategic plans",
            metadata={"tags": ["plan", "strategy"]},
        ),
        SkillGraph(
            id="decision",
            name="Decision Making",
            description="Make decisions from options",
            metadata={"tags": ["decide", "choice"]},
        ),
        SkillGraph(
            id="writing",
            name="Content Writing",
            description="Create and write content",
            metadata={"tags": ["create", "write", "generate"]},
        ),
    ]
    return CapabilitySelector(graphs)


# ── 23-009: Intent → Graph 映射 ────────────────────────────────────────────


def test_selector_intent_to_graph_solve(populated_selector):
    """"solve" 关键词应映射到 problem_solving。"""
    result = populated_selector.select("我需要解决一个技术问题")

    assert result.selected_graph is not None
    assert result.selected_graph.id == "problem_solving"
    assert result.confidence > 0


def test_selector_intent_to_graph_plan(populated_selector):
    """"plan" 关键词应映射到 planning。"""
    result = populated_selector.select("制定一个项目计划")

    assert result.selected_graph is not None
    assert result.selected_graph.id == "planning"


def test_selector_intent_to_graph_decide(populated_selector):
    """"decide/make a decision" 关键词应映射到 decision。"""
    result = populated_selector.select("需要做出一个决定")

    assert result.selected_graph is not None
    assert result.selected_graph.id == "decision"


def test_selector_intent_to_graph_create(populated_selector):
    """"create" 关键词应映射到 writing。"""
    result = populated_selector.select("创建一篇技术博客")

    assert result.selected_graph is not None
    assert result.selected_graph.id == "writing"


def test_selector_intent_object_input(populated_selector):
    """Intent 对象应被正确处理。"""
    class MockIntent:
        content = "analyze the system architecture"

    intent = MockIntent()
    result = populated_selector.select(intent)

    assert result.selected_graph is not None
    # "analyze" → problem_solving（因为 problem_solving 有 analyze 标签）
    assert result.selected_graph.id == "problem_solving"


# ── 23-010: Ranking ────────────────────────────────────────────────────────


def test_selector_ranking_multiple_candidates():
    """多个匹配 Graph 时第一个被选中。"""
    graphs = [
        SkillGraph(
            id="problem_solving_1",
            name="Problem Solving v1",
            description="solve problems",
        ),
        SkillGraph(
            id="problem_solving_2",
            name="Advanced Problem Solving",
            description="solve complex problems",
        ),
    ]
    selector = CapabilitySelector(graphs)

    result = selector.select("solve this problem")

    assert result.selected_graph is not None
    assert len(result.candidates) == 2
    assert result.confidence == 0.5  # 1/2
    # 第一个注册的排在前面
    assert result.selected_graph.id == "problem_solving_1"


def test_selector_single_candidate_confidence():
    """单候选应有 1.0 信心。"""
    graph = SkillGraph(id="solve", name="Problem Solver", description="solve problems")
    selector = CapabilitySelector([graph])

    result = selector.select("solve this")

    assert result.selected_graph is not None
    assert result.confidence == 1.0


# ── 23-011: 无匹配降级 ────────────────────────────────────────────────────


def test_selector_no_match(populated_selector):
    """无匹配时返回 None with reason。"""
    result = populated_selector.select("xyzzy quux foo bar")

    assert result.selected_graph is None
    assert result.confidence == 0.0
    assert result.reason  # 应有原因


def test_selector_empty(empty_selector):
    """无注册 Graph 时应返回 None。"""
    result = empty_selector.select("solve this")

    assert result.selected_graph is None
    assert result.confidence == 0.0
    assert "no graphs" in result.reason.lower()


def test_selector_none_intent(populated_selector):
    """None intent 应优雅降级。"""
    result = populated_selector.select(None)

    assert result.selected_graph is None
    assert result.confidence == 0.0


def test_selector_different_keywords():
    """不同关键词应命中不同 Graph。"""
    selector = CapabilitySelector([
        SkillGraph(id="research", name="Research", description="explore and discover"),
        SkillGraph(id="optimize", name="Optimize", description="improve things"),
    ])

    r1 = selector.select("research the topic")
    assert r1.selected_graph.id == "research"

    r2 = selector.select("optimize the code")
    assert r2.selected_graph.id == "optimize"


# ── 额外：register/unregister ──────────────────────────────────────────────


def test_selector_register_unregister():
    """注册/注销应正确更新图集合。"""
    selector = CapabilitySelector()
    graph = SkillGraph(id="test", name="Test")

    selector.register(graph)
    result = selector.select("test")
    assert result.selected_graph is not None

    assert selector.unregister("test") is True
    result2 = selector.select("test")
    assert result2.selected_graph is None

    # 再次注销应返回 False
    assert selector.unregister("test") is False


def test_selector_clear():
    """clear() 应清空所有图。"""
    selector = CapabilitySelector([
        SkillGraph(id="test", name="Test"),
    ])
    result = selector.select("test")
    assert result.selected_graph is not None

    selector.clear()
    result2 = selector.select("test")
    assert result2.selected_graph is None
