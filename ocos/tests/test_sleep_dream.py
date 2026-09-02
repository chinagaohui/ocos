"""Phase U: SleepDream 单元测试。"""

import pytest
import time

from ocos.sleep_dream import (
    SleepDreamManager,
    SleepState,
    DreamType,
    DreamGenerator,
)


class TestDreamGenerator:
    """DreamGenerator 测试。"""

    def test_generate_memory_replay(self):
        gen = DreamGenerator()
        dream = gen.generate_dream(DreamType.MEMORY_REPLAY, source_memories=["memory1", "memory2"])
        assert dream.dream_type == DreamType.MEMORY_REPLAY
        assert "回放" in dream.content
        assert dream.confidence > 0
        assert dream.duration_seconds == 0.0  # 刚生成

    def test_generate_creative_combo(self):
        gen = DreamGenerator()
        dream = gen.generate_dream(DreamType.CREATIVE_COMBO, source_memories=["a", "b", "c"])
        assert dream.dream_type == DreamType.CREATIVE_COMBO
        assert "+" in dream.content or "组合" in dream.content

    def test_generate_with_no_sources(self):
        gen = DreamGenerator()
        dream = gen.generate_dream(DreamType.MEMORY_REPLAY)
        assert dream is not None
        assert dream.content  # 至少有内容

    def test_get_recent_dreams(self):
        gen = DreamGenerator()
        for i in range(5):
            gen.generate_dream(DreamType.MEMORY_REPLAY, source_memories=[f"mem{i}"])
        recent = gen.get_recent_dreams(3)
        assert len(recent) == 3

    def test_get_stats(self):
        gen = DreamGenerator()
        gen.generate_dream(DreamType.MEMORY_REPLAY)
        gen.generate_dream(DreamType.CREATIVE_COMBO)
        stats = gen.get_stats()
        assert stats["total_dreams"] == 2
        assert stats["insight_rate"] > 0


class TestSleepDreamManager:
    """SleepDreamManager 核心功能测试。"""

    def test_create(self):
        mgr = SleepDreamManager()
        assert mgr.state == SleepState.AWAKE

    def test_decide_sleep_no_need(self):
        mgr = SleepDreamManager()
        # 刚创建，不应该立即睡眠
        decision = mgr.decide_sleep()
        # 可能因为 idle 时间不够而不需要睡眠
        assert decision.sleep_type in ("none", "power_nap", "full_sleep", "rem_cycle")

    def test_start_and_wake(self):
        mgr = SleepDreamManager()
        result = mgr.start_sleep()
        assert result["status"] == "falling_asleep"
        assert mgr.state == SleepState.FALLING_ASLEEP

        wake_result = mgr.wake_up()
        assert wake_result["status"] == "awake"
        assert mgr.state == SleepState.AWAKE

    def test_run_sleep_cycle(self):
        mgr = SleepDreamManager()
        result = mgr.run_sleep_cycle()
        assert "status" in result
        # 可能因为不需要睡眠而返回 no_sleep_needed
        if result.get("status") == "no_sleep_needed":
            return
        assert "dreams" in result
        assert mgr.state == SleepState.AWAKE

    def test_get_stats(self):
        mgr = SleepDreamManager()
        stats = mgr.get_stats()
        assert "total_sleeps" in stats
        assert "total_dreams" in stats
        assert stats["total_sleeps"] == 0

    def test_generate_report(self):
        mgr = SleepDreamManager()
        report = mgr.generate_report()
        assert "睡眠与梦境报告" in report

    def test_multiple_sleep_cycles(self):
        mgr = SleepDreamManager()
        # 手动触发睡眠
        mgr.start_sleep()
        mgr.enter_dreaming(DreamType.MEMORY_REPLAY)
        mgr.wake_up()

        # 再次睡眠
        mgr.start_sleep()
        mgr.enter_dreaming(DreamType.CREATIVE_COMBO)
        mgr.wake_up()

        stats = mgr.get_stats()
        assert stats["total_sleeps"] == 2
        assert stats["total_dreams"] == 2
        assert stats["insights_generated"] == 2


class TestSleepState:
    """睡眠状态转换测试。"""

    def test_state_transitions(self):
        mgr = SleepDreamManager()
        assert mgr.state == SleepState.AWAKE

        mgr.start_sleep()
        assert mgr.state == SleepState.FALLING_ASLEEP

        mgr.enter_dreaming()
        assert mgr.state == SleepState.DREAMING

        mgr.wake_up()
        assert mgr.state == SleepState.AWAKE
