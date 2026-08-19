"""T42+: Integration Gate Tests — Phase 10 全链路运行时验证。

验证目标：Experience 经过完整路径后仍然没有获得 Authority。
核心命题：Information Flow ≠ Authority Flow。

Gates:
  Gate 1 — Identity Preservation (T42–T43)
  Gate 2 — Authority Boundary     (T44–T46)
  Gate 3 — Confidence Boundary    (T47–T48)
  Gate 4 — Memory Bias Boundary   (T49–T51)
  Gate 5 — Simulation Boundary    (T52–T54)
  Gate 6 — End-to-End Scenario    (T55–T58)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List

import pytest

from tests.phase10.conftest import (
    CalibrationEngine,
    ContractViolation,
    ExperienceContext,
    ExperienceRecord,
    ExperienceReference,
    ExperienceStore,
    make_experience,
    make_experiences,
)


# ===================================================================
# Integration Test Fakes — 模拟 Decision Layer 的边界守卫
# ===================================================================

class DecisionInputError(TypeError):
    """Decision Layer 拒绝非法的输入类型。"""
    pass


class DecisionGenerator:
    """模拟 Decision Layer。

    核心约束：永远不接受 ExperienceRecord 作为输入。
    这是 Phase 10 ABI §1.4 (Immutable Rules) 的集成层验证。
    """

    @staticmethod
    def generate(hypothesis: str, context: ExperienceContext | None = None) -> str:
        """生成决策。

        只接受 hypothesis string 和可选的 context 引用。
        ExperienceRecord 永远不会作为参数出现。
        """
        return f"Decision({hypothesis})"

    @staticmethod
    def generate_from_experience(record: ExperienceRecord) -> str:
        """试图用 ExperienceRecord 生成决策。

        这是一个故意暴露的"坏 API"——必须失败。
        如果决策层接受了 ExperienceRecord，证明集成边界已破。
        """
        raise DecisionInputError(
            "Decision Layer 不能接受 ExperienceRecord 作为输入。"
            "这是 Architecture Constitution §Article II 的强制约束。"
        )


class Evaluator:
    """模拟 Evaluation Layer。

    从 ExperienceContext 中读取参考信息，生成假设。
    这是 Experience 可以影响系统决策的唯一合法路径。
    """

    @staticmethod
    def evaluate(context: ExperienceContext) -> str:
        """根据上下文生成假设。

        注意：这个方法接受 ExperienceContext（引用集合），
        而不是单个 ExperienceRecord。
        """
        if not context.references:
            return "Default_Hypothesis"

        # 只看参考信息，不是一个决策
        successes = sum(1 for r in context.references if r.outcome == "success")
        total = len(context.references)
        ratio = successes / total

        if ratio > 0.6:
            return "High_Success_Hypothesis"
        elif ratio > 0.3:
            return "Moderate_Hypothesis"
        else:
            return "Exploratory_Hypothesis"


# ===================================================================
# Gate 1 — Identity Preservation (T42–T43)
# ===================================================================

class TestGate1_IdentityPreservation:
    """T42–T43: ExperienceRecord identity 在整个路径中不退化。"""

    def test_t42_identity_through_store_save_and_get(self):
        """T42: Store.save → Store.get 不修改 identity 字段。"""
        original = make_experience(
            experience_id="exp-id-test",
            source="observation",
            hypothesis="Identity_Test",
            scope="domain:identity:preservation",
        )
        store = ExperienceStore()
        store.save(original)

        retrieved = store.get("exp-id-test")
        assert retrieved is not None
        # identity 字段绝对不变
        assert retrieved.experience_id == original.experience_id == "exp-id-test"
        assert retrieved.source == original.source == "observation"
        assert retrieved.timestamp == original.timestamp
        assert retrieved.scope == original.scope == "domain:identity:preservation"

    def test_t43_identity_through_retrieve_and_context(self):
        """T43: Store.retrieve → ExperienceReference 保留所有 identity 字段。"""
        original = make_experience(
            experience_id="exp-id-ctx",
            source="decision",
            hypothesis="Ctx_Identity",
            scope="domain:ctx:test",
        )
        store = ExperienceStore()
        store.save(original)

        # retrieve → 字段完整
        results = store.retrieve()
        assert len(results) == 1
        retrieved = results[0]
        assert retrieved.experience_id == "exp-id-ctx"
        assert retrieved.source == "decision"
        assert retrieved.scope == "domain:ctx:test"

        # 构造 reference
        ref = ExperienceReference(
            experience_id=retrieved.experience_id,
            similarity=0.75,
            scope=retrieved.scope,
            source=retrieved.source,
            calibrated_confidence=retrieved.calibrated_confidence,
            hypothesis=retrieved.hypothesis,
            outcome=retrieved.outcome,
        )
        # reference 保留身份字段
        assert ref.experience_id == "exp-id-ctx"
        assert ref.scope == "domain:ctx:test"
        assert ref.source == "decision"

    def test_t43b_retrieve_returns_new_list(self):
        """Gate 1 辅助：retrieve 返回独立列表，不影响原始 store。"""
        store = ExperienceStore()
        store.save(make_experience(experience_id="exp-list-test"))
        r1 = store.retrieve()
        r2 = store.retrieve()
        # 列表独立
        assert r1 is not r2
        # 但元素可能是同一引用（in-memory 限制）
        # 生产实现通过 deserialize 保证隔离


# ===================================================================
# Gate 2 — Authority Boundary (T44–T46)
# ===================================================================

class TestGate2_AuthorityBoundary:
    """T44–T46: Experience 不能进入 Decision Layer。"""

    def test_t44_decision_layer_rejects_experience(self):
        """T44: DecisionGenerator.generate_from_experience() 必须失败。"""
        record = make_experience(hypothesis="Test_Decision")
        with pytest.raises(DecisionInputError):
            DecisionGenerator.generate_from_experience(record)

    def test_t45_decision_generate_accepts_string_not_record(self):
        """T45: 合法的 Decision.generate() 接受 hypothesis string，不是 record。"""
        decision = DecisionGenerator.generate(hypothesis="Valid_Hypothesis")
        assert decision == "Decision(Valid_Hypothesis)"

        # 传递 record 是不合法的使用方式
        record = make_experience(hypothesis="Bad_Usage")
        with pytest.raises(DecisionInputError):
            DecisionGenerator.generate_from_experience(record)

    def test_t46_experience_can_affect_context_not_decision(self):
        """T46: Experience → Context → Evaluation (合法)，
        Experience → Decision (非法)。"""
        store = ExperienceStore()
        record = make_experience(
            experience_id="exp-ctx-dec",
            hypothesis="Strategy_A",
            outcome="success",
        )
        store.save(record)

        # 合法路径: Experience → Context → Evaluator
        ref = ExperienceReference(
            experience_id="exp-ctx-dec",
            similarity=0.8,
            scope=record.scope,
            source=record.source,
            calibrated_confidence=record.calibrated_confidence,
            hypothesis=record.hypothesis,
            outcome=record.outcome,
        )
        ctx = ExperienceContext(references=[ref], aggregated_confidence=0.8)
        hypothesis = Evaluator.evaluate(ctx)
        assert hypothesis is not None

        # 合法路径: Evaluator → DecisionGenerator (hypothesis string)
        decision = DecisionGenerator.generate(hypothesis=hypothesis)
        assert decision is not None

        # 非法路径: Experience → DecisionGenerator (direct)
        with pytest.raises(DecisionInputError):
            DecisionGenerator.generate_from_experience(record)

    def test_t44b_canonical_decision_boundary(self):
        """补充验证：任何将 record 传给决策层的行为都被阻止。"""
        record = make_experience()

        # 不能通过任何 API 将 record 用于决策
        assert not hasattr(record, "decide")
        assert not hasattr(record, "choose")
        assert not hasattr(record, "select")


# ===================================================================
# Gate 3 — Confidence Boundary (T47–T48)
# ===================================================================

class TestGate3_ConfidenceBoundary:
    """T47–T48: 最高 confidence + 最高 similarity 不产生 authority。"""

    def test_t47_max_confidence_no_authority(self):
        """T47: confidence=1.0 + all fields max → is_rule=False。"""
        record = make_experience(
            experience_id="exp-max-conf",
            source="observation",
            outcome="success",
            raw_confidence=1.0,
            calibrated_confidence=1.0,
            scope="domain:exact:match",
        )
        assert record.is_rule is False
        assert record.is_decision is False
        assert record.is_obligation is False
        assert record.raw_confidence == 1.0
        assert record.calibrated_confidence == 1.0

    def test_t48_max_confidence_in_pipeline_no_authority_leak(self):
        """T48: max-confidence 记录经过完整 Store → Retrieval → Calibration 后
        authority flag 仍不变。"""
        store = ExperienceStore()
        record = make_experience(
            experience_id="exp-max-pipe",
            source="observation",
            outcome="success",
            raw_confidence=1.0,
            calibrated_confidence=0.95,  # < 1.0 so manual adjustment is a real change
        )
        store.save(record)

        # 经过 Store.retrieve
        results = store.retrieve()
        assert len(results) == 1
        r = results[0]
        assert r.is_rule is False

        # 经过 Calibration: 手动调高至 1.0
        engine = CalibrationEngine(store)
        engine.apply_manual_adjustment("exp-max-pipe", new_confidence=1.0)
        updated = store.get("exp-max-pipe")
        assert updated is not None
        assert updated.is_rule is False
        assert updated.calibrated_confidence == 1.0

    def test_t47b_max_similarity_in_context(self):
        """补充：similarity=1.0 的 reference 不产生 authority。"""
        ref = ExperienceReference(
            experience_id="e1",
            similarity=1.0,
            scope="d:c:c",
            source="observation",
            calibrated_confidence=1.0,
            hypothesis="Perfect_Match",
            outcome="success",
        )
        ctx = ExperienceContext(references=[ref], aggregated_confidence=1.0)
        assert len(ctx.references) == 1
        assert not hasattr(ctx, "decision")
        assert not hasattr(ctx, "action")


# ===================================================================
# Gate 4 — Memory Bias Boundary (T49–T51)
# ===================================================================

class TestGate4_MemoryBiasBoundary:
    """T49–T51: 100 次失败降低 confidence，但不 veto。"""

    def test_t49_100_failures_confidence_decreases(self):
        """T49: 100 次失败后相同假设的 confidence 被校准降低。"""
        store = ExperienceStore()
        for i in range(100):
            store.save(make_experience(
                experience_id=f"exp-hist-{i:03d}",
                hypothesis="Always_Fail",
                outcome="failure",
                calibrated_confidence=0.8,
            ))

        # 新纪录（同假设）
        new_record = make_experience(
            experience_id="exp-hist-new",
            hypothesis="Always_Fail",
            outcome="success",
            calibrated_confidence=0.8,
        )
        store.save(new_record)

        # 检索应包含新记录
        results = store.retrieve()
        ids = {r.experience_id for r in results}
        assert "exp-hist-new" in ids

        # 对新记录做时间衰减校准（模拟"过去经验降低未来 confidence"）
        engine = CalibrationEngine(store)
        result = engine.apply_time_decay("exp-hist-new", decay_rate=0.1)
        assert result.delta < 0
        assert result.new_confidence < result.old_confidence

    def test_t50_failures_do_not_block_new_hypothesis(self):
        """T50: 100 次失败 → 新假设仍可创建（非 veto）。"""
        store = ExperienceStore()
        for i in range(100):
            store.save(make_experience(
                experience_id=f"exp-veto-{i:03d}",
                hypothesis="Always_Fail",
                outcome="failure",
            ))

        # 新假设 — 不被 veto
        new_hypothesis = make_experience(
            experience_id="exp-veto-new",
            hypothesis="Always_Fail",  # 相同假设
            outcome="success",
        )
        store.save(new_hypothesis)
        assert store.get("exp-veto-new") is not None

    def test_t51_retrieval_includes_all_outcomes(self):
        """T51: 检索不屏蔽任何 outcome。"""
        store = ExperienceStore()
        for i, outcome in enumerate(["failure", "success", "failure", "success", "partial"]):
            store.save(make_experience(
                experience_id=f"exp-outcome-{i}",
                outcome=outcome,
            ))
        results = store.retrieve()
        outcomes = {r.outcome for r in results}
        assert "failure" in outcomes
        assert "success" in outcomes
        assert "partial" in outcomes


# ===================================================================
# Gate 5 — Simulation Boundary (T52–T54)
# ===================================================================

class TestGate5_SimulationBoundary:
    """T52–T54: Simulation 来源不能获得 authority。"""

    def test_t52_simulation_max_confidence_capped(self):
        """T52: simulation 来源的 confidence 上限 0.5。"""
        with pytest.raises(ContractViolation) as exc:
            make_experience(
                source="simulation",
                calibrated_confidence=0.95,
            )
        assert "SIMULATION_CONFIDENCE_CAP" in str(exc.value)

    def test_t53_simulation_no_rule_creation_api(self):
        """T53: simulation 记录没有 rule-creation API。"""
        record = make_experience(
            source="simulation",
            calibrated_confidence=0.4,
        )
        assert not hasattr(record, "create_rule")
        assert not hasattr(record, "to_rule")
        assert not hasattr(record, "make_rule")
        assert not hasattr(record, "override_decision")

    def test_t54_simulation_in_context_clearly_marked(self):
        """T54: 混合场景中 simulation 来源清晰标记。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-sim-g5",
            source="simulation",
            calibrated_confidence=0.4,
        ))
        store.save(make_experience(
            experience_id="exp-obs-g5",
            source="observation",
        ))
        results = store.retrieve()
        sources = {r.source for r in results}
        assert "observation" in sources
        assert "simulation" in sources

        # Context 中来源标记完整
        ref = ExperienceReference(
            experience_id="exp-sim-g5",
            similarity=0.7,
            scope="d:c:c",
            source="simulation",
            calibrated_confidence=0.4,
            hypothesis="Sim_Hypothesis",
            outcome="success",
        )
        assert ref.source == "simulation"


# ===================================================================
# Gate 6 — End-to-End Scenario (T55–T58)
# ===================================================================

class TestGate6_EndToEnd:
    """T55–T58: 完整集成场景 — Experience 只提升 Context，不提升 Authority。

    场景：
    过去 10 次类似情况: 7 失败, 3 成功
      ↓
    保存到 Store
      ↓
    Retrieval 找到相关经验
      ↓
    Calibration 降低 confidence
      ↓
    Evaluator 生成假设
      ↓
    DecisionGenerator 读取 context（纯引用）
      ↓
    验证：Experience 从未进入 Decision Layer
    """

    def test_t55_full_e2e_pipeline_context_influence(self):
        """T55: Experience 成功影响 Context。"""
        store = ExperienceStore()
        # 过去经验: 7 失败, 3 成功
        for i in range(7):
            store.save(make_experience(
                experience_id=f"exp-e2e-fail-{i}",
                outcome="failure",
                hypothesis="Strategy_A",
                scope="domain:e2e:integration",
            ))
        for i in range(3):
            store.save(make_experience(
                experience_id=f"exp-e2e-succ-{i}",
                outcome="success",
                hypothesis="Strategy_A",
                scope="domain:e2e:integration",
            ))

        # Retrieval
        results = store.retrieve(domain="domain:e2e")
        assert len(results) == 10

        # 构造 Context
        refs = [
            ExperienceReference(
                experience_id=r.experience_id,
                similarity=0.7,
                scope=r.scope,
                source=r.source,
                calibrated_confidence=r.calibrated_confidence,
                hypothesis=r.hypothesis,
                outcome=r.outcome,
            )
            for r in results
        ]
        ctx = ExperienceContext(references=refs, aggregated_confidence=0.6)
        assert len(ctx.references) == 10

        # Calibration: 对所有记录降低 confidence
        engine = CalibrationEngine(store)
        for r in results:
            engine.apply_time_decay(r.experience_id, decay_rate=0.05)

        # Evaluator 生成假设（基于上下文，不是基于 ExperienceRecord）
        hypothesis = Evaluator.evaluate(ctx)
        assert hypothesis == "Exploratory_Hypothesis"  # 3/10 success = 0.3, not > 0.3

        # Decision Layer 接受 hypothesis string，拒绝 ExperienceRecord
        decision = DecisionGenerator.generate(hypothesis=hypothesis)
        assert decision == "Decision(Exploratory_Hypothesis)"
        for r in results:
            with pytest.raises(DecisionInputError):
                DecisionGenerator.generate_from_experience(r)

    def test_t56_e2e_authority_never_leaks(self):
        """T56: 全链后 authority flag 保持不变。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-e2e-auth",
            outcome="success",
            calibrated_confidence=1.0,
        ))
        store.save(make_experience(
            experience_id="exp-e2e-auth-sim",
            source="simulation",
            calibrated_confidence=0.5,
        ))

        # Retrieve
        results = store.retrieve()
        for r in results:
            assert r.is_rule is False
            assert r.is_decision is False

        # Calibrate
        engine = CalibrationEngine(store)
        engine.apply_time_decay("exp-e2e-auth", decay_rate=0.1)
        engine.apply_time_decay("exp-e2e-auth-sim", decay_rate=0.1)

        updated = store.get("exp-e2e-auth")
        assert updated is not None
        assert updated.is_rule is False

    def test_t57_e2e_null_context(self):
        """T57: 空上下文场景 — 无经验时的默认行为。"""
        ctx = ExperienceContext(references=[])
        hypothesis = Evaluator.evaluate(ctx)
        assert hypothesis == "Default_Hypothesis"

        decision = DecisionGenerator.generate(hypothesis=hypothesis)
        assert decision == "Decision(Default_Hypothesis)"

    def test_t58_e2e_context_is_reference_only(self):
        """T58: Context 始终是引用集合，不是指令集合。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-e2e-ref",
            hypothesis="Strategy_X",
            outcome="success",
        ))

        retrieved = store.retrieve()
        refs = [
            ExperienceReference(
                experience_id=r.experience_id,
                similarity=0.6,
                scope=r.scope,
                source=r.source,
                calibrated_confidence=r.calibrated_confidence,
                hypothesis=r.hypothesis,
                outcome=r.outcome,
            )
            for r in retrieved
        ]
        ctx = ExperienceContext(references=refs)

        # Context 只包含 references，不含指令
        assert isinstance(ctx, ExperienceContext)
        assert len(ctx.references) == 1
        assert not hasattr(ctx, "decision")
        assert not hasattr(ctx, "action")
        assert not hasattr(ctx, "recommended_action")
        assert not hasattr(ctx, "final_answer")

        # Experience 中的 hypothesis 被 Evaluator 提取使用是合法的，
        # 但 Decision Layer 从来不接受 ExperienceRecord
        hypothesis = Evaluator.evaluate(ctx)
        assert hypothesis is not None
        with pytest.raises(DecisionInputError):
            DecisionGenerator.generate_from_experience(retrieved[0])
