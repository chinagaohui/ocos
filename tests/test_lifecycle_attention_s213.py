"""S2.13: 生命周期编排器注意力兼容层回归（白皮书 P1-10）。

复核确认（修正评审版 R6 的误判）：生产注入的
CognitiveAttentionController 只有 tick/fatigue/reset_fatigue，
无 needs_sleep/reset —— 原编排器 _tick_idle/_tick_sleep 无守卫直调
→ AttributeError 被 tick() 吞为 TickResult.ERROR（P1-10 成立）。
"""

from __future__ import annotations

import types

import pytest

from ocos.agent.life_cycle_orchestrator import LifeCycleOrchestrator
from ocos.capability.attention import CognitiveAttentionController


def _orchestrator(attention):
    agent = types.SimpleNamespace(
        attention=attention,
        sleep=lambda: None, dream=lambda: None,
        observe=lambda: None, think=lambda: None, decide=lambda: None,
        act=lambda: None, reflect=lambda: None, learn=lambda: None,
        maybe_proactive_output=lambda: None,
    )
    return LifeCycleOrchestrator(agent)


class TestAttentionCompat:
    def test_production_attention_no_error(self):
        """生产注意力对象下三个兼容方法不再抛 AttributeError。"""
        o = _orchestrator(CognitiveAttentionController())
        assert o._attention_fatigued() is False  # 初始不疲劳
        o._attention_tick()
        o._attention_reset()  # 回退 reset_fatigue，不抛

    def test_legacy_attention_still_works(self):
        """旧 Attention（有 needs_sleep/tick/reset）走原路径。"""
        class _LegacyAttention:
            def needs_sleep(self):
                return False

            def tick(self, seconds):
                pass

            def reset(self):
                pass

        o = _orchestrator(_LegacyAttention())
        assert o._attention_fatigued() is False
        o._attention_tick()
        o._attention_reset()

    def test_fatigue_threshold_triggers_sleep(self):
        """fatigue>0.9 → 疲劳判定为真（等效旧 needs_sleep）。"""
        att = CognitiveAttentionController()
        att._fatigue = 0.95
        o = _orchestrator(att)
        assert o._attention_fatigued() is True

    def test_incapable_attention_warns_not_raises(self):
        """无任何疲劳能力的注意力对象 → warning + False，不抛。"""
        o = _orchestrator(types.SimpleNamespace())
        assert o._attention_fatigued() is False
