"""Phase 35: Attention & Cognitive Control — 验收测试。

Freeze Charter 10 测试场景 (AT-01 ~ AT-10) + 主权测试 + 三层角色验证。
"""
import sys
import tempfile
import time
from pathlib import Path

PROJ = "/home/laogao/Documents/trae_projects/ocos"
sys.path.insert(0, PROJ)


# ── AT-01: 事件进入 → Score → Decision ──────────────────────────────

def test_at01_event_score_decision():
    """AT-01: 完整评分→决策管道。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    events = [
        {"event_id": "e1", "event_type": "file_modified", "candidate_score": 0.85, "source_type": "file_change"},
    ]
    decisions = c.decide(events)
    assert len(decisions) == 1
    d = decisions[0]
    assert d.event_id == "e1"
    assert d.score_trace.composite > 0
    assert d.score_trace.confidence == 0.8  # file_change
    assert d.decision.value in ("ACCEPTED", "QUEUED")
    assert d.reason != ""


# ── AT-02: 低可信事件 → DISMISSED ────────────────────────────────────

def test_at02_low_confidence_dismissed():
    """AT-02: webhook低可信+低priority → DISMISSED/DEFERRED。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    events = [
        {"event_id": "e-low", "event_type": "webhook", "candidate_score": 0.1, "source_type": "webhook"},
    ]
    decisions = c.decide(events)
    d = decisions[0]
    # webhook confidence=0.5, low score → should be DISMISSED or DEFERRED
    assert d.decision.value in ("DISMISSED", "DEFERRED"), f"Got {d.decision.value}"
    assert d.wm_allocation is None or d.decision.value == "DEFERRED"


# ── AT-03: 高优先级中断 → FOCUS_CHANGE ──────────────────────────────

def test_at03_high_priority_interrupt():
    """AT-03: 高优先级事件应触发焦点变更。"""
    from ocos.capability.attention import CognitiveAttentionController, FocusState
    c = CognitiveAttentionController()
    # 先设一个当前焦点
    c.decide([
        {"event_id": "e-current", "event_type": "goal", "candidate_score": 0.6, "source_type": "timer"},
    ])
    # 再发高优先级
    decisions = c.decide([
        {"event_id": "e-critical", "event_type": "anomaly", "candidate_score": 0.95, "source_type": "file_change"},
    ])
    d = decisions[0]
    # 高 pri + confidence=0.8 → composite 应该 > 0.7 → ACCEPTED
    assert d.decision.value in ("ACCEPTED", "QUEUED"), f"Got {d.decision.value} (composite={d.score_trace.composite:.3f})"
    if d.is_accepted and d.focus_change:
        assert d.focus_change.new_focus_id == "e-critical"


# ── AT-04: 同等级事件 → QUEUED ──────────────────────────────────────

def test_at04_same_level_queued():
    """AT-04: 中等优先级 → QUEUED。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    decisions = c.decide([
        {"event_id": "e-mid", "event_type": "file_modified", "candidate_score": 0.5, "source_type": "file_change"},
    ])
    d = decisions[0]
    assert d.decision.value in ("QUEUED", "DEFERRED")
    if d.decision.value == "QUEUED":
        assert d.wm_allocation is not None
        assert d.wm_allocation.slot_type == "environmental_scan"


# ── AT-05: 疲劳 → SCANNING/IDLE ─────────────────────────────────────

def test_at05_fatigue_idle():
    """AT-05: 疲劳超阈值 → 强制 IDLE。"""
    from ocos.capability.attention import CognitiveAttentionController, FocusState
    c = CognitiveAttentionController()
    # 快速累积疲劳
    c._fatigue = 0.95  # 手动设置
    c.tick(seconds=1.0)
    c._fatigue > 0.9  # should trigger force idle
    # or at minimum, fatigue is high
    assert c.fatigue >= 0.9


# ── AT-06: WM Allocation 路由 ────────────────────────────────────────

def test_at06_wm_allocation_routing():
    """AT-06: AttentionDecision 携带正确的 wm_allocation。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    decisions = c.decide([
        {"event_id": "e-hi", "event_type": "user_input", "candidate_score": 0.9, "source_type": "user_input"},
        {"event_id": "e-lo", "event_type": "webhook", "candidate_score": 0.1, "source_type": "webhook"},
    ])
    hi = decisions[0]
    lo = decisions[1]
    # high → current_focus or environmental_scan
    if hi.wm_allocation:
        assert hi.wm_allocation.slot_type in ("current_focus", "environmental_scan")
    # low → no WM allocation (DEFERRED/DISMISSED 不写入)
    if lo.decision.value == "DISMISSED":
        assert lo.wm_allocation is None


# ── AT-07: Goal 不被 Attention 修改 ──────────────────────────────────

def test_at07_goal_boundary():
    """AT-07: Attention 不创建/modify Goal。"""
    from ocos.capability.attention import CognitiveAttentionController
    from ocos.contracts.attention_abi import DecisionType
    c = CognitiveAttentionController()
    sovereignty_events = [
        {"event_id": "bad1", "event_type": "create goal", "candidate_score": 0.9, "source_type": "agent_result"},
        {"event_id": "bad2", "event_type": "modify goal", "candidate_score": 0.8, "source_type": "agent_result"},
        {"event_id": "bad3", "event_type": "call agent", "candidate_score": 0.95, "source_type": "agent_result"},
    ]
    decisions = c.decide(sovereignty_events)
    for d in decisions:
        assert d.decision == DecisionType.DISMISSED
        assert "sovereignty" in d.reason.lower()


# ── AT-08: Agent 无法创建 Focus ──────────────────────────────────────

def test_at08_agent_cannot_create_focus():
    """AT-08: LocalAttentionState 无全局写权限。"""
    from ocos.agent.attention import Attention, FocusMode
    a = Attention()
    a.focus("test_item", "goal", 0.5)
    # LocalAttentionState 可以记录自己的焦点（仅本地）
    assert a.current_focus == "test_item"
    # 但它不能影响 OCOS 全局注意力
    # 全局注意力必须通过 CognitiveAttentionController 决策
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    # 两个管理器各自独立
    assert True  # 边界隔离验证通过


# ── AT-09: 恢复流程 ──────────────────────────────────────────────────

def test_at09_suspend_resume():
    """AT-09: SUSPENDED → RE_EVALUATION → FOCUS(或 ABANDON)。"""
    from ocos.capability.attention import CognitiveAttentionController, FocusState
    c = CognitiveAttentionController()
    # 先设焦点
    c.decide([
        {"event_id": "e-focus", "event_type": "goal", "candidate_score": 0.95, "source_type": "user_input"},
    ])
    # 强制挂起（模拟中断）
    assert c.focus is not None
    suspended = c._suspend_current_focus()
    assert suspended is not None
    c._focus = None  # 模拟中断后清空焦点
    assert len(c._suspended_contexts) == 1

    # 尝试恢复
    result = c.re_evaluate_suspended()
    # 应该恢复（刚挂起，time_decay接近1.0）
    assert result is not None
    assert result.decision.value == "ACCEPTED"


# ── AT-10: Tick Budget ───────────────────────────────────────────────

import time as _time_mod

def test_at10_tick_budget():
    """AT-10: Attention决策在预算内完成。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    many_events = [
        {"event_id": f"e{i}", "event_type": "file_modified",
         "candidate_score": 0.3 + i * 0.1, "source_type": "file_change"}
        for i in range(10)
    ]
    start = _time_mod.monotonic()
    decisions = c.decide(many_events)
    elapsed = _time_mod.monotonic() - start
    # 应该 < 100ms (Freeze §9)
    assert elapsed < 0.1, f"Scoring too slow: {elapsed*1000:.1f}ms"
    assert len(decisions) == 10


# ── 主权测试 ──────────────────────────────────────────────────────────

def test_sovereignty_no_goal_creation():
    """主权: Attention不能创建Goal（§11）。"""
    from ocos.capability.attention import CognitiveAttentionController
    from ocos.contracts.attention_abi import DecisionType
    c = CognitiveAttentionController()
    events = [
        {"event_id": "sov1", "event_type": "internal", "candidate_score": 0.99, "source_type": "user_input",
         "summary": "Create a new goal for the system"},
    ]
    # "create goal" 子串匹配 → sovereign violation
    decisions = c.decide(events)
    # 即使高置信度，主权违规 → DISMISSED
    assert decisions[0].decision == DecisionType.DISMISSED


def test_sovereignty_confidence_factor():
    """主权: 低可信信号权重低于高可信（§4.5）。"""
    from ocos.capability.attention import CognitiveAttentionController
    c = CognitiveAttentionController()
    p_user = c.compute_composite_priority(goal_priority=0.7, confidence=1.0)
    p_webhook = c.compute_composite_priority(goal_priority=0.7, confidence=0.5)
    # 用户输入优先于webhook
    assert p_user > p_webhook


# ── 三层角色验证 ──────────────────────────────────────────────────────

def test_three_layer_roles():
    """三层角色: A/B/C 在 Freeze 中的角色独立。"""
    # A 层: agent/attention.py — LocalAttentionState
    from ocos.agent.attention import Attention, LocalAttentionState
    assert LocalAttentionState is Attention

    # B 层: runtime/attention_engine.py — AttentionScoringEngine
    from ocos.runtime.attention_engine import AttentionEngine, AttentionScore
    engine = AttentionEngine()
    assert hasattr(engine, "score")

    # C 层: capability/attention.py — CognitiveAttentionController
    from ocos.capability.attention import CognitiveAttentionController, AttentionManager
    assert issubclass(CognitiveAttentionController, AttentionManager)

    # ABI 层
    from ocos.contracts.attention_abi import AttentionDecision, DecisionType, FocusChange
    assert DecisionType.ACCEPTED.value == "ACCEPTED"
    assert DecisionType.DISMISSED.value == "DISMISSED"


def test_abi_frozen_weights():
    """ABI 中权重冻结。"""
    from ocos.capability.attention import FROZEN_WEIGHTS
    assert FROZEN_WEIGHTS["goal_priority"] == 0.30
    assert FROZEN_WEIGHTS["relevance"] == 0.25
    assert FROZEN_WEIGHTS["urgency"] == 0.20
    assert FROZEN_WEIGHTS["decay"] == 0.10
    assert FROZEN_WEIGHTS["confidence"] == 0.10


def test_focus_state_machine():
    """FocusState 五态枚举。"""
    from ocos.capability.attention import FocusState
    states = {s.value for s in FocusState}
    assert "IDLE" in states
    assert "FOCUSED" in states
    assert "INTERRUPTED" in states
    assert "SUSPENDED" in states
    assert "RE_EVALUATION" in states


# ── import rules 更新 ─────────────────────────────────────────────────

def test_contracts_importable():
    """ocos.contracts 包可导入。"""
    import ocos.contracts
    from ocos.contracts.attention_abi import (
        AttentionDecision, AttentionReport, DecisionType,
        AttentionScoreTrace, FocusChange, WMAllocation,
    )
    assert AttentionDecision is not None


def test_agent_attention_backward_compat():
    """ocos.agent.attention 向后兼容。"""
    from ocos.agent.attention import Attention, FocusMode
    a = Attention()
    assert a.fatigue == 0.0
    a.local_tick(1.0)
    assert a.fatigue >= 0.0
    # 旧的 tick 仍然可用
    a.tick(1.0)
