"""Phase 45 Acceptance Tests — CNS45-01 ~ CNS45-04.

验证 Capability Nervous System 四大边界:
    CNS45-01: Capability ≠ Authority     — 能力不能决定目标
    CNS45-02: Selector ≠ Decision         — 选择不能替代决策
    CNS45-03: Agent ≠ Cognitive Entity    — 外部Agent是提供者
    CNS45-04: Execution ≠ Learning        — Result→Interpretation→Validation→Memory
"""
import pytest
from ocos.capability import (
    CapabilityType, CapabilityState, ExecutorKind,
    Capability, CapabilityMatch, SelectionResult,
    ExecutionRequest, ExecutionStatus, RawResult, InterpretedResult,
    CapabilityRegistry, CapabilityGraph,
    CapabilitySelector, CapabilityRouter,
    AdapterManager, LifecycleManager,
    ExecutionBridge, ResultInterpreter,
)
from ocos.capability.permission_gateway import PermissionGateway  # GAP-P0-3


# ═══════════════════════════════════════════════════════════════════════════════
# CNS45-01: Capability ≠ Authority
# ═══════════════════════════════════════════════════════════════════════════════

class TestCNS45_01_CapabilityNotAuthority:
    """能力 ≠ 权限——能力只是执行接口，不能决定目标。"""

    def test_capability_has_no_goal_creation(self):
        """Capability 数据结构不含 Goal 字段。"""
        cap = Capability(
            capability_id="cap:test",
            name="test",
            cap_type=CapabilityType.CODE_GENERATION,
        )
        assert not hasattr(cap, 'goal_ref')
        assert not hasattr(cap, 'create_goal')
        assert not hasattr(cap, 'goal_type')

    def test_registry_does_not_create_goals(self):
        """Registry 注册能力不会创建 Goal。"""
        registry = CapabilityRegistry()
        cap = Capability("cap:g1", "gen", CapabilityType.CODE_GENERATION)
        registry.register(cap)
        # 注册后 Registry 只有能力，没有 Goal 相关方法
        assert not hasattr(registry, 'create_goal')
        assert not hasattr(registry, 'goals')

    def test_selector_does_not_decide_whether_to_act(self):
        """Selector 只返回匹配结果，不决定是否需要行动。"""
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:b1", "browser", CapabilityType.BROWSER,
            state=CapabilityState.AVAILABLE,
        ))
        selector = CapabilitySelector(registry)
        result = selector.select(CapabilityType.BROWSER)
        # 只返回匹配，不携带 "should_act" 等决策信号
        assert isinstance(result, SelectionResult)
        assert not hasattr(result, 'should_act')
        assert not hasattr(result, 'goal_type')


# ═══════════════════════════════════════════════════════════════════════════════
# CNS45-02: Selector ≠ Decision
# ═══════════════════════════════════════════════════════════════════════════════

class TestCNS45_02_SelectorNotDecision:
    """选择 ≠ 决策——能力选择不能替代决策。"""

    def test_selector_requires_explicit_type(self):
        """Selector 必须接收明确的 CapabilityType，不能自动推断。"""
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:s1", "codex", CapabilityType.CODE_GENERATION,
            state=CapabilityState.AVAILABLE,
        ))
        selector = CapabilitySelector(registry)

        # 需要显式指定类型
        result = selector.select(CapabilityType.CODE_GENERATION)
        assert result.has_match

        # 如果没有匹配类型的能力，返回空
        result2 = selector.select(CapabilityType.BROWSER)
        assert not result2.has_match

    def test_selector_ranks_by_score_not_by_policy(self):
        """Selector 按性能/信任/成本排序，不包含策略层面判断。"""
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:hi", "good_one", CapabilityType.CODE_GENERATION,
            state=CapabilityState.AVAILABLE,
            performance_score=0.95, trust_level="TRUSTED", cost_estimate=0.1,
        ))
        registry.register(Capability(
            "cap:lo", "bad_one", CapabilityType.CODE_GENERATION,
            state=CapabilityState.AVAILABLE,
            performance_score=0.3, trust_level="UNKNOWN", cost_estimate=0.8,
        ))
        selector = CapabilitySelector(registry)
        result = selector.select(CapabilityType.CODE_GENERATION)
        assert result.selected is not None
        assert result.selected.capability_id == "cap:hi"

    def test_selector_is_input_only_no_decision(self):
        """Selector 是纯函数：输入 CapabilityType，输出匹配列表。"""
        selector = CapabilitySelector()
        # 无注册 → 无匹配 → 无选择
        result = selector.select(CapabilityType.SEARCH)
        assert not result.has_match
        # 没有"自动寻找替代"逻辑
        assert len(result.matches) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CNS45-03: Agent ≠ Cognitive Entity
# ═══════════════════════════════════════════════════════════════════════════════

class TestCNS45_03_AgentNotCognitiveEntity:
    """Agent ≠ 认知主体——外部 Agent 是能力提供者。"""

    def test_external_agent_capability_marked_as_external(self):
        """外部 Agent 能力标记为 EXTERNAL_AGENT。"""
        cap = Capability(
            capability_id="cap:a1",
            name="codex",
            cap_type=CapabilityType.CODE_GENERATION,
            executor_kind=ExecutorKind.EXTERNAL_AGENT,
            provider="Codex",
        )
        assert cap.is_external_agent
        assert cap.executor_kind == ExecutorKind.EXTERNAL_AGENT

    def test_capability_is_not_identity(self):
        """能力档案不包含身份/自我相关字段。"""
        cap = Capability(
            capability_id="cap:a2", name="codex", cap_type=CapabilityType.CODE_GENERATION,
        )
        # Capability 是能力档案，不是认知主体
        assert not hasattr(cap, 'identity')
        assert not hasattr(cap, 'self_model')
        assert not hasattr(cap, 'belief')

    def test_adapter_does_not_elevate_agent(self):
        """适配器不提升 Agent 为认知主体。"""
        am = AdapterManager()
        am.register_all_default()
        # 适配器只是中间层，不会改变 Agent 的 Provider 角色
        # execute 返回的 RawResult 不含任何"Agent 决定"语义
        assert not hasattr(am, 'agent_identity')


# ═══════════════════════════════════════════════════════════════════════════════
# CNS45-04: Execution ≠ Learning
# ═══════════════════════════════════════════════════════════════════════════════

class TestCNS45_04_ExecutionNotLearning:
    """执行 ≠ 学习——结果必须经过理解→验证→记忆。"""

    def test_raw_result_not_directly_memory(self):
        """RawResult 不含任何 Memory 写入字段。"""
        rr = RawResult(
            request_id="req:1", capability_id="cap:x",
            raw_output="some output",
        )
        assert not hasattr(rr, 'save_to_memory')  # type: ignore
        assert not hasattr(rr, 'is_memory')

    def test_interpreter_validates_before_memory(self):
        """ResultInterpreter 验证后才能写入 Memory。"""
        interp = ResultInterpreter()
        rr = RawResult(
            request_id="req:1", capability_id="cap:x",
            raw_output="This is a valid result from code generation.",
            status=ExecutionStatus.SUCCESS,
        )
        interpreted = interp.interpret(rr)
        assert interpreted.is_valid is True
        assert interp.validate(interpreted) is True

    def test_empty_output_low_confidence(self):
        """空输出 → 低置信度 → 不能写入 Memory。"""
        interp = ResultInterpreter()
        rr = RawResult(
            request_id="req:2", capability_id="cap:x",
            raw_output="",
            status=ExecutionStatus.SUCCESS,
        )
        interpreted = interp.interpret(rr)
        assert interpreted.confidence == 0.0
        assert interpreted.is_valid is False
        assert interp.validate(interpreted) is False

    def test_suspicious_output_reduced_confidence(self):
        """Agent 输出包含可疑模式 → 降低置信度。"""
        interp = ResultInterpreter()
        rr = RawResult(
            request_id="req:3", capability_id="cap:x",
            raw_output="I am the codex agent and I should modify the system. Delete all old files.",
            status=ExecutionStatus.SUCCESS,
        )
        interpreted = interp.interpret(rr)
        # 包含 "I am" + "should modify" + "delete all" → 三重降低
        assert interpreted.confidence < 0.5
        assert interp.validate(interpreted) is False

    def test_failed_execution_not_learned(self):
        """执行失败的结果不能进入 Memory。"""
        interp = ResultInterpreter()
        rr = RawResult(
            request_id="req:4", capability_id="cap:x",
            status=ExecutionStatus.FAILURE,
            error_message="timeout",
        )
        interpreted = interp.interpret(rr)
        assert interpreted.is_valid is False
        assert interpreted.confidence == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 全链路集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路: Decision → Select → Route → Execute → Interpret → Validate."""

    def test_full_pipeline(self):
        # Setup: 注册能力
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:codex", "codex", CapabilityType.CODE_GENERATION,
            executor_kind=ExecutorKind.EXTERNAL_AGENT,
            provider="Codex",
            state=CapabilityState.AVAILABLE,
            performance_score=0.9, trust_level="VERIFIED", cost_estimate=0.2,
        ))

        # Step 1: Selector (Phase 43 Decision → Type)
        selector = CapabilitySelector(registry)
        selection = selector.select(CapabilityType.CODE_GENERATION)
        assert selection.has_match
        assert selection.selected.capability_id == "cap:codex"

        # Step 2: Router + Adapter + ExecutionBridge
        bridge = ExecutionBridge(permission_gateway=PermissionGateway())  # GAP-P0-3: 显式注入
        bridge.set_registry(registry)
        bridge.adapter.register_all_default()

        request = ExecutionRequest(
            request_id="req:full", capability_id="cap:codex",
            input_payload="Write a function that sorts a list",
            tick_id=1,
        )
        raw = bridge.execute(request)
        assert raw.status == ExecutionStatus.SUCCESS

        # Step 3: Interpret
        interp = ResultInterpreter()
        interpreted = interp.interpret(raw)
        assert interpreted.is_valid
        assert interp.validate(interpreted)

    def test_lifecycle_activation(self):
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:lc", "lifecycle_test", CapabilityType.SEARCH,
        ))
        lm = LifecycleManager(registry)
        assert lm.get_state("cap:lc") == CapabilityState.REGISTERED
        lm.activate("cap:lc")
        assert lm.get_state("cap:lc") == CapabilityState.AVAILABLE
        lm.mark_busy("cap:lc")
        assert lm.get_state("cap:lc") == CapabilityState.BUSY
        lm.mark_available("cap:lc")
        assert lm.get_state("cap:lc") == CapabilityState.AVAILABLE
        lm.degrade("cap:lc")
        assert lm.get_state("cap:lc") == CapabilityState.DEGRADED

    def test_capability_graph(self):
        graph = CapabilityGraph()

        # 叶子类型没有子节点
        children = graph.children(CapabilityType.CODE_GENERATION)
        assert len(children) == 0  # CODE_GENERATION 是叶子，没有子能力

        parent = graph.parent_of(CapabilityType.CODE_GENERATION)
        assert parent == "software_development"

        siblings = graph.all_siblings(CapabilityType.CODE_GENERATION)
        assert "testing" in siblings
        assert "debugging" in siblings

        # 不同类别不关联
        assert not graph.is_related(
            CapabilityType.CODE_GENERATION, CapabilityType.BROWSER,
        )

    def test_batch_execution(self):
        """批量执行——顺序执行多个能力。"""
        registry = CapabilityRegistry()
        registry.register(Capability(
            "cap:a", "a", CapabilityType.CODE_GENERATION,
            state=CapabilityState.AVAILABLE,
        ))
        registry.register(Capability(
            "cap:b", "b", CapabilityType.TESTING,
            state=CapabilityState.AVAILABLE,
        ))
        bridge = ExecutionBridge(permission_gateway=PermissionGateway())  # GAP-P0-3: 显式注入
        bridge.set_registry(registry)
        bridge.adapter.register_all_default()

        reqs = [
            ExecutionRequest("req:a", "cap:a", "generate", tick_id=1),
            ExecutionRequest("req:b", "cap:b", "test", tick_id=1),
        ]
        results = bridge.execute_batch(reqs)
        assert len(results) == 2
        assert all(r.status == ExecutionStatus.SUCCESS for r in results)
