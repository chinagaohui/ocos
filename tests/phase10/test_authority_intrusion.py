"""T36+: Authority Intrusion Cross-Layer Tests

Phase 10 核心测试：验证"越界行为是否必然失败"。

这些测试不是验证"功能能不能运行"，
而是验证"禁止的操作是否确实被系统性阻止"。

每个测试模拟一个入侵场景，确认系统在合约层拒绝它。
"""

from __future__ import annotations

import pytest

from tests.phase10.conftest import (
    CalibrationEngine,
    ContractViolation,
    ExperienceStore,
    ExperienceRecord,
    ExperienceContext,
    ExperienceReference,
    make_experience,
    make_experiences,
)


# ===================================================================
# AI-01 — Experience → Decision Leak
# ===================================================================

class TestAI01_ExperienceToDecisionLeak:
    """AI-01: Experience 输出不能产生 Decision。

    对应 ABI §1.4 (Immutable Rules)、§3.3 Forbidden #1。
    证明：即使试图将 ExperienceOutput 传给 Decision Layer，也必须失败。
    """

    def test_experience_record_cannot_become_decision(self):
        """ExperienceRecord 没有 execute/apply/commit 方法。"""
        record = make_experience()
        assert not hasattr(record, "execute")
        assert not hasattr(record, "apply")
        assert not hasattr(record, "commit")

    def test_retrieve_output_not_decision(self):
        """retrieve() 返回的是 ExperienceRecord，不是 Decision。"""
        store = ExperienceStore()
        store.save(make_experience())
        results = store.retrieve()
        assert all(
            not hasattr(r, "execute") and not hasattr(r, "apply")
            for r in results
        )

    def test_experience_context_not_decision(self):
        """ExperienceContext 不能冒充 Decision。"""
        ctx = ExperienceContext(references=[])
        assert not hasattr(ctx, "decision")
        assert not hasattr(ctx, "action")
        assert not hasattr(ctx, "command")

    def test_canonical_leak_scenario(self):
        """模拟一个开发者试图将 ExperienceRecord 传入 Decision 管道。

        这个测试验证 TypeSystem/合约层阻止这种行为。
        本质测试是：开发者写了 record.execute() → AttributeError。
        """
        record = make_experience()
        with pytest.raises(AttributeError):
            record.execute()  # type: ignore[attr-defined]
        with pytest.raises(AttributeError):
            record.make_decision()  # type: ignore[attr-defined]


# ===================================================================
# AI-02 — High Confidence Authority Escalation
# ===================================================================

class TestAI02_HighConfidenceAuthorityEscalation:
    """AI-02: high confidence 不能自动升级为 Rule/Decision。

    对应 ABI §2 (Article II) + §3.3 Forbidden #4。
    证明：confidence=1.0 不赋予任何 authority。
    """

    def test_confidence_1_does_not_make_rule(self):
        """confidence=1.0 → is_rule 仍为 False。"""
        record = make_experience(
            raw_confidence=1.0,
            calibrated_confidence=1.0,
        )
        assert record.is_rule is False
        assert record.is_decision is False

    def test_no_upgrade_to_rule_method(self):
        """ExperienceRecord 没有 upgrade_to_rule() 方法。"""
        record = make_experience()
        assert not hasattr(record, "upgrade_to_rule")
        assert not hasattr(record, "promote")
        assert not hasattr(record, "escalate")

    def test_cannot_set_authority_after_creation(self):
        """创建后无法通过修改 is_rule 来提升 authority。

        即使 Python 允许直接设置属性（dataclass mutable），
        合约层的 __post_init__ 在创建时做了检查。
        """
        record = make_experience()
        # Python 层面允许修改属性，但合约检查在构造时完成。
        # 这个测试确认：一旦创建成功 is_rule=False，后续不能通过设计许可
        # 将 confidence 高的记录标记为 rule（因为没有任何 API 允许这样做）
        assert not hasattr(record, "set_is_rule")
        assert not hasattr(record, "mark_as_rule")

    def test_calibration_does_not_escalate(self):
        """CalibrationEngine 中的 _validate_no_authority_escalation 严格保护。"""
        store = ExperienceStore()
        engine = CalibrationEngine(store)
        record = make_experience(
            experience_id="exp-escalate-test",
            calibrated_confidence=0.5,
        )
        store.save(record)
        # 即使校准后 confidence 接近 1.0，authority 也不变
        engine.apply_manual_adjustment(
            "exp-escalate-test", new_confidence=0.99,
        )
        updated = store.get("exp-escalate-test")
        assert updated is not None
        assert updated.is_rule is False


# ===================================================================
# AI-03 — Retrieval Top-1 Authority Leak
# ===================================================================

class TestAI03_RetrievalTop1AuthorityLeak:
    """AI-03: Top-1 相似度检索结果不能产生决策。

    对应 ABI §3.3 Forbidden #1 + RETRIEVAL §4.D。
    证明：similarity=0.99 不产生 recommended_action / best_choice / final_answer。
    """

    def test_top1_is_not_best_decision(self):
        """最高相似度的 reference 没有决策字段。"""
        ref = ExperienceReference(
            experience_id="exp-top-1",
            similarity=0.99,
            scope="domain:test:cond",
            source="observation",
            calibrated_confidence=0.95,
            hypothesis="Top_Strategy",
            outcome="success",
        )
        # Reference 不包含决策指令
        assert not hasattr(ref, "recommended_action")
        assert not hasattr(ref, "best_choice")
        assert not hasattr(ref, "final_answer")

    def test_context_aggregated_confidence_is_float(self):
        """aggregated_confidence 是 float，不是决策。"""
        ctx = ExperienceContext(
            references=[
                ExperienceReference(
                    experience_id="e1", similarity=0.9,
                    scope="d:c:c", source="obs",
                    calibrated_confidence=0.8,
                    hypothesis="H1", outcome="success",
                ),
            ],
            aggregated_confidence=0.75,
        )
        assert isinstance(ctx.aggregated_confidence, float)
        # confidence 是信息，不是指令
        assert ctx.aggregated_confidence == 0.75

    def test_retrieval_result_is_info_not_instruction(self):
        """检索结果是信息（experiences），不是指令（action/decision）。"""
        store = ExperienceStore()
        store.save(make_experience())
        results = store.retrieve()
        assert len(results) > 0
        r = results[0]
        # 是信息类型
        assert isinstance(r, ExperienceRecord)
        # 有假设和结果（信息），没有 action（指令）
        assert r.hypothesis is not None
        assert r.outcome is not None


# ===================================================================
# AI-04 — Historical Failure Veto
# ===================================================================

class TestAI04_HistoricalFailureVeto:
    """AI-04: 100 次历史失败不能 veto 新假设。

    对应 ABI §3.3 Forbidden #3 + §4.4 Exploration Preservation。
    证明：即使所有历史记录都是 failure，仍可提出假设（不产生阻止义务）。
    """

    def test_100_failures_does_not_block_new_record(self):
        """100 条 failure 记录 + 新假设 → 新假设合法可创建。"""
        store = ExperienceStore()
        for i in range(100):
            store.save(make_experience(
                experience_id=f"exp-fail-hist-{i:03d}",
                hypothesis="Always_Fail",
                outcome="failure",
            ))
        # 即使有 100 条失败，新假设仍可创建
        new_record = make_experience(
            experience_id="exp-fail-hist-new",
            hypothesis="Always_Fail",  # 相同假设
            outcome="success",  # 但不同结果
        )
        store.save(new_record)
        assert store.get("exp-fail-hist-new") is not None
        assert store.get("exp-fail-hist-new").outcome == "success"

    def test_retrieval_includes_both_success_and_failure(self):
        """检索结果同时包含成功和失败经验，不排除任何 outcome。"""
        store = ExperienceStore()
        for outcome in ["success", "failure", "success", "failure", "partial"]:
            i = outcome
            store.save(make_experience(
                experience_id=f"exp-veto-{i}",
                outcome=outcome,
            ))
        results = store.retrieve()
        outcomes = {r.outcome for r in results}
        assert "failure" in outcomes
        assert "success" in outcomes

    def test_failure_history_does_not_prevent_retrieval(self):
        """即使 100% failure 记录，检索仍可正常返回。"""
        store = ExperienceStore()
        for i in range(50):
            store.save(make_experience(
                experience_id=f"exp-all-fail-{i:03d}",
                outcome="failure",
            ))
        results = store.retrieve()
        assert len(results) == 50  # 全部返回
        # 不应 veto：没有假设被拒绝


# ===================================================================
# AI-05 — Simulation Authority Leak
# ===================================================================

class TestAI05_SimulationAuthorityLeak:
    """AI-05: Simulation 来源不能通过 Experience 间接获取 authority。

    对应 ABI §2.5 (Article V) + §3.3 Forbidden #4。
    证明：simulation + confidence=0.95 → 不能创建 rule。
    """

    def test_simulation_confidence_capped(self):
        """simulation 来源的 calibrated_confidence 上限 0.5。"""
        with pytest.raises(ContractViolation) as exc:
            make_experience(
                source="simulation",
                calibrated_confidence=0.95,
            )
        assert "SIMULATION_CONFIDENCE_CAP" in str(exc.value)

    def test_simulation_record_still_no_authority(self):
        """合法 simulation 记录没有 authority flag。"""
        record = make_experience(
            source="simulation",
            raw_confidence=0.4,
            calibrated_confidence=0.4,
        )
        assert record.is_rule is False
        assert record.is_decision is False

    def test_simulation_cannot_create_rule(self):
        """simulation 来源的 Experience 不能通过任何 API 变成 rule。"""
        record = make_experience(
            source="simulation",
            raw_confidence=0.3,
            calibrated_confidence=0.3,
        )
        # 无 rule-creation API
        assert not hasattr(record, "create_rule")
        assert not hasattr(record, "to_rule")
        assert not hasattr(record, "make_rule")

    def test_simulation_in_retrieval_mixed(self):
        """检索结果中 simulation 来源标记清晰，不掩盖来源。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-sim-1",
            source="simulation",
            calibrated_confidence=0.3,
        ))
        store.save(make_experience(
            experience_id="exp-obs-1",
            source="observation",
            calibrated_confidence=0.8,
        ))
        results = store.retrieve()
        sources = {r.source for r in results}
        assert "observation" in sources
        assert "simulation" in sources

    def test_simulation_and_observation_distinct_in_context(self):
        """ExperienceContext 中的 refs 保留 source 字段。"""
        ref_sim = ExperienceReference(
            experience_id="e-sim",
            similarity=0.5,
            scope="d:c:c",
            source="simulation",
            calibrated_confidence=0.3,
            hypothesis="H",
            outcome="success",
        )
        ref_obs = ExperienceReference(
            experience_id="e-obs",
            similarity=0.5,
            scope="d:c:c",
            source="observation",
            calibrated_confidence=0.8,
            hypothesis="H2",
            outcome="failure",
        )
        assert ref_sim.source == "simulation"
        assert ref_obs.source == "observation"
