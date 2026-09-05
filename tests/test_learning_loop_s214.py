"""S2.14: 学习闭环三连修复回归（白皮书 P2）。

1. agent_runtime._extract_beliefs: outcome 判定含 "completed"
   （ExperienceStore.record 写入值），信念提取不再恒空转
2. outcome_evaluation: reliability 查 total 键（原查 count 恒 0.5）
3. calibration_store: 不再调用不存在的 update_reliability，诚实降级
"""

from __future__ import annotations

from ocos.agent.experience_store import ExperienceStore


class TestBeliefExtraction:
    def test_completed_outcome_yields_belief(self, tmp_path):
        """completed 经验 → 提取出信念（修复前恒空）。"""
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.agent.belief_system import BeliefSystem

        store = ExperienceStore()
        store.record(situation="写周报", action="分步总结",
                     outcome="completed", reflection="好",
                     importance=0.9)
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.experiences = store
        rt.beliefs = BeliefSystem()
        from ocos.agent.knowledge_base import KnowledgeBase
        rt.knowledge = KnowledgeBase()
        rt._extract_beliefs()
        held = rt.beliefs.get_all()
        assert any("分步总结" in b.statement for b in held), \
            "completed 经验应产出信念"


class TestReliabilityLookup:
    def test_reliability_uses_total_key(self, tmp_path):
        """有历史数据时 reliability 不再恒 0.5。"""
        from ocos.capability.experience_memory import (
            CapabilityExperienceMemory, ExperienceNode,
        )
        from ocos.capability.outcome_evaluation import OutcomeEvaluator

        mem = CapabilityExperienceMemory(":memory:")
        for i in range(6):
            node = ExperienceNode(
                experience_id=f"exp-{i}", capability_id="write",
                provider_id="prov-a", task_type="create",
                outcome="failure" if i == 0 else "success",
                quality_score=0.9, duration_ms=100,
                user_satisfaction=0.9)
            mem.save(node)
        evaluator = OutcomeEvaluator(experience_memory=mem)
        score = evaluator._reliability_score("write", "prov-a")
        # 5/6 成功率 ≈ 0.8333 —— 修复前因查 count 键恒取 0.5 兜底
        assert abs(score - 5 / 6) < 0.01, \
            f"reliability 应反映真实成功率(5/6)，实际 {score}"
        assert 0.0 <= score <= 1.0


class TestCalibrationHonesty:
    def test_no_fake_applied(self, tmp_path):
        """达标校准不再假报 applied=True。"""
        from ocos.capability.calibration_store import CalibrationStore

        store = CalibrationStore()
        for i in range(8):
            result = store.record_calibration(
                capability_id="write", provider_id="prov-a",
                calibration_delta=0.15)
        # 样本数达标后：本地校准累计，但不假报已写入后端
        assert result.applied is False
        assert "CALIBRATED" in result.reason
        assert result.cumulative_delta != 0
