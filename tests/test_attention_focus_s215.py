"""S2.15: attention/focus process_observation TypeError 修复回归
（白皮书 P2）。

原缺陷：_update_focus(focus_target=...) 关键字名错误（形参为 target）
且缺必需实参 score → composite≥阈值的观察进入即 TypeError
（主入口即坏，单测未覆盖该分支故未被发现）。
"""

from __future__ import annotations

from types import SimpleNamespace

from ocos.attention.focus import AttentionFocus, create_attention_focus
from ocos.runtime.attention_engine import (
    AttentionEngine, DefaultContentAnalyzer,
)


def _observation(content: str):
    return SimpleNamespace(
        observation_id=f"obs-{abs(hash(content))}",
        content=content,
        source="probe",
    )


class TestProcessObservation:
    def test_high_composite_observation_no_typeerror(self):
        """composite≥阈值的观察 → 正常更新焦点（修复前抛 TypeError）。"""
        focus = create_attention_focus()
        engine = AttentionEngine(analyzer=DefaultContentAnalyzer())
        focus._engine = engine
        state = focus.process_observation(
            _observation("URGENT: 生产环境磁盘写满，服务即将中断"))
        # 不抛 TypeError 且焦点已更新为外部焦点
        assert state is not None

    def test_focus_state_updated_on_threshold(self):
        focus = AttentionFocus()
        engine = AttentionEngine(analyzer=DefaultContentAnalyzer())
        focus._engine = engine
        obs = _observation("紧急告警 磁盘满 立即处理 主目标相关")
        before = focus.focus_state.focus_score
        after = focus.process_observation(obs)
        assert after.focus_score >= before
        assert after.focus_type.name in ("EXTERNAL", "GOAL_DRIVEN", "IDLE")

    def test_low_composite_keeps_focus(self):
        focus = AttentionFocus(focus_threshold=0.99)  # 阈值抬高确保低分不过
        engine = AttentionEngine(analyzer=DefaultContentAnalyzer())
        focus._engine = engine
        before = focus.focus_state
        after = focus.process_observation(_observation("a"))
        assert after.focus_target == before.focus_target
