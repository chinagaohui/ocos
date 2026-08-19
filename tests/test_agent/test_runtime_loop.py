"""Phase 22-C: 10 步 Tick 集成测试 (22c8)。

验证:
  - tick() 返回 10 步骤日志
  - 每步都有 step/name 字段
  - Tick budget 跟踪
  - 异常恢复后仍可继续
"""
import pytest

from ocos.agent.agent_runtime import AgentRuntime, RuntimeState


# ── 核心 Tick 测试 ────────────────────────────────────────────────────────


class TestTenStepTick:
    """10 步 Tick 集成测试。"""

    @pytest.fixture
    def runtime(self):
        """创建最小 AgentRuntime 用于 tick 测试。"""
        from unittest.mock import MagicMock
        from ocos.agent.master_agent import MasterAgent

        identity = MagicMock()
        identity.verify.return_value = True
        goal_stack = MagicMock()
        goal_stack.peek.return_value = None
        intent = MagicMock()
        attention = MagicMock()
        attention.current_focus = "test_focus"
        working_memory = MagicMock()
        capability_manager = MagicMock()
        execution_manager = MagicMock()

        agent = MasterAgent(
            agent_id="test-tick",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_manager,
            execution_manager=execution_manager,
        )
        rt = AgentRuntime(agent)
        rt._state = RuntimeState.RUNNING
        return rt

    def test_tick_returns_ten_steps(self, runtime):
        """tick() 应返回 10 个 step 日志条目。"""
        result = runtime.tick()
        assert result["status"] == "completed"
        assert "steps" in result
        assert len(result["steps"]) == 10, f"Expected 10 steps, got {len(result['steps'])}"

    def test_step_fields(self, runtime):
        """每个 step 应有 step (1-10) 和 name 字段。"""
        result = runtime.tick()
        for i, step in enumerate(result["steps"], 1):
            assert step["step"] == i, f"Step {i} has step={step.get('step')}"
            assert "name" in step, f"Step {i} missing 'name'"

    def test_tick_tracks_budget(self, runtime):
        """tick() 应跟踪 budget_ok 和 tick_elapsed_s。"""
        result = runtime.tick()
        assert "budget_ok" in result
        assert "tick_elapsed_s" in result
        assert result["tick_elapsed_s"] >= 0

    def test_tick_cycle_count(self, runtime):
        """每次 tick 增加 cycle_count。"""
        c1 = runtime.tick()["cycle"]
        c2 = runtime.tick()["cycle"]
        assert c2 == c1 + 1

    def test_tick_step_names(self, runtime):
        """10 步的名称应与 spec 匹配。"""
        expected = [
            "event_ingestion",
            "attention_update",
            "wm_sync",
            "goal_maintenance",
            "execution_check",
            "planning_trigger",
            "core_loop",
            "dispatch",
            "result_ingest",
            "learning_consolidation",
        ]
        result = runtime.tick()
        names = [s["name"] for s in result["steps"]]
        assert names == expected, f"Expected {expected}, got {names}"

    def test_not_running_returns_status(self, runtime):
        """非 RUNNING 状态的 runtime 返回 not_running。"""
        runtime._state = RuntimeState.STOPPED
        result = runtime.tick()
        assert result["status"] == "not_running"

    def test_tick_budget_exceeded_detection(self, runtime):
        """预算超时检测。"""
        # 设置极低预算确保触发
        runtime._tick_budget = 0.0
        result = runtime.tick()
        assert result["budget_ok"] is False
