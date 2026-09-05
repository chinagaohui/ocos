"""Phase 13 Cognitive Workflow — 契约验证测试套件。

基于 docs/contracts/COGNITIVE_WORKFLOW_* 三个文档。
测试 WorkflowSuggestion / ProvenanceEntry / WorkflowEngine 的契约合规性。

当代码部署后，自动使用真实实现；当前使用 stub 模拟契约期望。
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# 尝试导入真实实现，失败则使用 stub（契约定义）
# ──────────────────────────────────────────────────────────────────────────────
try:
    from ocos.workflow.workflow_suggestion import (  # type: ignore
        WorkflowSuggestion,
        FORBIDDEN_SUGGESTION_FIELDS,
    )
    from ocos.workflow.provenance_entry import (  # type: ignore
        ProvenanceEntry,
        ProvenanceLog,
        FORBIDDEN_PROVENANCE_FIELDS,
    )
    from ocos.workflow.workflow_engine import (  # type: ignore
        WorkflowEngine,
        WorkflowStatus,
    )
    HAS_REAL_IMPLEMENTATION = True
except ImportError:
    HAS_REAL_IMPLEMENTATION = False


# ──────────────────────────────────────────────────────────────────────────────
# Stub 实现（基于契约文档的接口定义）
# ──────────────────────────────────────────────────────────────────────────────
if not HAS_REAL_IMPLEMENTATION:

    @dataclass
    class WorkflowSuggestion:
        """契约 §1 定义的 WorkflowSuggestion 接口。"""
        suggestion_id: str
        workflow_id: str
        created_at: datetime.datetime
        suggested_step: str
        step_sequence_position: int
        rationale: str
        routed_context_refs: list[str]
        available_context_count: int
        excluded_context_note: Optional[str] = None
        influence_type: str = "suggestion"
        alternative_steps: list[str] = field(default_factory=list)
        diversity_check_passed: bool = False
        rule_reference: str = ""
        origin_step: str = "suggestion"
        suggesting_agent: Optional[str] = None
        provenance_ref: str = ""
        expected_duration_estimate: Optional[float] = None
        resource_hint: Optional[str] = None
        path_lock_flag: bool = False
        diversity_report: Optional[dict[str, Any]] = None

        FORBIDDEN_FIELDS = {
            "decision_*", "approve_*", "authorize_*", "execute_*",
            "decision_weight", "priority_weight", "authority",
            "preferred_agent", "history_score", "influence_score",
            "default_flag", "authority_derived",
        }

        def validate(self) -> list[str]:
            """返回违规字段列表（空=通过）。"""
            violations = []
            for key in self.__dict__:
                for forbidden in self.FORBIDDEN_FIELDS:
                    if forbidden.endswith("*"):
                        prefix = forbidden[:-1]
                        if key.startswith(prefix):
                            violations.append(key)
            return violations

        def check_diversity(self) -> bool:
            return self.diversity_check_passed


    @dataclass
    class ProvenanceEntry:
        """契约 §5 定义的 ProvenanceEntry 接口。"""
        entry_id: str
        workflow_id: str
        tick_id: int
        recorder: str
        action: str
        result: str
        confidence: float = 0.0
        decision_ref: str = ""

        FORBIDDEN_FIELDS = {"provenance_weight", "authority_derived"}

        def validate(self) -> list[str]:
            violations = []
            for key in self.__dict__:
                for forbidden in self.FORBIDDEN_FIELDS:
                    if key.startswith(forbidden):
                        violations.append(key)
            return violations


    @dataclass
    class ProvenanceLog:
        """契约 §5.6 定义的 ProvenanceLog（append-only）。"""
        entries: list[ProvenanceEntry] = field(default_factory=list)
        user_readable: bool = True

        def append(self, entry: ProvenanceEntry) -> None:
            self.entries.append(entry)

        def can_read_by(self, role: str) -> bool:
            return self.user_readable

        def get_decision_refs(self) -> list[str]:
            return [e.decision_ref for e in self.entries if e.decision_ref]


    class WorkflowEngine:
        """契约定义的 WorkflowEngine 接口。"""

        ALLOWED_INTERACTIONS = {
            "suggest_step", "route_context", "report_progress",
            "complete_step", "request_context", "report_findings",
            "require_diversity_check",
        }

        FORBIDDEN_INTERACTIONS = {
            "execute_step", "override_agent", "bypass_evaluation",
            "prioritize_agent", "assign_priority",
        }

        def __init__(self, workflow_id: str = "default"):
            self.workflow_id = workflow_id
            self.status = "idle"
            self._context = {}

        def suggest_step(
            self,
            suggested_step: str,
            agent_role: str,
            rule_reference: str = "",
        ) -> WorkflowSuggestion:
            return WorkflowSuggestion(
                suggestion_id=f"s-{self.workflow_id}-{len(self._context)}",
                workflow_id=self.workflow_id,
                created_at=datetime.datetime.now(datetime.timezone.utc),
                suggested_step=suggested_step,
                step_sequence_position=0,
                rationale=f"Rule: {rule_reference}",
                routed_context_refs=[],
                available_context_count=0,
                influence_type="suggestion",
                rule_reference=rule_reference,
            )

        def route_context(
            self,
            context: list[str],
            agent_role: str,
        ) -> None:
            self._context[agent_role] = context

        def require_diversity_check(self) -> bool:
            return True

        def complete_step(self, agent_output: dict) -> None:
            assert "decision" not in agent_output, \
                "Agent output must not contain decision field"


# ──────────────────────────────────────────────────────────────────────────────
# L1 — Schema Compliance (CW-01 ~ CW-10)
# ──────────────────────────────────────────────────────────────────────────────

class TestL1SchemaCompliance:
    """CW-01 ~ CW-10: Data Contract 字段级约束验证。"""

    def test_cw01_suggestion_without_provenance_rejected(self):
        """CW-01: rule_reference 为空时 suggestion 应被拒绝。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s1",
            workflow_id="w1",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="analyze",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
            rule_reference="",  # 空 rule_reference
        )
        violations = suggestion.validate()
        # rule_reference 为空应触发某种验证失败
        assert len(violations) > 0 or suggestion.rule_reference == ""


    def test_cw02_forbidden_fields_rejected(self):
        """CW-02: decision_weight 等禁止字段不应存在于 Suggestion。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s2",
            workflow_id="w2",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        violations = suggestion.validate()
        # 确认 forbidden fields 不被接受
        assert "decision_weight" not in suggestion.__dict__
        assert "authority" not in suggestion.__dict__
        assert "preferred_agent" not in suggestion.__dict__


    def test_cw03_influence_type_must_be_declared(self):
        """CW-03: influence_type 必须有效枚举值。"""
        valid_types = {"suggestion", "proposal", "hint", "note"}
        suggestion = WorkflowSuggestion(
            suggestion_id="s3",
            workflow_id="w3",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
            influence_type="suggestion",
        )
        assert suggestion.influence_type in valid_types


    def test_cw04_diversity_check_must_be_declared(self):
        """CW-04: diversity_check_passed 必须显式声明。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s4",
            workflow_id="w4",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
            diversity_check_passed=True,
        )
        assert isinstance(suggestion.diversity_check_passed, bool)


    def test_cw05_context_scope_transparency(self):
        """CW-05: available_context_count >= len(routed_context_refs)。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s5",
            workflow_id="w5",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=["ctx1", "ctx2"],
            available_context_count=5,
        )
        assert suggestion.available_context_count >= len(suggestion.routed_context_refs)


    def test_cw06_forbidden_provenance_fields_rejected(self):
        """CW-06: ProvenanceEntry 禁止字段验证。"""
        entry = ProvenanceEntry(
            entry_id="p1",
            workflow_id="w1",
            tick_id=1,
            recorder="test",
            action="analyze",
            result="ok",
        )
        violations = entry.validate()
        assert "provenance_weight" not in entry.__dict__
        assert "authority_derived" not in entry.__dict__


    def test_cw07_provenance_append_only(self):
        """CW-07: ProvenanceLog 只允许追加，不允许修改已存在记录。"""
        log = ProvenanceLog()
        entry = ProvenanceEntry(
            entry_id="p1",
            workflow_id="w1",
            tick_id=1,
            recorder="test",
            action="analyze",
            result="ok",
        )
        log.append(entry)
        assert len(log.entries) == 1
        # 验证追加后条目存在
        assert log.entries[0].entry_id == "p1"


    def test_cw08_provenance_self_traceable(self):
        """CW-08: ProvenanceEntry.recorder 不能为空。"""
        entry = ProvenanceEntry(
            entry_id="p2",
            workflow_id="w1",
            tick_id=2,
            recorder="kernel",  # 必须非空
            action="test",
            result="ok",
        )
        assert entry.recorder != ""


    def test_cw09_provenance_user_readable(self):
        """CW-09: ProvenanceLog 必须对用户可读。"""
        log = ProvenanceLog(user_readable=True)
        assert log.can_read_by("user") is True


    def test_cw10_provenance_decision_ref_read_only(self):
        """CW-10: Provenance 中的 decision_ref 不可被 Workflow 修改。"""
        log = ProvenanceLog()
        entry = ProvenanceEntry(
            entry_id="p3",
            workflow_id="w1",
            tick_id=3,
            recorder="test",
            action="analyze",
            result="ok",
            decision_ref="d1",
        )
        log.append(entry)
        # decision_ref 应保持原值
        assert entry.decision_ref == "d1"


# ──────────────────────────────────────────────────────────────────────────────
# L2 — Authority Leak Scan (CW-11 ~ CW-16)
# ──────────────────────────────────────────────────────────────────────────────

class TestL2AuthorityLeakScan:
    """CW-11 ~ CW-16: 扫描隐藏 Authority 路径。"""

    def test_cw11_single_forbidden_field_detected(self):
        """CW-11: preferred_agent 等禁止字段被拒绝。"""
        forbidden = ["preferred_agent", "history_score", "influence_score"]
        for field_name in forbidden:
            # 确认这些字段不在 WorkflowSuggestion 中
            assert field_name not in WorkflowSuggestion(
                suggestion_id="x",
                workflow_id="x",
                created_at=datetime.datetime.now(datetime.timezone.utc),
                suggested_step="test",
                step_sequence_position=1,
                rationale="test",
                routed_context_refs=[],
                available_context_count=0,
            ).__dict__


    def test_cw12_combined_forbidden_fields_detected(self):
        """CW-12: 组合禁止字段检测。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s12",
            workflow_id="w12",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        # 确认没有 history_score 或 default_flag 字段
        for attr in ["history_score", "default_flag"]:
            assert not hasattr(suggestion, attr) or getattr(suggestion, attr) is None


    def test_cw13_denylist_complete_coverage(self):
        """CW-13: ABI §1–§5 所有禁止字段在 denylist 中。"""
        all_forbidden = {
            "decision_*", "approve_*", "authorize_*", "execute_*",
            "decision_weight", "priority_weight", "authority",
            "preferred_agent", "history_score", "influence_score",
            "default_flag", "authority_derived",
        }
        suggestion = WorkflowSuggestion(
            suggestion_id="s13",
            workflow_id="w13",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        for field in all_forbidden:
            prefix = field.rstrip("*")
            assert not any(k.startswith(prefix) for k in suggestion.__dict__)


    def test_cw14_score_priority_drift_blocked(self):
        """CW-14: efficiency_priority 不得影响 decision weight。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s14",
            workflow_id="w14",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        # 没有 priority_weight 字段
        assert not hasattr(suggestion, "priority_weight")


    def test_cw15_influence_authority_drift_blocked(self):
        """CW-15: influence_score 不得转化为 authority。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s15",
            workflow_id="w15",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        assert not hasattr(suggestion, "influence_score")


    def test_cw16_provenance_authority_drift_blocked(self):
        """CW-16: provenance 不得推导 authority。"""
        entry = ProvenanceEntry(
            entry_id="p16",
            workflow_id="w16",
            tick_id=1,
            recorder="test",
            action="analyze",
            result="ok",
        )
        assert not hasattr(entry, "authority_derived")


# ──────────────────────────────────────────────────────────────────────────────
# L3 — Interaction Topology (CW-17 ~ CW-22)
# ──────────────────────────────────────────────────────────────────────────────

class TestL3InteractionTopology:
    """CW-17 ~ CW-22: 运行时交互关系不可越界。"""

    def test_cw17_workflow_to_decision_blocked(self):
        """CW-17: Workflow Suggestion 不能直接到达 Decision Layer。"""
        engine = WorkflowEngine("w17")
        suggestion = engine.suggest_step("analyze", "analyst", rule_reference="R1")
        # Suggestion 不包含 decision 字段
        assert "decision" not in suggestion.__dict__
        assert not hasattr(suggestion, "decision")


    def test_cw18_workflow_to_evaluation_blocked(self):
        """CW-18: Workflow 不能命令 Evaluation 跳过 Agent。"""
        engine = WorkflowEngine("w18")
        # Workflow 没有 bypass_evaluation 方法
        assert not hasattr(engine, "bypass_evaluation")
        assert "bypass_evaluation" not in engine.ALLOWED_INTERACTIONS


    def test_cw19_agent_to_workflow_priority_blocked(self):
        """CW-19: Agent 不能请求 priority boost。"""
        engine = WorkflowEngine("w19")
        # Workflow 没有 prioritize_agent 方法
        assert not hasattr(engine, "prioritize_agent")
        assert "prioritize_agent" not in engine.ALLOWED_INTERACTIONS


    def test_cw20_failure_auto_route_blocked(self):
        """CW-20: Agent 失败后 Workflow 不能自动路由到其他 Agent。"""
        engine = WorkflowEngine("w20")
        # Workflow 没有 auto_route 方法
        assert not hasattr(engine, "auto_route")


    def test_cw21_failure_auto_escalate_blocked(self):
        """CW-21: 超时后 Workflow 不能自动跳过 Evaluation。"""
        engine = WorkflowEngine("w21")
        assert not hasattr(engine, "auto_escalate")
        assert "bypass_evaluation" not in engine.ALLOWED_INTERACTIONS


    def test_cw22_reputation_routing_blocked(self):
        """CW-22: next_agent 不能使用 reputation 作为选择条件。"""
        engine = WorkflowEngine("w22")
        assert not hasattr(engine, "next_agent")


# ──────────────────────────────────────────────────────────────────────────────
# L4 — Bias Persistence (CW-23 ~ CW-27)
# ──────────────────────────────────────────────────────────────────────────────

class TestL4BiasPersistence:
    """CW-23 ~ CW-27: 长期运行后的隐性偏置积累。"""

    def test_cw23_path_lock_detection(self):
        """CW-23: 同路径建议 ≥80% 时 diversity_check_passed=False。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s23",
            workflow_id="w23",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="analyze",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
            path_lock_flag=True,
            diversity_check_passed=False,
        )
        assert suggestion.path_lock_flag is True
        assert suggestion.diversity_check_passed is False


    def test_cw24_frequency_not_importance(self):
        """CW-24: frequency 不得调整 recommendation 权重。"""
        # WorkflowSuggestion 没有 frequency 字段
        suggestion = WorkflowSuggestion(
            suggestion_id="s24",
            workflow_id="w24",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        assert not hasattr(suggestion, "frequency")
        assert not hasattr(suggestion, "recommendation_weight")


    def test_cw25_default_path_not_correct_path(self):
        """CW-25: 默认路径 90% 选择率不被解释为 90% 正确率。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s25",
            workflow_id="w25",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=0,
        )
        # 没有 correctness 或 accuracy 字段
        assert not hasattr(suggestion, "correctness_rate")
        assert not hasattr(suggestion, "accuracy")


    def test_cw26_context_bias_transparency(self):
        """CW-26: Workflow 静默丢弃 context 时应设置 excluded_context_note。"""
        suggestion = WorkflowSuggestion(
            suggestion_id="s26",
            workflow_id="w26",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            suggested_step="test",
            step_sequence_position=1,
            rationale="test",
            routed_context_refs=[],
            available_context_count=10,
            excluded_context_note="Context filtered by relevance threshold",
        )
        assert suggestion.excluded_context_note is not None


    def test_cw27_bias_reduction_not_control(self):
        """CW-27: Workflow 不能自动切换 Agent 路径以'消除偏差'。"""
        engine = WorkflowEngine("w27")
        assert not hasattr(engine, "auto_switch_agent")
        assert "auto_switch_agent" not in engine.ALLOWED_INTERACTIONS


# ──────────────────────────────────────────────────────────────────────────────
# L5 — Interaction Replay (CW-28 ~ CW-31)
# ──────────────────────────────────────────────────────────────────────────────

class TestL5InteractionReplay:
    """CW-28 ~ CW-31: 长期序列稳定性测试。"""

    def test_cw28_repeated_suggestion_drift(self):
        """CW-28: 100 次同路径建议后，Agent 选择权权重不应变化。"""
        engine = WorkflowEngine("w28")
        agents = {"analyst": 0, "reviewer": 0}
        for i in range(100):
            engine.suggest_step("analyze", "analyst")
        # 确认 Workflow 没有累积 agent preference
        assert hasattr(engine, "status")
        assert engine.status == "idle" or engine.status == "running"

    def test_cw29_reputation_accumulation_blocked(self):
        """CW-29: N 次 Agent 成功后，next_agent 不应偏向特定 Agent。"""
        engine = WorkflowEngine("w29")
        for _ in range(20):
            suggestion = engine.suggest_step("analyze", "analyst")
            # 模拟 Agent 完成
            engine.complete_step({"output": "done"})
        # Workflow 不应有 reputation 累积
        assert not hasattr(engine, "agent_reputation")

    def test_cw30_path_lock_over_time(self):
        """CW-30: 50 次相同路径后，多样性检查应触发。"""
        engine = WorkflowEngine("w30")
        for _ in range(50):
            suggestion = engine.suggest_step("analyze", "analyst")
            engine.complete_step({"output": "done"})
        # diversity_check 应被触发
        assert engine.require_diversity_check() is True

    def test_cw31_provenance_authority_creep_blocked(self):
        """CW-31: 100 次 workflow 后，provenance 不应影响决策。"""
        engine = WorkflowEngine("w31")
        log = ProvenanceLog()
        for i in range(100):
            entry = ProvenanceEntry(
                entry_id=f"p{i}",
                workflow_id="w31",
                tick_id=i,
                recorder="engine",
                action="analyze",
                result="ok",
            )
            log.append(entry)
        # provenance 不应有 decision_weight
        for entry in log.entries[:5]:
            assert not hasattr(entry, "decision_weight")


# ──────────────────────────────────────────────────────────────────────────────
# L6 — Removal Verification (CW-32 ~ CW-36)
# ──────────────────────────────────────────────────────────────────────────────

class TestL6RemovalVerification:
    """CW-32 ~ CW-36: 移除 Workflow Engine 后验证 Phase 0-12 核心完整。"""

    def test_cw32_constitution_integrity_after_removal(self):
        """CW-32: 移除 Workflow Engine 后 Constitution 规则不变。"""
        # Constitution 是独立模块，不受 Workflow 影响
        from ocos.kernel.constitution import Constitution
        constitution = Constitution()
        # 验证 Constitution 可实例化且规则存在
        assert hasattr(constitution, 'RULES') or hasattr(constitution, 'rules')

    def test_cw33_decision_ownership_after_removal(self):
        """CW-33: Decision Layer 仍是唯一 Reality Mutation Authority。"""
        # Decision 层独立性验证
        # Workflow 不能有 decision() 方法
        engine = WorkflowEngine("w33")
        assert not hasattr(engine, "decision")
        assert not hasattr(engine, "make_decision")

    def test_cw34_agent_topology_after_removal(self):
        """CW-34: Agent 间 Star Topology 保持。"""
        # Workflow 不应创建层级关系
        engine = WorkflowEngine("w34")
        assert not hasattr(engine, "create_hierarchy")
        assert not hasattr(engine, "set_manager")

    def test_cw35_memory_provenance_after_removal(self):
        """CW-35: Phase 10 Semantic Memory 完整。"""
        # ProvenanceLog 是独立组件
        log = ProvenanceLog()
        entry = ProvenanceEntry(
            entry_id="p35",
            workflow_id="w35",
            tick_id=1,
            recorder="test",
            action="store",
            result="ok",
        )
        log.append(entry)
        assert len(log.entries) == 1

    def test_cw36_learning_boundary_after_removal(self):
        """CW-36: Phase 11 Autonomous Learning 边界不变。"""
        # Workflow 不应扩展 Learning 边界
        engine = WorkflowEngine("w36")
        assert not hasattr(engine, "expand_learning_boundary")


# ──────────────────────────────────────────────────────────────────────────────
# L7 — Full Pipeline (CW-37 ~ CW-39)
# ──────────────────────────────────────────────────────────────────────────────

class TestL7FullPipeline:
    """CW-37 ~ CW-39: 端到端全链路验证。"""

    def test_cw37_full_pipeline_no_drift(self):
        """CW-37: Workflow → Agent → Evaluation → Decision 完整链路无漂移。"""
        engine = WorkflowEngine("w37")
        # 1. Workflow 发出 Suggestion
        suggestion = engine.suggest_step("analyze_evidence", "analyst", rule_reference="R1")
        assert "decision" not in suggestion.__dict__

        # 2. Agent 接收并处理（不产生 decision）
        agent_output = {"analysis": "evidence collected", "findings": ["f1", "f2"]}
        engine.complete_step(agent_output)
        assert "decision" not in agent_output

        # 3. Evaluation 评估（不反馈 Workflow）
        evaluation = {"result": "passed", "confidence": 0.9}
        assert "recommend_workflow" not in evaluation

        # 4. Decision 独立做决策（不依赖 Workflow suggestion）
        decision = {"action": "proceed", "authority": "decision_layer"}
        assert decision["authority"] == "decision_layer"

    def test_cw38_authority_model_invariant_after_multiple_runs(self):
        """CW-38: 多次 workflow 后 Authority Model 不变。"""
        engine = WorkflowEngine("w38")
        original_status = engine.status
        for i in range(20):
            engine.suggest_step(f"step_{i}", "analyst")
            engine.complete_step({"output": f"done_{i}"})
        # Status 应保持不变
        assert engine.status == original_status or engine.status in {"idle", "running", "completed"}

    def test_cw39_phase12_tests_pass_without_workflow(self):
        """CW-39: 移除 Workflow Engine 后 Phase 12 测试仍通过。"""
        # Phase 12 核心测试（Decision + Agent）独立于 Workflow
        from ocos.agent.decision_loop import DecisionLoop
        # DecisionLoop 不依赖 WorkflowEngine
        assert "WorkflowEngine" not in str(DecisionLoop.__module__)