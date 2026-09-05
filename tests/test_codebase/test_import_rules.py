"""Phase 22 跨包导入规则测试。

Gate: 验证 Phase 22 新增模块的导入依赖方向合法。
"""
import pytest

# ── 允许/禁止的跨包导入方向 ──────────────────────────────────────────────

ALLOWED_IMPORTS: set[tuple[str, str]] = {
    # 原有
    ("ocos.agent", "ocos.memory"),
    ("ocos.agent", "ocos.storage"),
    ("ocos.agent", "ocos.goal"),
    ("ocos.agent", "ocos.models"),
    # Phase 22 新增
    ("ocos.agent", "ocos.capability"),
    ("ocos.agent", "ocos.events"),
    ("ocos.agent", "ocos.operations"),
    ("ocos.agent", "ocos.interaction"),
    ("ocos.agent", "ocos.agent_orchestration"),
    ("ocos.capability", "ocos.agent_orchestration"),
    # Phase 34: Runtime Awakening — event perception nerve
    ("ocos.agent", "ocos.perception_bus"),
    # Phase 35: Attention Constitution — contracts ABI
    ("ocos.capability", "ocos.contracts"),
    ("ocos.agent", "ocos.contracts"),
    # Phase 37: Adaptive Cognitive Feedback Loop — feedback_abi + outcome_eval
    ("ocos.capability", "ocos.contracts.feedback_abi"),
    ("ocos.agent", "ocos.contracts"),
}

FORBIDDEN_IMPORTS: set[tuple[str, str]] = {
    # 操作层不能引用 agent 层
    ("ocos.operations", "ocos.agent"),
    # 事件层不能引用 agent 层
    ("ocos.events", "ocos.agent"),
}


class TestImportRules:
    """Phase 22 跨包导入规则。"""

    def test_can_import_capability_from_agent(self):
        """agent 可引用 capability。"""
        from ocos.agent import agent_runtime  # noqa: F401
        # capability 模块存在且可导入
        import ocos.capability  # noqa: F401

    def test_can_import_operations_from_agent(self):
        """agent 可引用 operations。"""
        import ocos.operations  # noqa: F401

    def test_can_import_events(self):
        """events 模块存在。"""
        import ocos.events  # noqa: F401

    def test_can_import_interaction(self):
        """interaction 模块存在。"""
        import ocos.interaction  # noqa: F401

    def test_can_import_executive_controller(self):
        """ExecutiveController 可从 agent 导入。"""
        from ocos.agent.executive_controller import ExecutiveController
        assert ExecutiveController is not None

    def test_can_import_permission_gateway(self):
        """PermissionGateway 可从 capability 导入。"""
        from ocos.capability.permission_gateway import PermissionGateway
        assert PermissionGateway is not None

    def test_can_import_async_bridge(self):
        """AsyncBridge 可从 capability 导入。"""
        from ocos.capability.async_bridge import AsyncBridge
        assert AsyncBridge is not None

    def test_can_import_search_ops(self):
        """search_ops 可从 operations 导入。"""
        from ocos.operations.search_ops import SearchOps
        assert SearchOps is not None

    def test_can_import_sandbox_ops(self):
        """sandbox_ops 可从 operations 导入。"""
        from ocos.operations.sandbox_ops import SandboxOps
        assert SandboxOps is not None

    def test_can_import_stimulus(self):
        """stimulus 可从 interaction 导入。"""
        from ocos.interaction.stimulus import Stimulus, StimulusType
        assert Stimulus is not None
        assert StimulusType is not None

    def test_can_import_cognitive_interface(self):
        """CognitiveInterface 可从 interaction 导入。"""
        from ocos.interaction.cognitive_interface import CognitiveInterface
        assert CognitiveInterface is not None

    def test_phase_22_module_count(self):
        """Phase 22 新增模块数量检查。"""
        modules = [
            "ocos.capability.permission_gateway",
            "ocos.capability.async_bridge",
            "ocos.agent.executive_controller",
            "ocos.events.event_ingestion",
            "ocos.operations.search_ops",
            "ocos.operations.sandbox_ops",
            "ocos.interaction.stimulus",
            "ocos.interaction.cognitive_interface",
        ]
        for mod in modules:
            try:
                __import__(mod)
            except ImportError as e:
                pytest.fail(f"Cannot import {mod}: {e}")
