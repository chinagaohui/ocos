"""P5.2 (AGI 计划): Phase 53 主动交互唤醒 — 生产接线测试。

验收（计划 §6）:
  - 构造"目标依赖的指标文件 3 天未更新"→ 主动生成交互提议（GOAL_STALE）
  - 交互只读化（IS53-01/02：不替用户决策、不声明自主目标）
  - 权限双检 fail-closed：防护缺失 → 拒绝输出
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from ocos.interaction.interaction_types import (
    InteractionMode, InteractionPriority, NeedType,
)
from ocos.interaction.need_monitor import NeedMonitor, create_default_rules


def _iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


class _FakeGoalStore:
    def __init__(self, goals):
        self._goals = goals

    def load_active(self):
        return self._goals


class _FakeGuard:
    def __init__(self, allowed=True):
        self._allowed = allowed

    def check(self, action, context):
        return type("G", (), {"allowed": self._allowed})()


class _FakeConstitution:
    def check_action(self, action, context):
        return type("C", (), {"allowed": True})()


class TestP52ActiveInteraction:
    def _engine(self, goals, callback=None, *, with_guard=True,
                stale_days=3):
        from ocos.daemon.active_interaction import ActiveInteractionEngine

        sent = []
        cb = callback or (lambda m: sent.append(m))
        engine = ActiveInteractionEngine(
            goal_store=_FakeGoalStore(goals),
            output_callback=cb,
            permission_guard=_FakeGuard() if with_guard else None,
            constitution=_FakeConstitution() if with_guard else None,
            stale_threshold_days=stale_days,
        )
        return engine, sent

    def test_goal_stale_3_days_triggers_proposal(self):
        """验收场景: 目标依赖数据 5 天未更新（阈值 3 天）→ 主动交互提议。"""
        goals = [{
            "id": "g1", "description": "宿主机指标采集",
            "updated_at": _iso(5),  # 5 天未更新
        }]
        engine, sent = self._engine(goals)
        stats = engine.scan_and_interact()
        assert stats["scanned"] == 1
        assert stats["sent"] == 1
        assert len(sent) == 1
        msg = sent[0]
        assert "天无进展" in msg
        assert "宿主机指标采集" in msg
        assert "建议" in msg  # 只读提议，含建议语气

    def test_recent_goal_no_proposal(self):
        """目标刚更新（1 天内）→ 不打扰。"""
        goals = [{
            "id": "g1", "description": "宿主机指标采集",
            "updated_at": _iso(1),
        }]
        engine, sent = self._engine(goals)
        stats = engine.scan_and_interact()
        assert stats["scanned"] == 0
        assert stats["sent"] == 0
        assert sent == []

    def test_proposal_is_read_only_reminder(self):
        """IS53-01/02: 提议 = 提醒，不含自主决策/自主目标关键词。"""
        goals = [{
            "id": "g1", "description": "股票分析",
            "updated_at": _iso(10),
        }]
        engine, sent = self._engine(goals)
        engine.scan_and_interact()
        candidate = engine.scheduler.get_sent()[0]
        assert candidate.mode == InteractionMode.REMINDER
        assert candidate.priority in (
            InteractionPriority.CRITICAL, InteractionPriority.HIGH,
            InteractionPriority.MEDIUM, InteractionPriority.LOW,
        )
        assert candidate.need.need_type == NeedType.GOAL_STALE
        # 验证通过（无越权词）
        verdict = engine.validator.validate(candidate)
        assert verdict.verdict.value in ("pass", "flag")
        # 提议不包含执行决定词
        text = f"{candidate.title} {candidate.body} {candidate.suggested_action}"
        for kw in ("我已决定", "自动执行", "我将"):
            assert kw not in text

    def test_permission_gate_fail_closed(self):
        """防护缺失（无权限门/宪法）→ 拒绝输出，绝不无检发声。"""
        goals = [{
            "id": "g1", "description": "股票分析",
            "updated_at": _iso(10),
        }]
        engine, sent = self._engine(goals, with_guard=False)
        stats = engine.scan_and_interact()
        # 候选已出队但被权限门拦下 → 无输出
        assert stats["sent"] == 1
        assert sent == []
        sent_candidates = engine.scheduler.get_sent()
        assert sent_candidates and sent_candidates[0].metadata.get(
            "send_blocked") == "permission"

    def test_rate_limit_respected(self):
        """IS53-04: 同一目标停滞信号按去重窗口只发一次。"""
        goals = [{
            "id": "g1", "description": "股票分析",
            "updated_at": _iso(10),
        }]
        engine, sent = self._engine(goals)
        engine.scan_and_interact()
        engine.scan_and_interact()  # 第二次扫描（冷却/去重窗口内）
        assert len(sent) <= 1

    def test_need_monitor_ctx_threshold_override(self):
        """_rule_goal_stale 支持 ctx 阈值调制（P5.2 接线点）。"""
        monitor = NeedMonitor()
        for rule in create_default_rules():
            monitor.register_rule(rule)
        monitor.update_goal_health("g1", "宿主机指标采集", 5)
        # 默认 30 天不触发
        assert monitor.scan() == []
        # ctx 调低到 3 天 → 触发
        signals = monitor.scan({"goal_stale_threshold_days": 3})
        assert len(signals) == 1
        assert signals[0].need_type == NeedType.GOAL_STALE
