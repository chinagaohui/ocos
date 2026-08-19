"""Phase 31: Execution Loop — 端到端执行回路测试。

合约:
  - TaskDAG 注入 AgentRuntime → 每 tick 自动取 task → echo_agent 执行
  - 3 个 task 依次执行完毕 → DAG exhausted → 回退 idle
  - 结果存入 _recent_results
"""

import pytest
from ocos.planning.decomposer import TaskDecomposer
from ocos.kernel.goal_types import UserGoal, GoalDomain
from ocos.planning.models import TaskDAG
from ocos.agent.agent_runtime import AgentRuntime


# ── Fixtures ──


def _make_dag(description: str, domain: GoalDomain) -> tuple[TaskDAG, list[str]]:
    goal = UserGoal(
        id="GOAL-test31", raw_input=description,
        objective=description, domain=domain, caller="cli",
    )
    dag = TaskDecomposer.decompose(goal)
    order = dag.topological_order()
    return dag, order


def _make_rt(dag: TaskDAG) -> AgentRuntime:
    rt = AgentRuntime.__new__(AgentRuntime)
    rt._active_dag = dag
    rt._dag_cursor = 0
    rt._dag_total = len(dag.tasks)
    rt._task_statuses = {}
    rt._recent_results = []
    return rt


# ── Core execution ──


class TestExecutionLoop:
    """Phase 31: 核心执行回路测试。"""

    def test_dag_executes_all_tasks(self):
        """all 3 tasks complete over 3 ticks."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        for _ in range(3):
            rt._tick_step_core_loop()
        assert len(rt._recent_results) == 3
        assert all(r["success"] for r in rt._recent_results)

    def test_dag_exhausted_falls_back_to_idle(self):
        """After all tasks, tick #4 returns idle."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        for _ in range(3):
            rt._tick_step_core_loop()
        r7 = rt._tick_step_core_loop()
        assert r7.get("status") == "idle"

    def test_task_output_contains_agent_prefix(self):
        """echo_agent output format: '{Agent}: {description}'."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        rt._tick_step_core_loop()
        first = rt._recent_results[0]
        assert "Researcher" in first["output"]
        assert "设计架构" in first["output"]

    def test_task_statuses_tracked(self):
        """_task_statuses records completed for each task."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        for _ in range(3):
            rt._tick_step_core_loop()
        for tid in order:
            assert rt._task_statuses.get(tid) == "completed"

    def test_progress_tracking(self):
        """progress reports advancing cursor."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        r1 = rt._tick_step_core_loop()
        r2 = rt._tick_step_core_loop()
        r3 = rt._tick_step_core_loop()
        assert r1["progress"] == "1/3"
        assert r2["progress"] == "2/3"
        assert r3["progress"] == "3/3"

    def test_dag_reset_after_exhaustion(self):
        """After exhaustion, _active_dag is None."""
        dag, order = _make_dag("设计秒杀系统", GoalDomain.DEVELOPMENT)
        rt = _make_rt(dag)
        for _ in range(3):
            rt._tick_step_core_loop()
        rt._tick_step_core_loop()  # exhausts
        rt._tick_step_core_loop()  # idle
        assert rt._active_dag is None
        assert rt._dag_cursor == 0

    def test_analysis_domain(self):
        """ANALYSIS domain tasks execute correctly."""
        dag, order = _make_dag("分析AI趋势", GoalDomain.ANALYSIS)
        rt = _make_rt(dag)
        for _ in range(3):
            rt._tick_step_core_loop()
        assert len(rt._recent_results) == 3
        assert "收集数据" in rt._recent_results[0]["output"]

    def test_writing_domain(self):
        """WRITING domain produces 5 tasks, all execute."""
        dag, order = _make_dag("写小说", GoalDomain.WRITING)
        rt = _make_rt(dag)
        for _ in range(5):
            rt._tick_step_core_loop()
        assert len(rt._recent_results) == 5
        assert all(r["success"] for r in rt._recent_results)
        # verify task order
        descriptions = [r["description"] for r in rt._recent_results]
        assert descriptions[0] == "写大纲"
        assert descriptions[-1] == "修改润色"

    def test_empty_dag_noop(self):
        """No active DAG → tick returns idle."""
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._active_dag = None
        rt._dag_cursor = 0
        rt._dag_total = 0
        rt._task_statuses = {}
        rt._recent_results = []
        r7 = rt._tick_step_core_loop()
        assert r7.get("status") == "idle"

    def test_decomposer_integration_with_tick(self):
        """Full pipeline: decompose → inject → execute."""
        goal = UserGoal(
            id="GOAL-full31", raw_input="搭建API网关",
            objective="搭建分布式API网关", domain=GoalDomain.DEVELOPMENT, caller="cli",
        )
        dag = TaskDecomposer.decompose(goal)
        rt = _make_rt(dag)
        for _ in range(len(dag.tasks)):
            rt._tick_step_core_loop()
        assert all(r["success"] for r in rt._recent_results)
        assert len(rt._recent_results) == len(dag.tasks)
