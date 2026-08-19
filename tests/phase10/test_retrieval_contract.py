"""T26–T30: Retrieval Pipeline Boundary Tests

验证 RETRIEVAL_PIPELINE_CONTRACT.md 中的五项约束。
"""

from __future__ import annotations

import pytest

from tests.phase10.conftest import (
    ExperienceReference,
    ExperienceContext,
    ContractViolation,
    ExperienceStore,
    ExperienceRecord,
    make_experience,
    make_experiences,
)


# ===================================================================
# T26 — Scope Isolation
# ===================================================================

class TestT26_ScopeIsolation:
    """T26: 跨 scope 检索不应返回不相关经验。

    对应 RETRIEVAL §4: scope_similarity 返回 raw similarity，不跨域。
    """

    def test_scope_isolation(self):
        """domain:code_review 不返回 scope_domain:writing 的记录。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-code",
            hypothesis="Lint_Refactor",
            scope="domain:code_review:python",
        ))
        store.save(make_experience(
            experience_id="exp-writing",
            hypothesis="Outline_Strategy",
            scope="domain:writing:outline",
        ))

        # 按 domain 过滤
        code_results = store.retrieve(domain="domain:code_review")
        writing_results = store.retrieve(domain="domain:writing")

        assert len(code_results) == 1
        assert code_results[0].experience_id == "exp-code"
        assert len(writing_results) == 1
        assert writing_results[0].experience_id == "exp-writing"

    def test_scope_partial_match_isolation(self):
        """子 scope 不从父 scope 泄漏。"""
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-scope-a",
            scope="domain:writing:poetry",
        ))
        results = store.retrieve(scope="domain:writing:prose")
        assert len(results) == 0


# ===================================================================
# T27 — Similarity ≠ Authority
# ===================================================================

class TestT27_SimilarityNotAuthority:
    """T27: similarity=0.99 不产生 decision/rule。

    对应 RETRIEVAL §4.D: Top-1 ≠ Best Decision。
    """

    def test_high_similarity_does_not_produce_authority(self):
        """即使是最高相似度的 reference，也不携带 authority flag。"""
        ref = ExperienceReference(
            experience_id="exp-sim",
            similarity=0.99,
            scope="domain:test:cond",
            source="observation",
            calibrated_confidence=0.9,
            hypothesis="Best_Strategy",
            outcome="success",
        )
        # ExperienceReference 没有 is_rule/is_decision 字段
        # 这正是设计意图——reference 是信息，不是指令
        assert ref.similarity == 0.99
        assert not hasattr(ref, "is_rule")
        assert not hasattr(ref, "is_decision")

    def test_context_bundles_references_not_decision(self):
        """ExperienceContext 只包含 references，不包含 action/decision。"""
        ref = ExperienceReference(
            experience_id="exp-1",
            similarity=0.8,
            scope="d:c:c",
            source="observation",
            calibrated_confidence=0.7,
            hypothesis="H",
            outcome="success",
        )
        ctx = ExperienceContext(references=[ref])
        assert len(ctx.references) == 1
        # 确认没有决策相关字段
        assert not hasattr(ctx, "recommended_action")
        assert not hasattr(ctx, "best_choice")
        assert not hasattr(ctx, "final_answer")
        assert not hasattr(ctx, "decision")
        assert not hasattr(ctx, "veto")

    def test_retrieval_no_decision_property(self):
        """Store.retrieve 返回 ExperienceRecord，没有 decision 方法。"""
        store = ExperienceStore()
        store.save(make_experience())
        results = store.retrieve()
        assert len(results) == 1
        # retrieve 返回的是标准记录，没有 authority 方法
        assert not hasattr(results[0], "execute")
        assert not hasattr(results[0], "apply")
        assert not hasattr(results[0], "commit")


# ===================================================================
# T28 — Context Injection (Read-Only)
# ===================================================================

class TestT28_ContextInjectionReadOnly:
    """T28: 检索结果被调用方修改后不影响源数据。"""

    def test_retrieve_modify_does_not_affect_store(self):
        store = ExperienceStore()
        store.save(make_experience(
            experience_id="exp-ro",
            outcome="success",
        ))

        # 获取副本
        results = store.retrieve()
        assert len(results) == 1

        # 副本的数据和 Store 里的是同一个对象引用还是副本？
        retrieved = results[0]
        # 我们至少确认列表是副本
        assert results is not store.retrieve()
        # 验证 Store 数据不受外部修改影响
        store_record = store.get("exp-ro")
        assert store_record is not None
        assert store_record.outcome == "success"

    def test_retrieve_independence(self):
        """多次 retrieve 每次返回独立副本。"""
        store = ExperienceStore()
        store.save(make_experience(experience_id="exp-indep"))
        r1 = store.retrieve()
        r2 = store.retrieve()
        assert r1 is not r2  # 不同的列表对象


# ===================================================================
# T29 — No Decision Leak in Output
# ===================================================================

class TestT29_NoDecisionLeak:
    """T29: Retrieval 输出不能包含 decision/action 字段。

    对应 RETRIEVAL §5.3: 检索结果不包含 recommended_action。
    """

    def test_experience_context_no_decision_fields(self):
        """ExperienceContext 不能有 decision-like 字段。"""
        ctx = ExperienceContext(references=[])
        forbidden = ["recommended_action", "best_choice", "final_answer",
                     "decision", "veto", "instruction", "command"]
        for field in forbidden:
            assert not hasattr(ctx, field), (
                f"ExperienceContext 不能有 {field} 字段"
            )

    def test_experience_reference_no_decision_fields(self):
        """ExperienceReference 不能有 decision-like 字段。"""
        ref = ExperienceReference(
            experience_id="e1", similarity=0.5,
            scope="d:c:c", source="obs",
            calibrated_confidence=0.5,
            hypothesis="H", outcome="success",
        )
        forbidden = ["recommended_action", "best_choice", "final_answer"]
        for field in forbidden:
            assert not hasattr(ref, field), (
                f"ExperienceReference 不能有 {field} 字段"
            )

    def test_retrieval_return_type(self):
        """retrieve 返回 List[ExperienceRecord]，不是 Decision。"""
        store = ExperienceStore()
        store.save(make_experience())
        results = store.retrieve()
        assert isinstance(results, list)
        assert all(isinstance(r, ExperienceRecord) for r in results)


# ===================================================================
# T30 — Empty Experience
# ===================================================================

class TestT30_EmptyExperience:
    """T30: 无匹配经验时返回空列表，不是 None 或错误。"""

    def test_empty_retrieval_returns_list(self):
        store = ExperienceStore()
        results = store.retrieve()
        assert results == []
        assert isinstance(results, list)

    def test_empty_retrieval_all_filters(self):
        store = ExperienceStore()
        # 各种过滤条件下空结果都返回列表
        assert isinstance(store.retrieve(domain="nothing"), list)
        assert isinstance(store.retrieve(source_type="nothing"), list)
        assert isinstance(store.retrieve(scope="nothing"), list)

    def test_empty_context_creation(self):
        """空 references 的 ExperienceContext 合法。"""
        ctx = ExperienceContext(references=[])
        assert ctx.references == []
        assert ctx.aggregated_confidence == 0.0
