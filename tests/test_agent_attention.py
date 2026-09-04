"""OCOS agent attention/capability_selector/cortex_intent 测试。"""

import pytest
from ocos.agent.attention import Attention, FocusMode
from ocos.agent.capability_selector import CapabilitySelector
from ocos.agent.cortex_activator import CortexActivator, CortexMode
from ocos.agent.intent import Intent


class TestAttention:
    def test_focus_modes(self):
        assert FocusMode.FOCUSED.value == "focused"
        assert FocusMode.SCANNING.value == "scanning"
        assert FocusMode.IDLE.value == "idle"
        assert FocusMode.DISTRIBUTED.value == "distributed"

    def test_default_state(self):
        a = Attention()
        assert a.mode == FocusMode.IDLE
        assert a.fatigue == 0.0
        assert a.current_focus is None

    def test_focus_item(self):
        a = Attention()
        a.focus("item1", "type_a", 0.8)
        assert a.mode == FocusMode.FOCUSED
        assert a.current_focus == "item1"

    def test_unfocus(self):
        a = Attention()
        a.focus("item1", "type_a", 0.8)
        a.unfocus("item1")
        assert a.current_focus is None
        assert a.mode == FocusMode.IDLE

    def test_switch_to_higher_priority(self):
        a = Attention()
        a.focus("item1", "type_a", 0.5)
        result = a.switch_to("item2", 0.8)
        assert result is True
        assert a.current_focus == "item2"

    def test_switch_to_lower_priority_fails(self):
        a = Attention()
        a.focus("item1", "type_a", 0.8)
        result = a.switch_to("item2", 0.5)
        assert result is False
        assert a.current_focus == "item1"

    def test_fatigue_accumulates(self):
        a = Attention()
        a.focus("item1", "type_a", 0.8)
        for _ in range(10):
            a.tick(seconds=1.0)
        assert a.fatigue > 0.0

    def test_fatigue_rate_by_mode(self):
        focused = Attention()
        scanning = Attention()
        idle = Attention()
        focused.focus("i1", "t", 0.8)
        scanning.focus("i2", "t", 0.8)
        idle.focus("i3", "t", 0.8)
        # Set different modes directly
        focused.mode = FocusMode.FOCUSED
        scanning.mode = FocusMode.SCANNING
        idle.mode = FocusMode.IDLE
        for _ in range(100):
            focused.tick(seconds=1.0)
            scanning.tick(seconds=1.0)
            idle.tick(seconds=1.0)
        assert focused.fatigue > scanning.fatigue > idle.fatigue

    def test_needs_sleep(self):
        a = Attention()
        # Manually set high fatigue
        a._fatigue = 0.95
        assert a.needs_sleep() is True
        a._fatigue = 0.5
        assert a.needs_sleep() is False

    def test_reset(self):
        a = Attention()
        a.focus("item1", "type_a", 0.8)
        a._fatigue = 0.5
        a.reset()
        assert a.fatigue == 0.0
        assert a.mode == FocusMode.IDLE
        # Note: reset() doesn't clear current_focus, only fatigue and mode


class TestCapabilitySelector:
    @pytest.fixture
    def selector(self):
        return CapabilitySelector(engine_list=["planner", "writer", "reader"])

    def test_map_create(self, selector):
        result = selector.map("create")
        assert result == ["planner", "writer"]

    def test_map_unknown(self, selector):
        assert selector.map("unknown") == []

    def test_register_custom_mapping(self, selector):
        selector.register_mapping("custom", ["special"])
        assert selector.map("custom") == ["special"]

    def test_unregister_mapping(self, selector):
        selector.register_mapping("temp", ["a"])
        selector.unregister_mapping("temp")
        assert selector.map("temp") == []

    def test_get_available_intents(self, selector):
        intents = selector.get_available_intents()
        assert "create" in intents
        assert "search" in intents

    def test_get_required_engines(self, selector):
        engines = selector.get_required_engines("create")
        assert "planner" in engines
        assert "writer" in engines


class TestCortexActivator:
    def test_initial_mode(self):
        c = CortexActivator()
        assert c.mode == CortexMode.ACTIVE
        assert c.is_active() is True

    def test_sleep_and_recover(self):
        c = CortexActivator()
        c.sleep()
        assert c.mode == CortexMode.SLEEPING
        c.activate()
        assert c.mode == CortexMode.ACTIVE

    def test_block_and_emergency(self):
        c = CortexActivator()
        c.block()
        assert c.mode == CortexMode.BLOCKED
        assert c.is_blocked() is True
        result = c.emergency_activate()
        assert result is True
        assert c.mode == CortexMode.EMERGENCY

    def test_block_needs_intervention(self):
        c = CortexActivator()
        for _ in range(3):
            c.block()
        assert c.needs_intervention() is True

    def test_emergency_blocked_three_times(self):
        c = CortexActivator()
        for _ in range(3):
            c.block()
        result = c.emergency_activate()
        assert result is False

    def test_recover_from_emergency (self):
        c = CortexActivator()
        c.block()
        c.emergency_activate()
        assert c.recover() is True
        assert c.mode == CortexMode.ACTIVE

    def test_get_status(self):
        c = CortexActivator()
        status = c.get_status()
        assert status["mode"] == "ACTIVE"
        assert status["is_active"] is True
        assert status["needs_intervention"] is False


class TestIntent:
    @pytest.fixture
    def intent(self):
        return Intent()

    def test_extract_create_intent(self, intent):
        result = intent.extract("Create a new story chapter")
        assert result["type"] == "create"
        assert result["confidence"] > 0

    def test_extract_analyze_intent(self, intent):
        result = intent.extract("Analyze the character development")
        assert result["type"] == "analyze"

    def test_extract_unknown_intent(self, intent):
        result = intent.extract("xyz abc def")
        assert result["type"] == "unknown"
        assert result["confidence"] == 0.0

    def test_get_intent_type(self, intent):
        intent.extract("Write a new chapter")
        assert intent.get_intent_type() == "create"

    def test_get_confidence(self, intent):
        intent.extract("Write a new chapter and scene")
        assert intent.get_confidence() > 0

    def test_reset(self, intent):
        intent.extract("Create something")
        intent.reset()
        assert intent.get_intent_type() == "unknown"
        assert intent.get_confidence() == 0.0
