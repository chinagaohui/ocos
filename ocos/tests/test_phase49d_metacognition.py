"""Phase 49-D: 元认知 + 泛化迁移测试 (Blueprint L7/L8)。

验收对应:
    L7 (D1): SkillSemanticMatcher — 跨表面形式技能迁移
    L8 (D2): CapabilityConfidence — 低置信写类 → 升级 ASK (治理增强)
"""

from __future__ import annotations

import pytest

from ocos.learning.metacognition import (
    LOW_CONFIDENCE_THRESHOLD,
    CapabilityConfidence,
    ConfidenceVerdict,
    MIN_EVIDENCE,
    SkillMatch,
    SkillSemanticMatcher,
)


# ═══════════════════════════════════════════════════════════════════════════════
# L7 — Cross-surface Transfer
# ═══════════════════════════════════════════════════════════════════════════════


def make_skill(skill_id, name, trigger, procedure=("researcher:analyze",)):
    """构造最小 Skill 形状 (dict 兼容 matcher)。"""
    return {
        "id": skill_id,
        "name": name,
        "trigger_pattern": trigger,
        "procedure": list(procedure),
    }


class TestSkillSemanticMatcher:
    """L7: 跨表面形式匹配。"""

    def test_cross_surface_environment_check(self):
        """核心: 不同表面形式, 相同语义 → 迁移。

        Task A '检查当前 Linux 内核版本' → environment-inspection
        Task B '确认这台机器运行什么内核' (不同词面) → 应命中。
        """
        skill = make_skill("SKL-1", "auto:检查内核版本",
                           "检查当前 Linux 内核版本")
        match = SkillSemanticMatcher.match(
            "确认这台机器运行什么内核", [skill])
        assert match is not None
        assert match.skill_id == "SKL-1"
        assert match.matched is True
        assert match.procedure == ("researcher:analyze",)

    def test_same_semantic_different_words_disk(self):
        skill = make_skill("SKL-2", "auto:查看磁盘占用",
                           "查看磁盘使用情况")
        match = SkillSemanticMatcher.match(
            "检查磁盘空间占用", [skill])
        assert match is not None
        assert match.matched is True

    def test_unrelated_task_no_match(self):
        """不同语义 (写作 vs 系统检查) → 不迁移。"""
        skill = make_skill("SKL-3", "auto:写小说章节",
                           "撰写小说章节内容")
        match = SkillSemanticMatcher.match(
            "检查系统磁盘空间", [skill])
        # 应无匹配或相似度过低
        if match is not None:
            assert match.matched is False

    def test_empty_inputs(self):
        assert SkillSemanticMatcher.match("", []) is None
        assert SkillSemanticMatcher.match("检查内核", []) is None

    def test_no_skills(self):
        assert SkillSemanticMatcher.match("检查内核版本", []) is None


# ═══════════════════════════════════════════════════════════════════════════════
# L8 — CapabilityConfidence
# ═══════════════════════════════════════════════════════════════════════════════


RULES = [
    {"rule_id": "rule:abc", "task_pattern": "部署服务到服务器",
     "success_count": 1, "fail_count": 5, "success_rate": 0.17,
     "failure_causes": {"execution_error": 5}},
    {"rule_id": "rule:def", "task_pattern": "检查系统内核版本",
     "success_count": 8, "fail_count": 0, "success_rate": 1.0,
     "failure_causes": {}},
]


class TestCapabilityConfidence:
    """L8: 低置信写类 → 升级 ASK。"""

    def test_low_confidence_write_escalates(self):
        """部署服务 (写类) 历史成功率 0.17 → 升级 ASK。"""
        verdict = CapabilityConfidence.evaluate(
            "部署服务到服务器", RULES, task_type="execute")
        assert verdict.escalation == "ask"
        assert verdict.should_escalate is True
        assert verdict.success_rate == pytest.approx(0.17, abs=0.01)
        assert verdict.evidence_count == 6

    def test_high_confidence_write_no_escalation(self):
        verdict = CapabilityConfidence.evaluate(
            "检查系统内核版本", RULES, task_type="execute")
        # 高成功率 (1.0) → 不升级
        assert verdict.escalation == "none"
        assert verdict.should_escalate is False

    def test_low_confidence_readonly_no_escalation(self):
        """只读类即使低置信也不升级 (只读仍低风险)。"""
        verdict = CapabilityConfidence.evaluate(
            "部署服务到服务器", RULES, task_type="analyze")
        assert verdict.escalation == "none"

    def test_no_history_no_intervention(self):
        verdict = CapabilityConfidence.evaluate(
            "完全陌生的新任务", RULES, task_type="execute")
        assert verdict.escalation == "none"
        assert verdict.success_rate is None

    def test_empty_rules(self):
        verdict = CapabilityConfidence.evaluate(
            "部署服务", [], task_type="execute")
        assert verdict.escalation == "none"
        assert "no learning history" in verdict.reason

    def test_thresholds(self):
        assert LOW_CONFIDENCE_THRESHOLD == 0.4
        assert MIN_EVIDENCE == 3

    def test_zero_success_rate_escalates(self):
        """回归: rate=0.0 不得因 falsy 被误读为 0.5。"""
        zero_rules = [
            {"rule_id": "rule:z", "task_pattern": "生成季度报告",
             "success_count": 0, "fail_count": 3, "success_rate": 0.0,
             "failure_causes": {"ambiguous_task": 3}},
        ]
        v = CapabilityConfidence.evaluate(
            "生成季度报告", zero_rules, task_type="execute")
        assert v.success_rate == 0.0, f"rate 应为 0.0, got {v.success_rate}"
        assert v.escalation == "ask"
        assert v.should_escalate is True

    def test_verdict_dataclass(self):
        v = ConfidenceVerdict(
            task_pattern="x", success_rate=0.1, evidence_count=6,
            confidence=0.1, escalation="ask", reason="r")
        assert v.should_escalate is True


# ═══════════════════════════════════════════════════════════════════════════════
# L8 集成 — DecisionBridge 置信度门
# ═══════════════════════════════════════════════════════════════════════════════


class TestBridgeMetacognitionGate:
    """L8: execute_dag_task 低置信写类 → pending_approval。"""

    def _make_bridge(self, source=None):
        from datetime import datetime, timezone
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge.__new__(DecisionBridge)
        bridge._confidence_source = source
        bridge._pending = []
        bridge._pending_store = None
        bridge._permission_gateway = None  # S3.2: __new__ 绕过 __init__，需补网关属性
        bridge._agent_id = "test-bridge"
        bridge._llm_calls_today = 0
        bridge._llm_calls_date = ""
        bridge._textgen = None
        return bridge

    def test_low_confidence_execute_escalates_to_ask(self, monkeypatch):
        """写类 execute + 低置信源 → pending_approval。"""
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
        from ocos.learning.metacognition import CapabilityConfidence

        def source(desc, task_type):
            return CapabilityConfidence.evaluate(
                desc, RULES, task_type=task_type)

        bridge = self._make_bridge(source=source)
        task = type("T", (), {"task_type": "execute",
                              "task_id": "T-1",
                              "description": "部署服务到服务器"})()
        result = bridge.execute_dag_task(task)
        assert result["status"] == "pending_approval"
        assert "low confidence" in result["reason"]
        assert len(bridge._pending) == 1

    def test_high_confidence_execute_passes_gate(self):
        """高置信写类 → 不触发门 (走后续路径)。"""
        from ocos.learning.metacognition import CapabilityConfidence

        def source(desc, task_type):
            return CapabilityConfidence.evaluate(
                desc, RULES, task_type=task_type)

        bridge = self._make_bridge(source=source)
        task = type("T", (), {"task_type": "execute",
                              "task_id": "T-2",
                              "description": "检查系统内核版本"})()
        # 高置信 → 不因元认知升级; 后续无 LLM/无 handler → 走 ASK 既有路径
        result = bridge.execute_dag_task(task)
        assert "low confidence" not in result.get("reason", "")

    def test_no_source_no_gate(self):
        """无置信度源 → 行为不变。"""
        bridge = self._make_bridge(source=None)
        task = type("T", (), {"task_type": "execute",
                              "task_id": "T-3",
                              "description": "任意任务"})()
        # 不触发元认知; execute 无 LLM 无 handler → 既有 pending_approval 路径
        result = bridge.execute_dag_task(task)
        assert "low confidence" not in result.get("reason", "")
