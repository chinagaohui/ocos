"""Phase 23 — Gate 23-01: Kahn 拓扑排序 + 环检测。

验证:
  23-001: 正确返回拓扑序
  23-002: 环依赖抛出 CyclicDependencyError
  23-003: 前置 Skill 缺失抛出 UnknownPrerequisiteError
  23-003b: has_cycle() 检测
  23-003c: validate() 完整性检查
  23-003d: Skill fallback_strategy 验证
  23-003e: ProcessGraph 辅助方法
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def skill_infer() -> None:
    """创建简单的推理 Skill。"""
    from ocos.capability.models import Skill  # type: ignore[import-untyped]
    return Skill(
        id="infer",
        name="Inference",
        description="Basic reasoning inference",
        required_capability="reasoning",
    )


@pytest.fixture
def skill_plan() -> None:
    from ocos.capability.models import Skill  # type: ignore[import-untyped]
    return Skill(
        id="plan",
        name="Planning",
        description="Generate execution plan",
        required_capability="planning",
    )


@pytest.fixture
def skill_decide() -> None:
    from ocos.capability.models import Skill  # type: ignore[import-untyped]
    return Skill(
        id="decide",
        name="Decision",
        description="Make decision from alternatives",
        required_capability="decision",
    )


@pytest.fixture
def skill_reflect() -> None:
    from ocos.capability.models import Skill  # type: ignore[import-untyped]
    return Skill(
        id="reflect",
        name="Reflection",
        description="Reflect on outcomes",
        required_capability="reflection",
    )


@pytest.fixture
def skill_learn() -> None:
    from ocos.capability.models import Skill  # type: ignore[import-untyped]
    return Skill(
        id="learn",
        name="Learning",
        description="Learn from experience",
        required_capability="learning",
    )


def make_linear_graph(*skills) -> None:
    """创建 A→B→C 线性图。"""
    from ocos.capability.models import SkillGraph  # type: ignore[import-untyped]
    skill_list = list(skills)
    for i in range(1, len(skill_list)):
        skill_list[i].prerequisite = [skill_list[i - 1].id]

    return SkillGraph(
        id="linear",
        name="Linear Graph",
        description="A → B → C linear chain",
        skills=skill_list,
    )


# ── 23-001 — 拓扑排序 ───────────────────────────────────────────────────────


def test_kahn_topological_order_linear(
    skill_infer, skill_plan, skill_decide
) -> None:
    """线性依赖 infer → plan → decide 拓扑排序。"""
    graph = make_linear_graph(skill_infer, skill_plan, skill_decide)

    order = graph.get_dependency_order()

    assert len(order) == 3
    assert order.index(skill_infer.id) < order.index(skill_plan.id), (
        "infer 应在 plan 之前"
    )
    assert order.index(skill_plan.id) < order.index(skill_decide.id), (
        "plan 应在 decide 之前"
    )


def test_kahn_topological_order_diamond(
    skill_infer, skill_plan, skill_decide, skill_reflect
) -> None:
    """菱形依赖: infer → plan → decide, infer → plan → reflect。"""
    from ocos.capability.models import SkillGraph  # type: ignore[import-untyped]

    skill_plan.prerequisite = [skill_infer.id]
    skill_decide.prerequisite = [skill_plan.id]
    skill_reflect.prerequisite = [skill_plan.id]

    # infer 无前置
    skill_infer.prerequisite = []

    graph = SkillGraph(
        id="diamond",
        name="Diamond",
        skills=[skill_infer, skill_plan, skill_decide, skill_reflect],
    )

    order = graph.get_dependency_order()

    assert len(order) == 4
    assert order[0] == "infer"
    assert order[1] == "plan"
    # decide 和 reflect 的顺序不确定，但都在 plan 之后
    assert order.index("decide") > order.index("plan")
    assert order.index("reflect") > order.index("plan")


def test_kahn_topological_order_independent() -> None:
    """无依赖的独立 Skills。"""
    from ocos.capability.models import SkillGraph, Skill  # type: ignore[import-untyped]

    skills = [
        Skill(id=f"s{i}", name=f"Skill {i}")
        for i in range(5)
    ]

    graph = SkillGraph(id="independent", name="Independent", skills=skills)
    order = graph.get_dependency_order()

    assert len(order) == 5
    assert set(order) == {f"s{i}" for i in range(5)}


def test_kahn_topological_order_chain_of_5(
    skill_infer, skill_plan, skill_decide, skill_reflect, skill_learn
) -> None:
    """五链依赖 infer → plan → decide → reflect → learn。"""
    graph = make_linear_graph(
        skill_infer, skill_plan, skill_decide, skill_reflect, skill_learn
    )

    order = graph.get_dependency_order()

    assert order == ["infer", "plan", "decide", "reflect", "learn"]


# ── 23-002 — 环检测 ─────────────────────────────────────────────────────────


def test_cyclic_dependency_detection_simple_loop(
    skill_infer, skill_plan
) -> None:
    """简单环: infer → plan → infer。"""
    from ocos.capability.models import (
        SkillGraph,
        CyclicDependencyError,
    )  # type: ignore[import-untyped]

    skill_infer.prerequisite = [skill_plan.id]
    skill_plan.prerequisite = [skill_infer.id]

    graph = SkillGraph(
        id="loop",
        name="Simple Loop",
        skills=[skill_infer, skill_plan],
    )

    with pytest.raises(CyclicDependencyError) as exc_info:
        graph.get_dependency_order()

    assert "loop" in str(exc_info.value)
    assert len(exc_info.value.remaining_nodes) >= 1


def test_cyclic_dependency_detection_self_loop() -> None:
    """自环: s1 → s1。"""
    from ocos.capability.models import (
        Skill,
        SkillGraph,
        CyclicDependencyError,
    )  # type: ignore[import-untyped]

    skill = Skill(id="self", name="Self-referencing")
    skill.prerequisite = ["self"]

    graph = SkillGraph(id="self_loop", name="Self Loop", skills=[skill])

    with pytest.raises(CyclicDependencyError):
        graph.get_dependency_order()


def test_cyclic_dependency_long_chain() -> None:
    """长链环: A→B→C→D→A。"""
    from ocos.capability.models import (
        Skill,
        SkillGraph,
        CyclicDependencyError,
    )  # type: ignore[import-untyped]

    skills = [
        Skill(id=f"s{i}", name=f"Skill {i}")
        for i in range(5)
    ]
    for i in range(4):
        skills[i].prerequisite = [skills[i + 1].id]
    skills[4].prerequisite = [skills[0].id]  # 闭合环

    graph = SkillGraph(id="long_cycle", name="Long Cycle", skills=skills)

    with pytest.raises(CyclicDependencyError) as exc_info:
        graph.get_dependency_order()

    assert len(exc_info.value.remaining_nodes) == 5


# ── 23-003 — 前置 Skill 缺失 ────────────────────────────────────────────────


def test_unknown_prerequisite_raises_error() -> None:
    """引用不存在的 Skill ID 时抛出 UnknownPrerequisiteError。"""
    from ocos.capability.models import (
        Skill,
        SkillGraph,
        UnknownPrerequisiteError,
    )  # type: ignore[import-untyped]

    skill = Skill(
        id="s1",
        name="Skill 1",
        prerequisite=["non_existent"],
    )

    graph = SkillGraph(id="test", name="Test", skills=[skill])

    with pytest.raises(UnknownPrerequisiteError) as exc_info:
        graph.get_dependency_order()

    assert exc_info.value.skill_id == "s1"
    assert exc_info.value.missing_prereq == "non_existent"


# ── 23-003b — has_cycle ──────────────────────────────────────────────────────


def test_has_cycle_true(skill_infer, skill_plan) -> None:
    """has_cycle() 在循环依赖时返回 True。"""
    from ocos.capability.models import SkillGraph  # type: ignore[import-untyped]

    skill_infer.prerequisite = [skill_plan.id]
    skill_plan.prerequisite = [skill_infer.id]

    graph = SkillGraph(
        id="cycle", name="Cycle",
        skills=[skill_infer, skill_plan],
    )
    assert graph.has_cycle() is True


def test_has_cycle_false(skill_infer, skill_plan, skill_decide) -> None:
    """has_cycle() 在无环时返回 False。"""
    graph = make_linear_graph(skill_infer, skill_plan, skill_decide)
    assert graph.has_cycle() is False


# ── 23-003c — validate ──────────────────────────────────────────────────────


def test_validate_empty_graph() -> None:
    """空 SkillGraph 应报告违例。"""
    from ocos.capability.models import SkillGraph  # type: ignore[import-untyped]

    graph = SkillGraph(id="empty", name="Empty")
    violations = graph.validate()
    assert any("no skills" in v.lower() for v in violations)


def test_validate_duplicate_ids() -> None:
    """重复 Skill ID 应报告违例。"""
    from ocos.capability.models import SkillGraph, Skill  # type: ignore[import-untyped]

    skills = [
        Skill(id="dup", name="First"),
        Skill(id="dup", name="Second"),
    ]
    graph = SkillGraph(id="test", name="Test", skills=skills)
    violations = graph.validate()
    assert any("duplicate" in v.lower() for v in violations)


def test_validate_cycle(skill_infer, skill_plan) -> None:
    """循环依赖应报告违例。"""
    from ocos.capability.models import SkillGraph  # type: ignore[import-untyped]

    skill_infer.prerequisite = [skill_plan.id]
    skill_plan.prerequisite = [skill_infer.id]

    graph = SkillGraph(id="cycle", name="Cycle", skills=[skill_infer, skill_plan])
    violations = graph.validate()
    assert any("cyclic" in v.lower() for v in violations)


def test_validate_bad_entry_point() -> None:
    """entry_point 不存在时应报告违例。"""
    from ocos.capability.models import SkillGraph, Skill  # type: ignore[import-untyped]

    graph = SkillGraph(
        id="test", name="Test",
        skills=[Skill(id="s1", name="Skill 1")],
        entry_point="non_existent",
    )
    violations = graph.validate()
    assert any("entry_point" in v.lower() for v in violations)


def test_validate_valid(skill_infer, skill_plan, skill_decide) -> None:
    """正当 SkillGraph 应无违例。"""
    graph = make_linear_graph(skill_infer, skill_plan, skill_decide)
    violations = graph.validate()
    assert violations == [], f"应有零违例，实际: {violations}"


# ── 23-003d — fallback_strategy 验证 ─────────────────────────────────────────


def test_skill_fallback_strategy_valid() -> None:
    """有效的 fallback_strategy 不应报错。"""
    from ocos.capability.models import Skill  # type: ignore[import-untyped]

    # 不应抛异常
    Skill(id="s1", name="Test", fallback_strategy="abort")
    Skill(id="s2", name="Test", fallback_strategy="retry", max_retries=3)
    Skill(id="s3", name="Test", fallback_strategy="skip")
    Skill(id="s4", name="Test", fallback_strategy="fallback:backup_skill")


def test_skill_fallback_strategy_invalid() -> None:
    """无效的 fallback_strategy 应抛出 ValueError。"""
    from ocos.capability.models import Skill  # type: ignore[import-untyped]

    with pytest.raises(ValueError, match="fallback_strategy"):
        Skill(id="s1", name="Test", fallback_strategy="invalid")


# ── 23-003e — ProcessGraph 辅助方法 ──────────────────────────────────────────


def test_process_graph_add_record() -> None:
    """add_record 应更新 current_skill_index 和 last_update。"""
    from ocos.capability.models import (
        ProcessGraph,
        SkillExecutionRecord,
        SkillStatus,
    )  # type: ignore[import-untyped]

    process = ProcessGraph(
        id="p1", skill_graph_id="sg1", session_id="s1",
    )
    assert process.current_skill_index == 0

    record = SkillExecutionRecord(
        skill_id="s1", skill_name="Skill 1",
        status=SkillStatus.COMPLETED,
    )
    process.add_record(record)
    assert process.current_skill_index == 1
    assert process.last_update is not None
    assert process.last_record() is record


def test_process_graph_failed_count() -> None:
    """failed_count 应正确计数连续失败。"""
    from ocos.capability.models import (
        ProcessGraph,
        SkillExecutionRecord,
        SkillStatus,
    )  # type: ignore[import-untyped]

    process = ProcessGraph(
        id="p1", skill_graph_id="sg1", session_id="s1",
    )

    process.add_record(SkillExecutionRecord(
        skill_id="s1", skill_name="S1", status=SkillStatus.COMPLETED,
    ))
    assert process.failed_count() == 0

    process.add_record(SkillExecutionRecord(
        skill_id="s2", skill_name="S2", status=SkillStatus.FAILED,
    ))
    assert process.failed_count() == 1

    process.add_record(SkillExecutionRecord(
        skill_id="s3", skill_name="S3", status=SkillStatus.FAILED,
    ))
    assert process.failed_count() == 2

    # 成功应该打断连续计数
    process.add_record(SkillExecutionRecord(
        skill_id="s4", skill_name="S4", status=SkillStatus.COMPLETED,
    ))
    assert process.failed_count() == 0


def test_process_graph_repeated_skill_count() -> None:
    """repeated_skill_count 应正确计数。"""
    from ocos.capability.models import (
        ProcessGraph,
        SkillExecutionRecord,
        SkillStatus,
    )  # type: ignore[import-untyped]

    process = ProcessGraph(
        id="p1", skill_graph_id="sg1", session_id="s1",
    )

    for _ in range(3):
        process.add_record(SkillExecutionRecord(
            skill_id="s1", skill_name="S1", status=SkillStatus.FAILED,
        ))

    assert process.repeated_skill_count() == 3

    # 不同 Skill 应重置
    process.add_record(SkillExecutionRecord(
        skill_id="s2", skill_name="S2", status=SkillStatus.FAILED,
    ))
    assert process.repeated_skill_count() == 1
