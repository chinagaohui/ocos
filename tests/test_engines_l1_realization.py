"""L1 引擎真实化测试 — 九引擎 LLM/历史数据/真实计算落地验证。

覆盖:
- ReasoningEngine: episode 证据 + LLM 推理 / 确定性降级
- PlanningEngine: LLM 步骤分解 / 模板降级
- DecisionMakingEngine: PARETO 非支配排序 / MAJORITY 评审投票 / OPPORTUNITY_COST 历史成功率
- SimulationEngine: 蒙特卡洛真参数扰动 + 终态聚合
- ReflectionEngine: lesson 管道 + 失败归因
- PredictionEngine: 历史统计外推/回归/分类/集成
- LearningEngine: 快路径学习下沉（Episode 重放）
- PolicyEngine / GoalArbitrationEngine: 自主级别闸门挂接
"""
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.process import TransformProcess, ProcessType


@pytest.fixture(autouse=True)
def _clean_strategy_registry():
    """隔离全局决策策略注册表 — 其他套件（ocos/tests）注册的
    自定义 handler 会短路 L1 的 _real/_fallback 路径（合跑污染）。"""
    from ocos.engines import decision_making_engine as dme
    saved = dict(dme._STRATEGY_HANDLERS)
    dme._STRATEGY_HANDLERS.clear()
    yield
    dme._STRATEGY_HANDLERS.clear()
    dme._STRATEGY_HANDLERS.update(saved)


# ── 测试工具 ──────────────────────────────────────────────────────────────────


class ScriptedProvider:
    """固定响应的假 LLM provider（available=True）。"""

    available = True
    name = "scripted"

    def __init__(self, response: str):
        self._response = response
        self.last_prompt = ""

    async def generate(self, prompt: str, **kwargs) -> str:
        self.last_prompt = prompt
        return self._response


class ScriptedTextGenerator:
    def __init__(self, response: str):
        self.provider = ScriptedProvider(response)


class DeadProvider:
    available = False
    name = "dead"


class DeadTextGenerator:
    def __init__(self):
        self.provider = DeadProvider()


class FakeEp:
    """轻量 Episode 替身（outcome.success 可判）。"""

    def __init__(self, goal="", decision="", action="", success=None,
                 source="goal", context=None, tags=(), error="",
                 ep_id="", created_at=None, status_name="ACTIVE"):
        self.id = ep_id or f"EPI-{goal[:6]}-{id(self)}"
        self.goal = goal
        self.decision = decision
        self.action = action
        self.outcome = (
            {"success": success, **({"error": error} if error else {})}
            if success is not None else {}
        )
        self.source = source
        self.context = context or {}
        self.tags = list(tags)
        self.condition = ""
        self.created_at = created_at or datetime.now(timezone.utc)


def _make_store(episodes):
    """基于内存列表的假 EpisodeStore（query_by_time 新→旧，query_by_source）。"""

    class FakeStore:
        def query_by_time(self, limit=50, active_only=True):
            return list(reversed(episodes))[-limit:]

        def query_by_source(self, source, limit=10):
            return [ep for ep in reversed(episodes) if ep.source == source][:limit]

    return FakeStore()


# ── ReasoningEngine ──────────────────────────────────────────────────────────


class TestReasoningEngineL1:
    def _make(self, tg=None, store=None):
        from ocos.engines.reasoning_engine import ReasoningEngine
        return ReasoningEngine(EventBus(), WorkingMemory(),
                               memory_store=store, text_generator=tg)

    def test_real_reason_uses_llm_and_evidence(self):
        episodes = [
            FakeEp(goal="部署 api 服务", decision="用 systemd 拉起", success=True,
                   ep_id="EPI-DEPLOY-1"),
        ]
        engine = self._make(ScriptedTextGenerator(
            "结论：应使用 systemd [EPI-DEPLOY-1]"), _make_store(episodes))
        result = engine.execute(
            TransformProcess(process_type=ProcessType.REASONING),
            operation="analysis",
            premises={"inputs": ["部署 api 服务"]},
        )
        assert result.success
        trace = engine.get_trace(result.trace_id)
        assert trace is not None and trace.steps
        step = trace.steps[0]
        assert "systemd" in step.conclusion
        assert step.metadata["degraded"] is False
        assert "EPI-DEPLOY-1" in step.metadata["evidence"]

    def test_degraded_reason_honest(self):
        engine = self._make(DeadTextGenerator())
        result = engine.execute(
            TransformProcess(process_type=ProcessType.REASONING),
            operation="analysis",
            premises={"inputs": ["任意前提"]},
        )
        assert result.success  # 降级不失败，但诚实标注
        trace = engine.get_trace(result.trace_id)
        step = trace.steps[0]
        assert step.metadata["degraded"] is True
        assert "[degraded:analysis]" in step.conclusion


# ── PlanningEngine ───────────────────────────────────────────────────────────


class TestPlanningEngineL1:
    def _make(self, tg=None):
        from ocos.engines.planning_engine import PlanningEngine
        return PlanningEngine(EventBus(), WorkingMemory(), text_generator=tg)

    def test_real_plan_parses_steps(self):
        engine = self._make(ScriptedTextGenerator(
            "STEP|安装依赖|20\nSTEP|编写配置|30\nSTEP|启动服务|10"))
        result = engine.execute(
            TransformProcess(process_type=ProcessType.PLANNING),
            inputs={"goal": "部署服务"},
        )
        assert result.success
        trace = engine.get_trace(result.trace_id)
        assert not trace.error
        steps = trace.steps
        assert len(steps) == 3
        assert steps[0].description == "安装依赖"
        assert steps[0].estimated_effort == 20
        assert steps[0].depends_on == (), "首步无依赖"
        assert steps[0].step_id in steps[1].depends_on, "后续步骤应依赖前序"
        assert trace.total_effort == 60

    def test_real_plan_validates_output(self):
        engine = self._make(ScriptedTextGenerator("我不太确定该怎么规划。"))
        result = engine.execute(
            TransformProcess(process_type=ProcessType.PLANNING),
            inputs={"goal": "模糊目标"},
        )
        # LLM 无有效步骤 → 降级到模板，诚实标注
        trace = engine.get_trace(result.trace_id)
        assert "degraded" in trace.error
        assert trace.steps

    def test_degraded_plan_template(self):
        engine = self._make(DeadTextGenerator())
        result = engine.execute(
            TransformProcess(process_type=ProcessType.PLANNING),
            inputs={"goal": "部署服务"},
        )
        trace = engine.get_trace(result.trace_id)
        assert "degraded" in trace.error
        assert trace.steps[0].description.startswith("[degraded:")


# ── DecisionMakingEngine ─────────────────────────────────────────────────────


class TestDecisionMakingEngineL1:
    OPTIONS = [
        {"label": "A", "scores": {"quality": 9, "cost": 2, "risk": 2}},
        {"label": "B", "scores": {"quality": 5, "cost": 8, "risk": 8}},
        {"label": "C", "scores": {"quality": 6, "cost": 9, "risk": 1}},
    ]

    def _make(self, tg=None, store=None):
        from ocos.engines.decision_making_engine import DecisionMakingEngine
        return DecisionMakingEngine(EventBus(), WorkingMemory(),
                                    memory_store=store, text_generator=tg)

    def test_pareto_non_dominated_sorting(self):
        engine = self._make()
        result = engine.execute(
            TransformProcess(process_type=ProcessType.DECISION),
            strategy="pareto", options_data=self.OPTIONS,
        )
        trace = engine.get_trace(result.trace_id)
        # A 支配 B → 前沿 {A, C}；效用 A=7.4 > C=1.2 → A
        assert "['A', 'C']" in trace.rationale
        assert "'A'" in trace.rationale
        assert not trace.error

    def test_majority_degraded_dimension_voting(self):
        engine = self._make(DeadTextGenerator())
        result = engine.execute(
            TransformProcess(process_type=ProcessType.DECISION),
            strategy="majority", options_data=self.OPTIONS,
        )
        trace = engine.get_trace(result.trace_id)
        assert "[degraded:majority]" in trace.rationale
        assert "degraded" in trace.error
        # quality+cost 两票归 A
        assert trace.rationale.endswith("'A'")

    def test_majority_real_llm_votes(self):
        engine = self._make(ScriptedTextGenerator("VOTE|C\nVOTE|C\nVOTE|A"))
        result = engine.execute(
            TransformProcess(process_type=ProcessType.DECISION),
            strategy="majority", options_data=self.OPTIONS,
        )
        trace = engine.get_trace(result.trace_id)
        assert trace.rationale.startswith("majority: 评审投票")
        assert not trace.error
        assert "C" in trace.rationale  # C 得 2 票当选

    def test_opportunity_cost_degraded(self):
        engine = self._make()
        result = engine.execute(
            TransformProcess(process_type=ProcessType.DECISION),
            strategy="opportunity_cost", options_data=self.OPTIONS,
        )
        trace = engine.get_trace(result.trace_id)
        assert "[degraded:opportunity_cost]" in trace.rationale

    def test_opportunity_cost_real_history(self):
        episodes = [
            FakeEp(goal="选项C 类任务", success=True, ep_id="E1"),
            FakeEp(goal="选项C 类任务", success=True, ep_id="E2"),
            FakeEp(goal="选项C 类任务", success=False, ep_id="E3"),
            FakeEp(goal="选项A 类任务", success=False, ep_id="E4"),
            FakeEp(goal="选项A 类任务", success=False, ep_id="E5"),
            FakeEp(goal="选项A 类任务", success=False, ep_id="E6"),
        ]
        engine = self._make(store=_make_store(episodes))
        result = engine.execute(
            TransformProcess(process_type=ProcessType.DECISION),
            strategy="opportunity_cost", options_data=self.OPTIONS,
        )
        trace = engine.get_trace(result.trace_id)
        assert trace.rationale.startswith("opportunity_cost: 选用 'C'")
        assert "成功率" in trace.rationale
        assert not trace.error


# ── SimulationEngine ─────────────────────────────────────────────────────────


class TestSimulationEngineL1:
    def _make(self):
        from ocos.engines.simulation_engine import SimulationEngine
        return SimulationEngine(EventBus(), WorkingMemory())

    def test_monte_carlo_real_perturbation(self):
        engine = self._make()
        from ocos.models.simulation import SimulationScenario
        scenario = SimulationScenario(
            initial_state={"x": 0.0}, parameters={"growth": 2.0, "mode": "fast"},
            steps=3)
        traces = engine.run_monte_carlo(
            scenario, lambda state, params, i: {"x": state.get("x", 0) + params["growth"]},
            num_runs=5, seed=42)
        growth = [t.parameters["growth"] for t in traces]
        assert len(set(growth)) == 5, "每轮参数应被真实扰动"
        assert all(abs(g - 2.0) <= 0.2 for g in growth), "扰动幅度 ±10%"
        assert all(t.parameters["mode"] == "fast" for t in traces), "非数值参数不扰动"
        finals = [t.final_state["x"] for t in traces]
        assert len(set(finals)) == 5, "终态随扰动联动"

    def test_monte_carlo_reproducible_with_seed(self):
        engine = self._make()
        from ocos.models.simulation import SimulationScenario
        scenario = SimulationScenario(
            initial_state={"x": 0.0}, parameters={"growth": 2.0}, steps=2)
        kw = dict(num_runs=3, seed=7,
                  step_fn=lambda s, p, i: {"x": s.get("x", 0) + p["growth"]})
        g1 = [t.parameters["growth"] for t in engine.run_monte_carlo(scenario, **kw)]
        g2 = [t.parameters["growth"] for t in engine.run_monte_carlo(scenario, **kw)]
        assert g1 == g2

    def test_aggregate_final_states(self):
        engine = self._make()
        from ocos.models.simulation import SimulationScenario
        scenario = SimulationScenario(
            initial_state={"x": 0.0}, parameters={"growth": 2.0}, steps=2)
        traces = engine.run_monte_carlo(
            scenario, lambda s, p, i: {"x": s.get("x", 0) + p["growth"]},
            num_runs=4, seed=1)
        stats = engine.aggregate_final_states(traces)
        assert "x" in stats
        assert stats["x"]["min"] <= stats["x"]["mean"] <= stats["x"]["max"]


# ── ReflectionEngine ─────────────────────────────────────────────────────────


class TestReflectionEngineL1:
    def _make(self, store=None):
        from ocos.engines.reflection_engine import ReflectionEngine
        return ReflectionEngine(EventBus(), WorkingMemory(), memory_store=store)

    def test_lesson_pipeline_insights(self):
        from ocos.models.reflection import ReflectionStrategy
        episodes = [
            FakeEp(decision="批量任务应并行执行", action="并行分派", source="lesson",
                   context={"lesson_type": "效率"}, tags=["synthesized", "效率"],
                   ep_id="LES-1"),
            FakeEp(goal="备份文件", decision="cp", action="cp", success=False,
                   error="timeout: cp timed out after 300s", ep_id="EPI-F1"),
            FakeEp(goal="抓包", decision="tcpdump", action="tcpdump", success=False,
                   error="timeout: command timed out", ep_id="EPI-F2"),
            FakeEp(goal="列目录", decision="ls", action="ls", success=True,
                   ep_id="EPI-S1"),
        ]
        engine = self._make(_make_store(episodes))
        trace = engine.reflect("goal", "GOAL-1", None, ReflectionStrategy.CAUSAL)
        descriptions = [i.description for i in trace.insights]
        assert any("批量任务应并行执行" in d for d in descriptions), "lesson 应进入洞见"
        assert any("timeout" in d and "出现 2 次" in d for d in descriptions), "失败归因应进入洞见"
        assert any("因果主导" in d for d in descriptions), "CAUSAL 策略洞见"

    def test_no_memory_store_raises_honest(self):
        engine = self._make()
        with pytest.raises(ValueError, match="memory_store"):
            engine.reflect("goal", "X", None)

    def test_degraded_insight_on_store_failure(self):
        class BrokenStore:
            def query_by_source(self, *a, **kw):
                raise RuntimeError("db locked")

            def query_by_time(self, *a, **kw):
                raise RuntimeError("db locked")

        engine = self._make(BrokenStore())
        trace = engine.reflect("goal", "X", None)
        assert any("[degraded:reflection]" in i.description for i in trace.insights)


# ── PredictionEngine ─────────────────────────────────────────────────────────


class TestPredictionEngineL1:
    def _make(self, store=None):
        from ocos.engines.prediction_engine import PredictionEngine
        return PredictionEngine(EventBus(), WorkingMemory(), memory_store=store)

    def test_extrapolation_least_squares(self):
        from ocos.models.prediction import PredictionStrategy
        engine = self._make()
        trace = engine.predict({"series": [1, 2, 3, 4, 5], "horizon": 2},
                               None, PredictionStrategy.EXTRAPOLATION)
        p1, p2 = trace.predictions
        assert abs(p1.value - 6.0) < 1e-6 and abs(p2.value - 7.0) < 1e-6
        assert p1.interval is not None and p1.confidence >= 0.5

    def test_regression_fit(self):
        from ocos.models.prediction import PredictionStrategy
        engine = self._make()
        trace = engine.predict({"series": [1, 2, 3, 4, 5]}, None,
                               PredictionStrategy.REGRESSION)
        v = trace.predictions[0].value
        assert abs(v["slope"] - 1.0) < 1e-6 and v["r2"] > 0.99

    def test_classification_task_matched_history(self):
        from ocos.models.prediction import PredictionStrategy
        episodes = [
            FakeEp(goal="备份 big file", success=True, ep_id="E1"),
            FakeEp(goal="备份 big file", success=True, ep_id="E2"),
            FakeEp(goal="备份 big file", success=False, ep_id="E3"),
            FakeEp(goal="抓包", success=True, ep_id="E4"),
        ]
        engine = self._make(_make_store(episodes))
        trace = engine.predict({"task": "备份 big file"}, None,
                               PredictionStrategy.CLASSIFICATION)
        p = trace.predictions[0]
        assert abs(p.value["success_probability"] - 2 / 3) < 1e-3
        assert p.label == "success"
        assert p.metadata["method"] == "task_matched_history"

    def test_episode_derived_series_clamped(self):
        from ocos.models.prediction import PredictionStrategy
        episodes = []
        for d in range(5):
            for k in range(5):
                episodes.append(FakeEp(
                    goal=f"任务{d}-{k}",
                    created_at=datetime.now(timezone.utc) - timedelta(days=4 - d),
                    success=(k < d + 1)))
        engine = self._make(_make_store(episodes))
        trace = engine.predict({"horizon": 1}, None, PredictionStrategy.EXTRAPOLATION)
        p = trace.predictions[0]
        assert 0.0 <= p.value <= 1.0, "成功率外推应截断至 [0,1]"
        assert 0.0 <= p.interval.lower and p.interval.upper <= 1.0

    def test_ensemble_combines_views(self):
        from ocos.models.prediction import PredictionStrategy
        episodes = [FakeEp(goal=f"任务{i}", success=(i % 2 == 0)) for i in range(6)]
        engine = self._make(_make_store(episodes))
        trace = engine.predict({"series": [1, 2, 3, 4, 5], "task": "任务"},
                               None, PredictionStrategy.ENSEMBLE)
        assert len(trace.predictions) >= 2

    def test_degraded_honest(self):
        from ocos.models.prediction import PredictionStrategy
        engine = self._make()
        trace = engine.predict({"series": [1]}, None, PredictionStrategy.EXTRAPOLATION)
        p = trace.predictions[0]
        assert p.label == "degraded" and p.confidence == 0.0
        assert "degraded" in str(p.value)

    def test_no_source_raises_honest(self):
        engine = self._make()
        with pytest.raises(ValueError, match="memory_store"):
            engine.predict({}, None)


# ── LearningEngine ───────────────────────────────────────────────────────────


class TestLearningEngineL1:
    def _make(self, store=None):
        from ocos.engines.learning_engine import LearningEngine
        return LearningEngine(EventBus(), WorkingMemory(), memory_store=store)

    def test_fast_path_learning_from_episodes(self):
        episodes = [
            FakeEp(goal=f"部署服务{i}", decision=f"shell 部署 {i}",
                   action=f"systemctl start svc{i}", success=(i % 2 == 0),
                   error="" if i % 2 == 0 else "timeout: svc start timeout")
            for i in range(6)
        ]
        engine = self._make(_make_store(episodes))
        stats = engine.learn_from_episodes(today_only=False)
        assert stats["learning_engine"] is True
        assert stats["replayed"] == 6
        assert stats["examples"] > 0
        assert stats.get("trace_id")
        model = engine.get_model(stats["model_id"])
        assert model is not None

    def test_execute_fast_path(self):
        episodes = [
            FakeEp(goal=f"任务{i}", decision=f"do {i}", action=f"act {i}",
                   success=(i % 2 == 0)) for i in range(6)
        ]
        engine = self._make(_make_store(episodes))
        result = engine.execute(TransformProcess(process_type=ProcessType.LEARNING),
                                context={"today_only": False})
        assert result.success
        assert "Fast-path" in result.message

    def test_execute_honest_failure_without_store(self):
        engine = self._make()
        result = engine.execute(TransformProcess(process_type=ProcessType.LEARNING))
        assert not result.success
        assert "no memory_store" in result.message

    def test_learn_default_rule_learner(self):
        from ocos.models.learning import LearningExample
        engine = self._make()
        examples = [LearningExample(
            input_data={"task": "x"}, output_data={"action": "y"},
            reward=1.0, feedback="ok", metadata={})]
        model, trace = engine.learn(examples)
        assert model is not None and trace.trace_id


# ── 自主级别闸门挂接 ─────────────────────────────────────────────────────────


class TestAutonomyGateWiring:
    def test_policy_engine_gate(self):
        from ocos.engines.policy_engine import PolicyEngine
        engine = PolicyEngine(EventBus(), WorkingMemory())
        base_ctx = {"quality": 5, "cost": 3, "risk": 2}

        r0 = engine.execute(TransformProcess(process_type=ProcessType.POLICY),
                            target="t", context={**base_ctx, "autonomy_level": 0})
        assert not r0.all_passed
        trace = engine.get_trace(r0.trace_id)
        gate = [e for e in trace.evaluations if e.rule_id == "autonomy_gate"][0]
        assert not gate.passed and "LEVEL=0" in gate.detail

        r1 = engine.execute(TransformProcess(process_type=ProcessType.POLICY),
                            target="t", context={**base_ctx, "autonomy_level": 1})
        assert r1.all_passed

        # 业务规则在高级别下仍生效
        r2 = engine.execute(TransformProcess(process_type=ProcessType.POLICY),
                            target="t",
                            context={"autonomy_level": 2, "quality": 2,
                                     "cost": 3, "risk": 2})
        assert not r2.all_passed

    def test_goal_arbitration_gate(self):
        from ocos.engines.goal_arbitration_engine import GoalArbitrationEngine
        from ocos.models.goal_arbitration import (
            ArbitrationStrategy, GoalCandidate)
        engine = GoalArbitrationEngine(EventBus(), WorkingMemory())
        cands = [
            GoalCandidate(goal_id="G1", label="A", priority=1, weight=1.0,
                          urgency=0.5, resource_cost=1.0),
            GoalCandidate(goal_id="G2", label="B", priority=2, weight=0.5,
                          urgency=0.3, resource_cost=1.0),
        ]

        best0, tr0 = engine.arbitrate(cands, ArbitrationStrategy.PRIORITY,
                                      {"autonomy_level": 0})
        assert tr0.selected_ids == ()
        assert best0.selected is False
        assert "[autonomy:L0]" in best0.reason

        best1, tr1 = engine.arbitrate(cands, ArbitrationStrategy.PRIORITY,
                                      {"autonomy_level": 1})
        assert tr1.selected_ids == ("G1",)
        assert "需审批" in best1.reason

        best2, tr2 = engine.arbitrate(cands, ArbitrationStrategy.PRIORITY,
                                      {"autonomy_level": 2})
        assert tr2.selected_ids == ("G1",)
        assert "需审批" not in best2.reason
