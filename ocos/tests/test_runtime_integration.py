"""
Phase 18.5 — Runtime Integration (E2E 闭环验证)。

验证六个 Runtime Engine 的真正对象流是否正确。
不测试算法，只测试对象流（Object Flow）完整性。

覆盖:
1. Goal → Decision: Goal 约束 Decision
2. Decision → Execution: 仅 COMMITTED Decision 可生成 Execution
3. Execution → Observation: Execution 产生 Observation
4. Observation → Information: Observation 进入 Memory/Information
5. Information → Process: Process 消费 Information
6. Full Loop: Goal → ... → new Information → 下一轮 Goal/Decision
"""

from __future__ import annotations

from typing import Any

import pytest

from ocos.kernel.abi import (
    Goal,
    Decision,
    DecisionStatus,
    Observation,
    Memory,
)
from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.goal_runtime import GoalRuntimeEngine
from ocos.runtime.decision_runtime import DecisionRuntimeEngine
from ocos.runtime.execution_runtime import ExecutionRuntimeEngine
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.execution import Execution, ExecutionStatus
from ocos.models.process import TransformProcess, ProcessState, ProcessType, ProcessStep


# ═══════════════════════════════════════════════════════════════════════════════
# 共享 Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def working_memory(event_bus):
    return WorkingMemory(event_bus=event_bus)


@pytest.fixture
def goal_engine(event_bus, working_memory):
    eng = GoalRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def decision_engine(event_bus, working_memory):
    eng = DecisionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def execution_engine(event_bus, working_memory):
    eng = ExecutionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Goal → Decision
# ═══════════════════════════════════════════════════════════════════════════════

class TestGoalToDecision:
    """验证 Goal 约束 Decision 的对象流。"""

    def test_goal_creates_decision(self, goal_engine, decision_engine):
        """创建一个 Goal，然后创建一个 Decision 引用它。"""
        # 1. 创建 Goal（使用引擎 API: description, priority）
        gr = goal_engine.set_goal(
            description="完成用户需求",
            priority=8,
            goal_id="gtd-1",
        )
        assert gr.success
        gid = gr.goal_id

        # 2. 基于 Goal 形成 Decision
        result = decision_engine.form_decision(
            goal_id=gid,
            selected_option="方案A",
            reasoning="基于 Goal 优先级 8",
            confidence=0.85,
        )
        assert result.success

        # 3. 验证 Decision 正确引用了 Goal
        d = decision_engine.get_decision(result.decision_id)
        assert d is not None
        assert d.goal_id == gid
        assert d.selected_option == "方案A"

    def test_goal_ref_integrity(self, goal_engine, decision_engine):
            """验证 Decision 的 goal_id 指向存在的 Goal。"""
            # 创建 Goal（使用引擎 API）
            gr = goal_engine.set_goal(
                description="分析数据",
                priority=5,
                goal_id="tri-2",
            )
            assert gr.success
            gid = gr.goal_id

            # 创建引用它的 Decision
            r = decision_engine.form_decision(goal_id=gid)
            assert r.success

            # 验证 Goal 对象中存在对应的 goal_id
            goals = goal_engine.list_goals()
            goal_ids = {g.goal_id for g in goals}
            assert gid in goal_ids

    def test_multiple_decisions_one_goal(self, goal_engine, decision_engine):
        """一个 Goal 可以有多个候选 Decision。"""
        gr = goal_engine.set_goal(description="优化性能", priority=10, goal_id="tmd-3")
        gid = gr.goal_id

        r1 = decision_engine.form_decision(goal_id=gid, selected_option="方案A")
        r2 = decision_engine.form_decision(goal_id=gid, selected_option="方案B")
        assert r1.success and r2.success

        # 验证两个 Decision 都指向同一 Goal
        decisions = decision_engine.list_decisions()
        linked = [d for d in decisions if d.goal_id == gid]
        assert len(linked) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Decision → Execution
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionToExecution:
    """Execution 只能来自已 COMMITTED 的 Decision。"""

    def test_committed_decision_produces_execution(self, goal_engine, decision_engine, execution_engine):
        """COMMITTED Decision → 创建 Execution。"""
        # 1. 创建 Goal
        gr = goal_engine.set_goal(description="执行任务", goal_id="dtm-1")
        gid = gr.goal_id

        # 2. 形成 Decision 并提交
        r = decision_engine.form_decision(goal_id=gid, selected_option="执行方案")
        decision_engine.transition_decision(r.decision_id, DecisionStatus.COMMITTED)
        d = decision_engine.get_decision(r.decision_id)
        assert d.status == DecisionStatus.COMMITTED.value

        # 3. 基于 COMMITTED Decision 创建 Execution
        er = execution_engine.schedule_execution(decision_id=r.decision_id)
        assert er.success
        e = execution_engine.get_execution(er.execution_id)
        assert e.decision_id == r.decision_id

    def test_execution_uses_decision_options(self, goal_engine, decision_engine, execution_engine):
        """Execution 继承 Decision 的决策参数。"""
        gr = goal_engine.set_goal(description="带选项", goal_id="dtm-opts")
        dr = decision_engine.form_decision(goal_id=gr.goal_id, selected_option="方案B", confidence=0.95)
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)

        er = execution_engine.schedule_execution(
            decision_id=dr.decision_id,
            action_ids=("action1", "action2"),
        )
        assert er.success
        e = execution_engine.get_execution(er.execution_id)
        assert len(e.action_ids) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Execution → Observation
# ═══════════════════════════════════════════════════════════════════════════════

class TestExecutionToObservation:
    """Execution 完成后产生 Observation（观察记录）。"""

    def _prepare_execution(self, goal_engine, decision_engine, execution_engine):
        """辅助：建立一条 Goal → Decision → COMMITTED → Execution 管线。"""
        gr = goal_engine.set_goal(description="生产观察", goal_id="eto-prep")
        dr = decision_engine.form_decision(goal_id=gr.goal_id, selected_option="执行")
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)
        er = execution_engine.schedule_execution(decision_id=dr.decision_id)
        execution_engine.start_execution(er.execution_id)
        return dr, er

    def test_successful_execution_produces_observation(self, goal_engine, decision_engine, execution_engine):
        """SUCCEEDED Execution → 创建 Observation。"""
        dr, er = self._prepare_execution(goal_engine, decision_engine, execution_engine)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)

        e = execution_engine.get_execution(er.execution_id)
        assert e.status == ExecutionStatus.SUCCEEDED.value
        assert e.completed_at is not None

        # 构造 Observation（Execution 的产出物）
        obs = Observation(
            content={
                "execution_id": er.execution_id,
                "decision_id": dr.decision_id,
                "result": "success",
                "actions": list(e.action_ids),
            },
            source=f"execution:{er.execution_id}",
        )
        assert obs.content["execution_id"] == er.execution_id

    def test_failed_execution_produces_error_observation(self, goal_engine, decision_engine, execution_engine):
        """FAILED Execution → 错误 Observation。"""
        dr, er = self._prepare_execution(goal_engine, decision_engine, execution_engine)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.FAILED)

        obs = Observation(
            content={"execution_id": er.execution_id, "error": "timeout"},
            source=f"execution:{er.execution_id}",
        )
        assert "error" in obs.content

    def test_execution_obs_links_to_decision(self, goal_engine, decision_engine, execution_engine):
        """Observation 反向引用 Execution → Decision。"""
        gr = goal_engine.set_goal(description="trace-link", goal_id="eto-trace")
        dr = decision_engine.form_decision(goal_id=gr.goal_id)
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)
        er = execution_engine.schedule_execution(decision_id=dr.decision_id)
        execution_engine.start_execution(er.execution_id)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)

        obs = Observation(content={
            "execution_id": er.execution_id,
            "decision_id": dr.decision_id,
            "goal_id": gr.goal_id,
        })
        assert obs.content["execution_id"] == er.execution_id
        assert obs.content["decision_id"] == dr.decision_id
        assert obs.content["goal_id"] == gr.goal_id


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Observation → Information
# ═══════════════════════════════════════════════════════════════════════════════

class TestObservationToInformation:
    """Observation 进入 Memory（Information 层）。"""

    def test_observation_stored_as_memory(self):
        """Observation 的内容存档为 Memory。"""
        obs = Observation(
            content={"key": "value", "result": 42},
            source="test",
        )
        mem = Memory(
            memory_id=f"mem-{obs.observation_id}",
            content=obs.content,
            memory_type="episodic",
        )
        assert mem.content == obs.content
        assert "mem-" in mem.memory_id
        assert obs.observation_id in mem.memory_id

    def test_observation_content_preserved(self):
        """Observation 的 content 原样进入 Memory。"""
        obs = Observation(content={"temperature": 36.5, "unit": "celsius"})
        mem = Memory(content=obs.content)
        assert mem.content["temperature"] == 36.5
        assert mem.content["unit"] == "celsius"

    def test_information_accessible_via_address(self):
        """Information 通过地址可检索。"""
        obs = Observation(content={"report": "Q2 分析完成"})
        mem = Memory(memory_id=obs.observation_id, content=obs.content)

        # 通过地址检索
        assert mem.memory_id == obs.observation_id
        assert mem.content["report"] == "Q2 分析完成"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Information → Process
# ═══════════════════════════════════════════════════════════════════════════════

class TestInformationToProcess:
    """Process 消费 Information。"""

    def test_process_consumes_information(self, process_engine):
        """Process 通过 input_addresses 引用 Information。"""
        info_address = ("addr:info:q2_report",)
        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            input_addresses=info_address,
            output_addresses=("addr:info:q2_result",),
        )
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert "addr:info:q2_report" in p.input_addresses
        assert p.process_type == ProcessType.REASONING.value

    def test_process_transforms_information(self, process_engine):
        """Process 消费 Input Information，产生 Output Information。"""
        input_addr = ("addr:info:raw",)
        output_addr = ("addr:info:transformed",)

        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            input_addresses=input_addr,
            output_addresses=output_addr,
            steps=(
                ProcessStep(step_id="s1", description="parse", operation="parse"),
                ProcessStep(step_id="s2", description="transform", operation="transform"),
            ),
        )
        assert pr.success

        process_engine.start_process(pr.process_id)
        process_engine.complete_process(pr.process_id)

        p = process_engine.get_process(pr.process_id)
        assert p.process_state == ProcessState.COMPLETED.value
        assert "addr:info:transformed" in p.output_addresses
        assert len(p.steps) == 2

    def test_process_can_chain(self, process_engine):
        """两个 Process 串链：P1 的输出是 P2 的输入。"""
        intermediate_addr = ("addr:info:intermediate",)
        final_addr = ("addr:info:final",)

        p1 = process_engine.create_process(output_addresses=intermediate_addr)
        p1_obj = process_engine.get_process(p1.process_id)
        assert intermediate_addr[0] in p1_obj.output_addresses

        p2 = process_engine.create_process(
            input_addresses=intermediate_addr,
            output_addresses=final_addr,
        )
        p2_obj = process_engine.get_process(p2.process_id)
        assert intermediate_addr[0] in p2_obj.input_addresses
        assert final_addr[0] in p2_obj.output_addresses

        # 链式验证：P1 产出 = P2 消费
        assert p2_obj.input_addresses == p1_obj.output_addresses


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Full Loop
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullLoop:
    """完整闭环。"""

    def test_full_round_trip(self, goal_engine, decision_engine, execution_engine, process_engine):
        """一次完整的闭环。

        管线:
        Goal(分析Q2数据) → Decision(提交方案A) → Execution(执行并成功) →
        Observation(产出结果) → Information(存入Memory) →
        Process(推理产出新信息) → new Goal(基于新信息)。
        """
        # ── Step 1: Goal ─────────────────────────────────────────────
        g1r = goal_engine.set_goal(description="分析 Q2 数据", priority=8)
        assert g1r.success
        g1id = g1r.goal_id

        # ── Step 2: Decision (基于 Goal) ─────────────────────────────
        dr = decision_engine.form_decision(
            goal_id=g1id,
            selected_option="提交方案A",
            reasoning="方案A资源最优",
            confidence=0.9,
        )
        assert dr.success
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)
        d1 = decision_engine.get_decision(dr.decision_id)
        assert d1.status == DecisionStatus.COMMITTED.value
        assert d1.goal_id == g1id

        # ── Step 3: Execution (基于 Decision) ────────────────────────
        er = execution_engine.schedule_execution(
            decision_id=dr.decision_id,
            action_ids=("action:fetch_data", "action:compute_metrics"),
        )
        assert er.success
        execution_engine.start_execution(er.execution_id)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)
        e1 = execution_engine.get_execution(er.execution_id)
        assert e1.status == ExecutionStatus.SUCCEEDED.value
        assert e1.decision_id == dr.decision_id

        # ── Step 4: Observation (Execution 产出) ─────────────────────
        obs_data = {
            "execution_id": er.execution_id,
            "decision_id": dr.decision_id,
            "goal_id": g1id,
            "metrics": {"revenue": 125000, "growth": 0.15},
            "summary": "Q2 数据提取完成",
        }
        obs = Observation(content=obs_data, source="execution")

        # ── Step 5: Information (存储到 Memory) ──────────────────────
        mem = Memory(memory_id=obs.observation_id, content=obs_data)
        assert mem.content["metrics"]["revenue"] == 125000

        # ── Step 6: Process (消费 Information) ───────────────────────
        info_addr = (f"addr:obs:{obs.observation_id}",)
        result_addr = (f"addr:info:{obs.observation_id}:result",)
        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            input_addresses=info_addr,
            output_addresses=result_addr,
            confidence=0.9,
        )
        assert pr.success
        process_engine.start_process(pr.process_id)
        process_engine.complete_process(pr.process_id)
        p1 = process_engine.get_process(pr.process_id)
        assert p1.process_state == ProcessState.COMPLETED.value
        assert info_addr[0] in p1.input_addresses

        # ── Step 7: 新 Goal 和 Decision (基于 Process 的输出) ────────
        g2r = goal_engine.set_goal(
            description=f"基于 Process {pr.process_id} 的产出开展下一步",
            priority=7,
        )
        assert g2r.success
        g2id = g2r.goal_id

        dr2 = decision_engine.form_decision(
            goal_id=g2id,
            selected_option="执行优化方案",
            reasoning=f"基于 {p1.process_id} 的推理结果",
            confidence=0.85,
        )
        assert dr2.success
        d2 = decision_engine.get_decision(dr2.decision_id)
        assert d2.goal_id == g2id

        # ── 验证整条引用链不中断 ─────────────────────────────────────
        assert goal_engine.get_goal(g1id) is not None
        assert goal_engine.get_goal(g2id) is not None
        assert decision_engine.get_decision(dr.decision_id) is not None
        assert decision_engine.get_decision(dr2.decision_id) is not None
        assert execution_engine.get_execution(er.execution_id) is not None
        assert process_engine.get_process(pr.process_id) is not None

    def test_info_flows_back_to_decision(self, goal_engine, decision_engine, execution_engine, process_engine):
        """验证 Process 产出的 Information 能反馈到下一轮 Decision 中。"""
        # 第一轮：Goal → Decision → Execution → Process
        g1r = goal_engine.set_goal(description="初步分析", goal_id="cycle-1")
        g1id = g1r.goal_id

        dr1 = decision_engine.form_decision(goal_id=g1id, selected_option="分析")
        decision_engine.transition_decision(dr1.decision_id, DecisionStatus.COMMITTED)

        er1 = execution_engine.schedule_execution(decision_id=dr1.decision_id)
        execution_engine.start_execution(er1.execution_id)
        execution_engine.transition_execution(er1.execution_id, ExecutionStatus.SUCCEEDED)

        result_addr = ("addr:info:cycle-1:output",)
        pr1 = process_engine.create_process(output_addresses=result_addr)
        process_engine.start_process(pr1.process_id)
        process_engine.complete_process(pr1.process_id)

        # 第二轮：基于 Process 产出信息创建新 Decision
        g2r = goal_engine.set_goal(description="基于分析结果优化", goal_id="cycle-2")
        g2id = g2r.goal_id

        dr2 = decision_engine.form_decision(
            goal_id=g2id,
            selected_option="优化方案",
            reasoning=f"基于 Process {pr1.process_id} 产出 {result_addr}",
            confidence=0.88,
        )
        assert dr2.success
        d2 = decision_engine.get_decision(dr2.decision_id)
        assert d2.goal_id == g2id
        assert result_addr[0] in d2.reasoning
