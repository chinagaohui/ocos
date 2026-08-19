"""
M3 测试 — Knowledge Validator + Evolution Manager。
"""

import uuid

import pytest

from ocos.knowledge.knowledge_evolution import (
    EvolutionChangeType,
    EvolutionManager,
    EvolutionProposal,
    EvolutionProposalStatus,
)
from ocos.knowledge.knowledge_lifecycle import KnowledgeLifecycle
from ocos.knowledge.knowledge_ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)
from ocos.knowledge.knowledge_registry import KnowledgeRegistry
from ocos.knowledge.knowledge_validator import (
    DEFAULT_VALIDATION_RULES,
    KnowledgeValidator,
    ValidationReport,
    ValidationRule,
    ValidationResult,
    ValidationSeverity,
)
from ocos.knowledge.promotion_rules import PromotionRuleEngine


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# KnowledgeValidator 测试
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =


class TestValidatorDefaults:
    def test_validator_loads_default_rules(self):
        v = KnowledgeValidator()
        rules = v.get_rule_names()
        assert len(rules) >= 3
        assert "content_exists" in rules

    def test_valid_unit_passes(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"data": 42},
        )
        report = v.validate(u)
        assert not report.has_errors

    def test_empty_content_fails(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={},
        )
        report = v.validate(u)
        assert report.has_errors
        errors = report.errors
        assert any("content" in e.field for e in errors)

    def test_tags_format_is_warning_for_long_source(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
            source="x" * 200,
        )
        report = v.validate(u)
        assert not report.has_errors
        assert report.has_warnings

    def test_selective_rules(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        report = v.validate(u, rule_names=["level_status_valid"])
        assert not report.has_errors

    def test_nonexistent_rule_skipped(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        report = v.validate(u, rule_names=["nonexistent"])
        assert report.has_warnings

    def test_custom_rule(self):
        v = KnowledgeValidator()
        def custom_check(u, ctx):
            if "test_flag" not in u.content:
                return [
                    ValidationResult("content", ValidationSeverity.ERROR, "需要 test_flag")
                ]
            return []
        v.register_rule(ValidationRule("custom_test", "测试规则", custom_check))

        u1 = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        report = v.validate(u1, rule_names=["custom_test"])
        assert report.has_errors

        u2 = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"test_flag": True},
        )
        report2 = v.validate(u2, rule_names=["custom_test"])
        assert not report2.has_errors

    def test_validation_report_aggregation(self):
        v = KnowledgeValidator()
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={},
        )
        report = v.validate(u)
        assert report.has_errors
        assert len(report.errors) >= 1


# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
# EvolutionManager 测试
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =


@pytest.fixture
def evo_env():
    """创建完整的演进测试环境。"""
    registry = KnowledgeRegistry()
    registry._access_matrix.set_default_permissions("sensor")
    registry._access_matrix.set_default_permissions("governance")
    # governance 作为审核者，需对 PRINCIPLE 有写权限
    registry._access_matrix.set_permission("governance", KnowledgeLevel.PRINCIPLE, True, True)
    lifecycle = KnowledgeLifecycle(registry)
    validator = KnowledgeValidator()
    promotion = PromotionRuleEngine()
    promotion.load_default_policies()
    manager = EvolutionManager(registry, lifecycle, validator, promotion)
    # 测试模式 — 不需要审批
    manager.set_approval_required(False)
    return {
        "registry": registry,
        "lifecycle": lifecycle,
        "validator": validator,
        "promotion": promotion,
        "manager": manager,
    }


class TestEvolutionProposalCreation:
    def test_create_edit_proposal(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"old": "data"},
        )
        registry.register(u, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑内容",
            reason="数据更新",
            new_payload={"new": "data"},
        )
        assert ok is True
        # auto-approve 模式返回消息字符串
        assert isinstance(result, str)
        # 验证提案已 APPLIED
        prop = manager.get_proposal("EP-0001")
        assert prop is not None
        assert prop.change_type == EvolutionChangeType.EDIT
        assert prop.status == EvolutionProposalStatus.APPLIED

    def test_create_proposal_no_permission(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        # sensor 对 PATTERN 无写权限
        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="尝试编辑",
            reason="test",
            new_payload={"y": 2},
        )
        assert ok is False

    def test_create_elevate_proposal(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]
        promotion = evo_env["promotion"]

        # 给 sensor EVIDENCE 写权限
        registry._access_matrix.set_permission(
            "sensor", KnowledgeLevel.EVIDENCE, True, True
        )
        # 注册自定义提升策略
        from ocos.knowledge.promotion_rules import PromotionPolicy
        policy = PromotionPolicy(allowed_sources=["sensor"])
        promotion.register_policy(KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE, policy)

        # 创建并激活 OBSERVATION
        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
            content={"pattern": "repeated"},
        )
        registry.register(u, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.ELEVATE,
            target_ids=[u.unit_id],
            owner="sensor",
            description="提升到 Evidence",
            reason="重复出现 3 次",
            new_level=KnowledgeLevel.EVIDENCE,
        )
        assert ok is True
        # auto-approve 返回消息字符串
        assert isinstance(result, str)
        # 验证提案已执行
        prop = manager.get_proposal("EP-0001")
        assert prop is not None
        assert prop.status == EvolutionProposalStatus.APPLIED

        # 验证提升后的单元存在
        evidence_units = registry.get_by_level(KnowledgeLevel.EVIDENCE, requestor="sensor")
        assert len(evidence_units) >= 1

    def test_create_deprecate_proposal(self, evo_env):
        registry = evo_env["registry"]
        lifecycle = evo_env["lifecycle"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")
        # 激活
        lifecycle.change_status(u.unit_id, KnowledgeStatus.ACTIVE, "sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.DEPRECATE,
            target_ids=[u.unit_id],
            owner="sensor",
            description="废弃",
            reason="不再需要",
        )
        assert ok is True
        # auto-approve 返回消息字符串
        assert isinstance(result, str)

        # 验证提案已执行
        prop = manager.get_proposal("EP-0001")
        assert prop is not None
        assert prop.status == EvolutionProposalStatus.APPLIED

        # 验证状态已变更
        entry = registry.get(u.unit_id, requestor="sensor")
        assert entry is not None
        assert entry.unit.status == KnowledgeStatus.DEPRECATED

    def test_create_merge_proposal(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u1 = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
            content={"a": 1},
        )
        u2 = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
            content={"b": 2},
        )
        registry.register(u1, owner="sensor")
        registry.register(u2, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.MERGE,
            target_ids=[u1.unit_id, u2.unit_id],
            owner="sensor",
            description="合并",
            reason="合并同类项",
            new_payload={"a": 1, "b": 2, "summary": "merged"},
        )
        assert ok is True
        # auto-approve 返回消息字符串
        assert isinstance(result, str)
        prop = manager.get_proposal("EP-0001")
        assert prop is not None
        assert prop.status == EvolutionProposalStatus.APPLIED

    def test_create_split_proposal(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
            content={"big": "complex payload with multiple signals"},
        )
        registry.register(u, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.SPLIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="拆分",
            reason="内容过于庞大",
            new_payload={
                "parts": [
                    {"content": {"signal": "a"}},
                    {"content": {"signal": "b"}},
                ]
            },
        )
        assert ok is True
        # auto-approve 返回消息字符串
        assert isinstance(result, str)
        prop = manager.get_proposal("EP-0001")
        assert prop is not None
        assert prop.status == EvolutionProposalStatus.APPLIED


class TestEvolutionApprovalWorkflow:
    def test_full_approval_flow(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]
        manager.set_approval_required(True)

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑",
            reason="更新",
            new_payload={"x": 2},
        )
        assert ok is True
        prop = result
        assert prop.status == EvolutionProposalStatus.DRAFT

        # 提交审核
        ok, msg = manager.submit_review(prop.proposal_id)
        assert ok is True

        # 审批
        ok, msg = manager.approve(prop.proposal_id, "governance")
        assert ok is True

        # 执行
        ok, msg = manager.apply(prop.proposal_id, "governance")
        assert ok is True

        # 验证已更新
        entry = registry.get(u.unit_id, requestor="sensor")
        assert entry is not None
        assert entry.unit.content["x"] == 2

    def test_reject_proposal(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]
        manager.set_approval_required(True)

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        ok, result = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑",
            reason="更新",
            new_payload={"x": 2},
        )
        assert ok is True
        prop = result

        # 提交审核 -> 驳回
        manager.submit_review(prop.proposal_id)
        ok, msg = manager.reject(prop.proposal_id, "governance", "不符合规范")
        assert ok is True

        prop2 = manager.get_proposal(prop.proposal_id)
        assert prop2.status == EvolutionProposalStatus.REJECTED
        assert prop2.rejection_reason == "不符合规范"

        # 内容不变
        entry = registry.get(u.unit_id, requestor="sensor")
        assert entry.unit.content["x"] == 1

    def test_list_proposals(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        for i in range(3):
            manager.create_proposal(
                change_type=EvolutionChangeType.EDIT,
                target_ids=[u.unit_id],
                owner="sensor",
                description=f"编辑 {i}",
                reason="更新",
                new_payload={"x": i},
            )

        proposals = manager.list_proposals(owner="sensor")
        assert len(proposals) == 3

        # 按状态统计
        counts = manager.count_by_status()
        assert "applied" in counts
        assert counts["applied"] == 3

    def test_get_all_proposals(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑",
            reason="更新",
            new_payload={"x": 2},
        )
        all_props = manager.list_proposals()
        assert len(all_props) >= 1


class TestEvolutionErrorCases:
    def test_apply_not_approved(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]
        manager.set_approval_required(True)

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        ok, prop = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑",
            reason="更新",
            new_payload={"x": 2},
        )
        assert ok is True

        # 未审批直接 apply
        ok, msg = manager.apply(prop.proposal_id, "sensor")
        assert ok is False
        assert "APPROVED" in msg

    def test_nonexistent_proposal(self, evo_env):
        manager = evo_env["manager"]
        ok, msg = manager.approve("NONEXISTENT", "governance")
        assert ok is False

    def test_double_submit_review(self, evo_env):
        registry = evo_env["registry"]
        manager = evo_env["manager"]
        manager.set_approval_required(True)

        u = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content={"x": 1},
        )
        registry.register(u, owner="sensor")

        ok, prop = manager.create_proposal(
            change_type=EvolutionChangeType.EDIT,
            target_ids=[u.unit_id],
            owner="sensor",
            description="编辑",
            reason="更新",
            new_payload={"x": 2},
        )

        manager.submit_review(prop.proposal_id)
        ok, msg = manager.submit_review(prop.proposal_id)
        assert ok is False  # 已经是 REVIEW 状态
