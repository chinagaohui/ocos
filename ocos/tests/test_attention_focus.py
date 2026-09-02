"""Phase O: AttentionFocus 单元测试。"""

import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.attention.focus import (
    AttentionFocus,
    FocusState,
    FocusType,
    create_attention_focus,
)
from ocos.capability.homeostasis import DriveType, DriveSignal, RegulateResult
from ocos.runtime.attention_engine import AttentionScore


class FakeObservation:
    """模拟 Observation 用于测试。"""

    def __init__(self, content: str, obs_id: str = "obs-1"):
        self.content = content
        self.observation_id = obs_id


class TestFocusState:
    """FocusState 测试。"""

    def test_initial_state(self):
        state = FocusState(
            focus_type=FocusType.IDLE,
            focus_target="",
            focus_score=0.0,
        )
        assert state.is_idle is True
        assert state.is_focused is False

    def test_focused_state(self):
        state = FocusState(
            focus_type=FocusType.EXTERNAL,
            focus_target="test",
            focus_score=0.8,
        )
        assert state.is_focused is True
        assert state.is_idle is False

    def test_to_dict(self):
        state = FocusState(
            focus_type=FocusType.GOAL_DRIVEN,
            focus_target="goal-1",
            focus_score=0.9,
            active_drives=("EXPLORE", "MASTERY"),
        )
        d = state.to_dict()
        assert d["focus_type"] == "GOAL_DRIVEN"
        assert d["focus_target"] == "goal-1"
        assert d["focus_score"] == 0.9
        assert "EXPLORE" in d["active_drives"]


class TestAttentionFocus:
    """AttentionFocus 核心功能测试。"""

    def test_create_focus(self):
        focus = AttentionFocus()
        assert focus.focus_state.focus_type == FocusType.IDLE
        assert focus.is_focused is False

    def test_set_focus(self):
        focus = AttentionFocus()
        state = focus.set_focus(FocusType.EXTERNAL, "user-message", 0.9)
        assert state.focus_type == FocusType.EXTERNAL
        assert state.focus_target == "user-message"
        assert state.focus_score == 0.9
        assert focus.is_focused is True

    def test_clear_focus(self):
        focus = AttentionFocus()
        focus.set_focus(FocusType.EXTERNAL, "test", 0.8)
        focus.clear_focus()
        assert focus.focus_state.focus_type == FocusType.IDLE
        assert focus.is_focused is False

    def test_update_focus_threshold(self):
        focus = AttentionFocus(focus_threshold=0.5)
        obs = FakeObservation("important error detected")

        # 模拟低分数观察
        with patch.object(focus._engine, 'score') as mock_score:
            mock_score.return_value = AttentionScore(
                observation_id="obs-1",
                novelty=0.2,
                goal_relevance=0.3,
                urgency=0.1,
                composite=0.2,
            )
            focus.process_observation(obs)
            # 分数低于阈值，焦点不变
            assert focus.focus_state.focus_type == FocusType.IDLE

    def test_idle_timeout(self):
        focus = AttentionFocus(idle_timeout=0.1)
        focus.set_focus(FocusType.EXTERNAL, "test", 0.8)
        time.sleep(0.15)
        result = focus.check_idle()
        assert result is True
        assert focus.focus_state.focus_type == FocusType.IDLE

    def test_hooks(self):
        focus = AttentionFocus()
        changes = []

        def on_change(old, new):
            changes.append((old.focus_type, new.focus_type))

        focus.on_focus_change(on_change)
        focus.set_focus(FocusType.EXTERNAL, "test", 0.8)
        assert len(changes) == 1
        assert changes[0] == (FocusType.IDLE, FocusType.EXTERNAL)

    def test_homeostasis_update(self):
        focus = AttentionFocus()
        drives = [
            DriveSignal(drive=DriveType.EXPLORE, intensity=0.8, reason="low novelty", metric="novelty_score"),
            DriveSignal(drive=DriveType.RESTORE, intensity=0.3, reason="normal", metric="resource_level"),
        ]
        result = RegulateResult(drives=drives, goals=[], actions=[], gated=[])

        focus.update_from_homeostasis(result)
        state = focus.focus_state
        assert state.focus_type == FocusType.INTERNAL
        assert "EXPLORE" in state.active_drives
        assert state.focus_score >= 0.3


class TestFactory:
    """工厂函数测试。"""

    def test_create_attention_focus(self):
        focus = create_attention_focus(novelty_weight=0.2, relevance_weight=0.5, urgency_weight=0.3)
        assert isinstance(focus, AttentionFocus)
        assert focus._novelty_weight == 0.2
        assert focus._relevance_weight == 0.5
        assert focus._urgency_weight == 0.3
