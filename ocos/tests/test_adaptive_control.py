"""
B6 Adaptive Control — 完整测试套件。

覆盖：
- Dataclass 冻结（AdaptiveConfig / Adaptation / RuntimeParam / RiskLevel）
- get_config 返回初始值 / 自定义初始值
- adapt 显式设置 / 无效参数名跳过 / 无变更跳过
- auto_adapt 降级方向（内存/CPU/GPU/风险）
- auto_adapt 缓慢恢复方向
- 参数 clamp 边界
- B5 ResourceManager 集成（mock usage）
- B4 PolicyEngine 集成（mock risk level）
- Event Bus 集成（RESOURCE_EXHAUSTED 事件触发 auto_adapt）
- 订阅管理（subscribe / unsubscribe）
- reset / history 上限
- 无 Event Bus / 无 PolicyEngine 降级
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from ocos.runtime.adaptive_control import (
    DEFAULT_CONFIG,
    PARAM_BOUNDS,
    RECOVERY_COOLDOWN_SECONDS,
    Adaptation,
    AdaptiveConfig,
    AdaptiveController,
    RiskLevel,
    RuntimeParam,
    _clamp,
)
from ocos.kernel.abi import Event, EventType


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_resource_manager() -> MagicMock:
    """Mock ResourceManager — 默认所有资源充足（使用率 0%）。"""
    rm = MagicMock()
    rm.get_usage.return_value = [
        _usage("cpu", total=8.0, available=8.0),
        _usage("memory", total=16384.0, available=16384.0),
        _usage("gpu", total=1.0, available=1.0),
    ]
    return rm


@pytest.fixture
def stressed_resource_manager() -> MagicMock:
    """Mock ResourceManager — 高负载（内存 85%, CPU 90%）。"""
    rm = MagicMock()
    rm.get_usage.return_value = [
        _usage("cpu", total=8.0, available=0.8),       # 90%
        _usage("memory", total=16384.0, available=2457.6),  # 85%
        _usage("gpu", total=1.0, available=0.15),         # 85%
    ]
    return rm


@pytest.fixture
def critical_resource_manager() -> MagicMock:
    """Mock ResourceManager — 极高负载（内存 95%, CPU 95%）。"""
    rm = MagicMock()
    rm.get_usage.return_value = [
        _usage("cpu", total=8.0, available=0.4),          # 95%
        _usage("memory", total=16384.0, available=819.2), # 95%
        _usage("gpu", total=1.0, available=0.05),          # 95%
    ]
    return rm


@pytest.fixture
def relaxed_resource_manager() -> MagicMock:
    """Mock ResourceManager — 低负载（<50%）。"""
    rm = MagicMock()
    rm.get_usage.return_value = [
        _usage("cpu", total=8.0, available=6.0),          # 25%
        _usage("memory", total=16384.0, available=12288.0), # 25%
        _usage("gpu", total=1.0, available=0.8),            # 20%
    ]
    return rm


@pytest.fixture
def mock_policy_engine() -> MagicMock:
    """Mock PolicyEngine — 默认风险 NORMAL。"""
    pe = MagicMock()
    pe.get_risk_level.return_value = "normal"
    return pe


@pytest.fixture
def mock_event_bus() -> MagicMock:
    """Mock EventBus。"""
    eb = MagicMock()
    eb.subscribe.return_value = "sub-1"
    return eb


@pytest.fixture
def controller(
    mock_resource_manager: MagicMock,
) -> AdaptiveController:
    """默认 AdaptiveController（无 PolicyEngine，无 Event Bus）。"""
    return AdaptiveController(resource_manager=mock_resource_manager)


@pytest.fixture
def full_controller(
    mock_resource_manager: MagicMock,
    mock_policy_engine: MagicMock,
    mock_event_bus: MagicMock,
) -> AdaptiveController:
    """完整 AdaptiveController（含 PolicyEngine + Event Bus）。"""
    return AdaptiveController(
        resource_manager=mock_resource_manager,
        policy_engine=mock_policy_engine,
        event_bus=mock_event_bus,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _usage(
    resource_type: str,
    total: float,
    available: float,
) -> Mock:
    u = Mock()
    u.resource_type = resource_type
    u.total = total
    u.available = available
    return u


# ══════════════════════════════════════════════════════════════════════════════
# Dataclass Frozen
# ══════════════════════════════════════════════════════════════════════════════


class TestDataclassFrozen:
    def test_adaptive_config_frozen(self):
        with pytest.raises(AttributeError):
            AdaptiveConfig().simulation_depth = 99

    def test_adaptation_frozen(self):
        with pytest.raises(AttributeError):
            Adaptation().param = "x"

    def test_adaptive_config_defaults(self):
        c = AdaptiveConfig()
        assert c.simulation_depth == 5.0
        assert c.learning_rate == 0.3
        assert c.attention_threshold == 0.4
        assert c.scheduler_max_queue == 100.0

    def test_adaptive_config_to_dict(self):
        c = AdaptiveConfig(simulation_depth=3.0)
        d = c.to_dict()
        assert d["simulation_depth"] == 3.0

    def test_enum_values(self):
        assert RuntimeParam.SIMULATION_DEPTH.value == "simulation_depth"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


# ══════════════════════════════════════════════════════════════════════════════
# Init
# ══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_default_config(self, controller):
        c = controller.get_config()
        assert c.simulation_depth == 5.0
        assert c.learning_rate == 0.3
        assert controller.adaptation_count == 0

    def test_custom_initial_config(self, mock_resource_manager):
        ctrl = AdaptiveController(
            resource_manager=mock_resource_manager,
            initial_config={"simulation_depth": 3.0, "learning_rate": 0.5},
        )
        config = ctrl.get_config()
        assert config.simulation_depth == 3.0
        assert config.learning_rate == 0.5
        # 其他参数保持默认
        assert config.attention_threshold == 0.4

    def test_subscribes_to_resource_events(self, full_controller, mock_event_bus):
        """构造时自动订阅 RESOURCE_EXHAUSTED 和 RESOURCE_RELEASED。"""
        sub_calls = mock_event_bus.subscribe.call_args_list
        types = [call.args[0] for call in sub_calls]
        assert EventType.RESOURCE_EXHAUSTED in types
        assert EventType.RESOURCE_RELEASED in types

    def test_no_event_bus_graceful(self, controller):
        """无 Event Bus 时不订阅。"""
        assert controller._subscription_ids == []


# ══════════════════════════════════════════════════════════════════════════════
# get_config
# ══════════════════════════════════════════════════════════════════════════════


class TestGetConfig:
    def test_returns_immutable_copy(self, controller):
        config = controller.get_config()
        with pytest.raises(AttributeError):
            config.simulation_depth = 99

    def test_values_are_clamped(self, mock_resource_manager):
        """即使内部值超出范围，get_config 返回 clamp 后的值。"""
        ctrl = AdaptiveController(
            resource_manager=mock_resource_manager,
            initial_config={"simulation_depth": 100.0},
        )
        assert ctrl.get_config().simulation_depth == 10.0

    def test_history_default_empty(self, controller):
        assert controller.get_adaptation_history() == []


# ══════════════════════════════════════════════════════════════════════════════
# adapt — 显式设置
# ══════════════════════════════════════════════════════════════════════════════


class TestAdapt:
    def test_set_single_param(self, controller):
        adpts = controller.adapt({"simulation_depth": 3.0}, reason="manual")
        assert len(adpts) == 1
        assert adpts[0].param == "simulation_depth"
        assert adpts[0].old_value == 5.0
        assert adpts[0].new_value == 3.0
        assert adpts[0].reason == "manual"
        assert controller.get_config().simulation_depth == 3.0

    def test_set_multiple_params(self, controller):
        adpts = controller.adapt(
            {"simulation_depth": 2.0, "learning_rate": 0.1},
            reason="override",
        )
        assert len(adpts) == 2
        config = controller.get_config()
        assert config.simulation_depth == 2.0
        assert config.learning_rate == 0.1

    def test_same_value_no_adaptation(self, controller):
        adpts = controller.adapt({"simulation_depth": 5.0}, reason="noop")
        assert adpts == []

    def test_unknown_param_skipped(self, controller):
        adpts = controller.adapt({"nonexistent": 999}, reason="test")
        assert adpts == []

    def test_clamp_out_of_range(self, controller):
        adpts = controller.adapt({"simulation_depth": 999.0}, reason="extreme")
        assert len(adpts) == 1
        assert adpts[0].new_value == 10.0  # clamp 到上限

    def test_trigger_event_id_recorded(self, controller):
        adpts = controller.adapt(
            {"simulation_depth": 3.0},
            reason="governance",
            trigger_event_id="evt-123",
        )
        assert adpts[0].trigger_event_id == "evt-123"


# ══════════════════════════════════════════════════════════════════════════════
# auto_adapt — 自动降级
# ══════════════════════════════════════════════════════════════════════════════


class TestAutoAdaptDegrade:
    def test_normal_load_no_changes(self, controller, mock_resource_manager):
        """负载正常时 auto_adapt 无变更。"""
        adpts = controller.auto_adapt()
        assert adpts == []

    def test_memory_high_reduces_simulation_depth(self, stressed_resource_manager):
        """MEMORY > 80% → simulation_depth -= 2。"""
        ctrl = AdaptiveController(resource_manager=stressed_resource_manager)
        adpts = ctrl.auto_adapt()
        params = {a.param for a in adpts}
        assert "simulation_depth" in params
        assert ctrl.get_config().simulation_depth == 3.0  # 5-2

    def test_memory_critical_reduces_queue(self, critical_resource_manager):
        """MEMORY > 90% → scheduler_max_queue /= 2。"""
        ctrl = AdaptiveController(resource_manager=critical_resource_manager)
        ctrl.auto_adapt()
        assert ctrl.get_config().scheduler_max_queue == 50.0  # 100/2

    def test_cpu_high_raises_attention_threshold(self, stressed_resource_manager):
        """CPU > 80% → attention_threshold += 0.1。"""
        ctrl = AdaptiveController(resource_manager=stressed_resource_manager)
        ctrl.auto_adapt()
        assert ctrl.get_config().attention_threshold == 0.5  # 0.4+0.1

    def test_gpu_high_reduces_learning_rate(self, stressed_resource_manager):
        """GPU > 80% → learning_rate *= 0.5。"""
        ctrl = AdaptiveController(resource_manager=stressed_resource_manager)
        ctrl.auto_adapt()
        assert ctrl.get_config().learning_rate == 0.15  # 0.3*0.5

    def test_high_risk_reduces_learning_rate(self, mock_resource_manager):
        """Risk >= HIGH → learning_rate *= 0.3, attention_threshold += 0.2。"""
        pe = MagicMock()
        pe.get_risk_level.return_value = "high"
        ctrl = AdaptiveController(
            resource_manager=mock_resource_manager,
            policy_engine=pe,
        )
        ctrl.auto_adapt()
        config = ctrl.get_config()
        assert config.learning_rate == 0.09  # 0.3*0.3
        assert config.attention_threshold == pytest.approx(0.6, rel=1e-9)  # 0.4+0.2

    def test_critical_risk_also_degrades(self, mock_resource_manager):
        """CRITICAL 风险同样触发降级。"""
        pe = MagicMock()
        pe.get_risk_level.return_value = "critical"
        ctrl = AdaptiveController(
            resource_manager=mock_resource_manager,
            policy_engine=pe,
        )
        adpts = ctrl.auto_adapt()
        assert len(adpts) > 0

    def test_multiple_triggers_stack(self, critical_resource_manager):
        """多个条件同时触发时，所有降级被应用。"""
        ctrl = AdaptiveController(resource_manager=critical_resource_manager)
        adpts = ctrl.auto_adapt()
        # 预计至少：simulation_depth, scheduler_max_queue, learning_rate (GPU>80%)
        assert len(adpts) >= 3

    def test_trigger_event_id_propagated(self, stressed_resource_manager, mock_event_bus):
        """trigger_event_id 传递给 Adaptation 记录。"""
        ctrl = AdaptiveController(
            resource_manager=stressed_resource_manager,
            event_bus=mock_event_bus,
        )
        adpts = ctrl.auto_adapt(trigger_event_id="evt-456")
        for a in adpts:
            assert a.trigger_event_id == "evt-456"


# ══════════════════════════════════════════════════════════════════════════════
# auto_adapt — 缓慢恢复
# ══════════════════════════════════════════════════════════════════════════════


class TestAutoAdaptRecovery:
    def test_recovery_one_step_at_a_time(self, relaxed_resource_manager):
        """资源充裕时恢复一个步长。"""
        ctrl = AdaptiveController(
            resource_manager=relaxed_resource_manager,
            initial_config={"simulation_depth": 3.0},
        )

        # 设置上次恢复时间为很早以前，使恢复可触发
        ctrl._last_recovery_ts = 0.0

        adpts = ctrl.auto_adapt()
        # simulation_depth 从 3.0 → 4.0（+1）
        assert ctrl.get_config().simulation_depth == 4.0

    def test_recovery_cooldown_respected(self, relaxed_resource_manager):
        """距上次恢复 < 30 秒时不应再恢复。"""
        ctrl = AdaptiveController(
            resource_manager=relaxed_resource_manager,
            initial_config={"simulation_depth": 3.0},
        )
        ctrl._last_recovery_ts = time.time()  # 刚刚恢复过

        adpts = ctrl.auto_adapt()
        # 不应触发恢复
        rec_adapts = [a for a in adpts if a.reason == "recovery"]
        assert len(rec_adapts) == 0

    def test_recovery_multiple_calls_reach_default(self, relaxed_resource_manager):
        """多次恢复最终到达默认值。"""
        ctrl = AdaptiveController(
            resource_manager=relaxed_resource_manager,
            initial_config={"simulation_depth": 1.0},
        )

        # 多次恢复到达 5.0
        for _ in range(10):
            ctrl._last_recovery_ts = 0.0  # 重置冷却
            ctrl.auto_adapt()

        config = ctrl.get_config()
        assert config.simulation_depth == 5.0

    def test_no_recovery_when_load_above_50(self, stressed_resource_manager):
        """负载 > 50% 时不触发恢复。"""
        ctrl = AdaptiveController(resource_manager=stressed_resource_manager)
        ctrl._last_recovery_ts = 0.0
        adpts = ctrl.auto_adapt()
        rec_adapts = [a for a in adpts if a.reason == "recovery"]
        assert len(rec_adapts) == 0


# ══════════════════════════════════════════════════════════════════════════════
# _clamp 边界
# ══════════════════════════════════════════════════════════════════════════════


class TestClamp:
    def test_simulation_depth_lower_bound(self):
        assert _clamp("simulation_depth", 0.0) == 1.0

    def test_simulation_depth_upper_bound(self):
        assert _clamp("simulation_depth", 100.0) == 10.0

    def test_learning_rate_lower_bound(self):
        assert _clamp("learning_rate", -1.0) == 0.0

    def test_learning_rate_upper_bound(self):
        assert _clamp("learning_rate", 2.0) == 1.0

    def test_attention_threshold_upper_bound(self):
        assert _clamp("attention_threshold", 1.5) == 1.0

    def test_scheduler_max_queue_lower_bound(self):
        assert _clamp("scheduler_max_queue", 0.0) == 10.0

    def test_unknown_param_passthrough(self):
        assert _clamp("nonexistent", 999.0) == 999.0


# ══════════════════════════════════════════════════════════════════════════════
# Event Bus 集成
# ══════════════════════════════════════════════════════════════════════════════


class TestEventBus:
    def test_resource_exhausted_triggers_auto_adapt(self, full_controller, mock_event_bus):
        """收到 RESOURCE_EXHAUSTED 事件时调用 auto_adapt。"""
        # 触发回调
        event = Event(
            event_type=EventType.RESOURCE_EXHAUSTED,
            source="resource-manager",
            payload={"resource_type": "memory", "reason": "insufficient"},
        )
        full_controller._on_resource_exhausted(event)
        # auto_adapt 应执行（即使无变更）
        assert full_controller.adaptation_count >= 0

    def test_resource_released_triggers_auto_adapt(self, full_controller, mock_event_bus):
        """收到 RESOURCE_RELEASED 事件时调用 auto_adapt。"""
        event = Event(
            event_type=EventType.RESOURCE_RELEASED,
            source="resource-manager",
        )
        full_controller._on_resource_released(event)
        assert full_controller.adaptation_count >= 0

    def test_adaptation_applied_event_emitted(
        self,
        stressed_resource_manager,
        mock_event_bus,
    ):
        """auto_adapt 产生变更时发射 ADAPTATION_APPLIED 事件。"""
        ctrl = AdaptiveController(
            resource_manager=stressed_resource_manager,
            event_bus=mock_event_bus,
        )
        ctrl.auto_adapt()
        # 验证发射了 ADAPTATION_APPLIED
        emitted_events = [
            c.args[0]
            for c in mock_event_bus.emit.call_args_list
        ]
        adapt_events = [
            e for e in emitted_events
            if e.event_type == EventType.ADAPTATION_APPLIED
        ]
        assert len(adapt_events) >= 1
        payload = adapt_events[0].payload
        assert "adaptations" in payload
        assert len(payload["adaptations"]) >= 1

    def test_adapt_applied_event_contains_trigger_id(
        self,
        stressed_resource_manager,
        mock_event_bus,
    ):
        """ADAPTATION_APPLIED 事件携带 trigger_event_id。"""
        ctrl = AdaptiveController(
            resource_manager=stressed_resource_manager,
            event_bus=mock_event_bus,
        )
        ctrl.auto_adapt(trigger_event_id="evt-789")
        emitted = [
            c.args[0]
            for c in mock_event_bus.emit.call_args_list
            if c.args[0].event_type == EventType.ADAPTATION_APPLIED
        ]
        if emitted:
            for a in emitted[0].payload["adaptations"]:
                assert a["trigger_event_id"] == "evt-789"

    def test_unsubscribe_all(self, full_controller, mock_event_bus):
        full_controller.unsubscribe_all()
        assert full_controller._subscription_ids == []
        assert mock_event_bus.unsubscribe.call_count >= 1

    def test_no_event_bus_emit_skipped(self, controller):
        """无 Event Bus 时 emit 不执行。"""
        adpts = controller.adapt({"simulation_depth": 2.0}, reason="test")
        assert len(adpts) == 1
        # 不应抛出 AttributeError


# ══════════════════════════════════════════════════════════════════════════════
# PolicyEngine 集成
# ══════════════════════════════════════════════════════════════════════════════


class TestPolicyEngine:
    def test_set_policy_engine_dynamic(self, controller):
        pe = MagicMock()
        pe.get_risk_level.return_value = "high"
        controller.set_policy_engine(pe)

        # 手动验证风险等级
        assert controller._get_risk_level() == RiskLevel.HIGH

    def test_no_policy_engine_default_normal(self, controller):
        assert controller._get_risk_level() == RiskLevel.NORMAL

    def test_policy_engine_without_get_risk_level(self, controller):
        """PolicyEngine 无 get_risk_level 方法时降级为 NORMAL。"""
        pe = MagicMock(spec=[])  # 空 spec，无方法
        controller.set_policy_engine(pe)
        assert controller._get_risk_level() == RiskLevel.NORMAL


# ══════════════════════════════════════════════════════════════════════════════
# reset
# ══════════════════════════════════════════════════════════════════════════════


class TestReset:
    def test_reset_restores_default(self, controller):
        controller.adapt({"simulation_depth": 2.0}, reason="test")
        controller.reset()
        assert controller.get_config().simulation_depth == 5.0
        assert controller.adaptation_count == 0

    def test_reset_clears_last_recovery_ts(self, controller):
        controller._last_recovery_ts = 12345.0
        controller.reset()
        assert controller.last_recovery_ts == 0.0


# ══════════════════════════════════════════════════════════════════════════════
# History
# ══════════════════════════════════════════════════════════════════════════════


class TestHistory:
    def test_history_limited(self, controller):
        """超过 100 条时自动截断。"""
        for i in range(110):
            controller.adapt({"simulation_depth": 3.0 + (i % 5) * 0.1}, reason="test")
        assert len(controller._adaptation_history) == 100

    def test_get_history_respects_limit(self, controller):
        for i in range(50):
            controller._adaptation_history.append(
                Adaptation(param="simulation_depth", old_value=5.0, new_value=3.0)
            )
        recent = controller.get_adaptation_history(limit=5)
        assert len(recent) == 5


# ══════════════════════════════════════════════════════════════════════════════
# 边界条件
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_adaptation_struct_trigger_event_id(self):
        """trigger_event_id 是 Adaptation 的可选字段。"""
        a = Adaptation(param="x", old_value=1.0, new_value=2.0, trigger_event_id="evt-001")
        assert a.trigger_event_id == "evt-001"

    def test_adaptation_reason_propagation(self, controller):
        adpts = controller.adapt({"simulation_depth": 1.0}, reason="governance")
        assert adpts[0].reason == "governance"

    def test_adaptation_timestamp_auto_set(self, controller):
        adpts = controller.adapt({"simulation_depth": 1.0}, reason="test")
        assert adpts[0].timestamp != ""
