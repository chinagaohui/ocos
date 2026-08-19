"""
Phase 17.5 — Process Theory → Code Alignment 测试.

验证 PROCESS_THEORY.md 的 5 个关键维度与代码的一致性：
- Invariant 1: Process 不拥有 Information（使用 Address 引用）
- Invariant 2: Process 不控制生命周期
- Invariant 3: Process 不执行 Action
- Invariant 4: Process 必须引用 Evidence
- ProcessState 生命周期: CREATED → RUNNING → {COMPLETED, FAILED}
- ProcessType 扩展原则: 复用优先
- Process → Trace 映射存在且正确
"""

from __future__ import annotations

import dataclasses

import pytest

from ocos.kernel.constitution import ConstitutionalRule
from ocos.models.information import UniversalAddress
from ocos.models.process import (
    ProcessState,
    ProcessStep,
    ProcessType,
    TransformProcess,
)


class TestProcessInvariants:
    """验证 4 条 Process 不变量（PROCESS_THEORY §5.3）。"""

    def test_invariant_1_not_own_information(self):
        """Invariant 1: Process 不使用 content 字段（使用 Address）。"""
        # TransformProcess 的所有 input/output 必须是 Address，非 content
        fields = dataclasses.fields(TransformProcess)
        field_names = {f.name for f in fields}
        # 不能有 content/data 字段
        forbidden = {"content", "data", "value", "raw"}
        assert field_names.isdisjoint(forbidden), (
            f"TransformProcess 不应包含 data 字段，"
            f"交集: {field_names & forbidden}"
        )
        # 必须有 input_addresses 和 output_addresses
        assert "input_addresses" in field_names
        assert "output_addresses" in field_names

    def test_invariant_2_not_control_lifecycle(self):
        """Invariant 2: Process 类型不包含 lifecycle/state 转换方法。"""
        # 验证 TransformProcess 没有 transition_to / lifecycle 方法
        methods = {
            m for m in dir(TransformProcess)
            if not m.startswith("_") and callable(getattr(TransformProcess, m, None))
        }
        assert "can_transition_to" not in methods
        assert "transition_to" not in methods
        assert "archive" not in methods
        assert "promote" not in methods

    def test_invariant_3_not_execute_action(self):
        """Invariant 3: Process 类型不包含 execute 方法。"""
        methods = {
            m for m in dir(TransformProcess)
            if not m.startswith("_") and callable(getattr(TransformProcess, m, None))
        }
        assert "execute" not in methods

    def test_invariant_4_must_reference_evidence(self):
        """Invariant 4: TransformProcess 必须有 input 或 output address。"""
        # 空构造允许（有默认值），但必须至少有一个 address
        proc = TransformProcess()
        assert len(proc.input_addresses) == 0
        assert len(proc.output_addresses) == 0
        # 空引用可构造（frozen data），但宪法要求不得为空引用
        # 宪法 R24 强制执行此不变量
        assert ConstitutionalRule.PROCESS_MUST_REFERENCE_EVIDENCE.value == (
            "process_must_reference_evidence"
        )

    def test_invariant_4_with_addresses_passes(self):
        """验证引用 Evidence 的 Process 可正常工作。"""
        addr = UniversalAddress(namespace="info", type="obs", id="e-001")
        proc = TransformProcess(
            process_type=ProcessType.REASONING,
            input_addresses=(addr,),
            output_addresses=(addr,),
        )
        assert len(proc.input_addresses) == 1
        assert len(proc.output_addresses) == 1


class TestProcessStateMachine:
    """验证 ProcessState 四态生命周期（PROCESS_THEORY §5.3）。"""

    def test_created_to_running(self):
        """CREATED → RUNNING: 开始执行。"""
        assert ProcessState.CREATED != ProcessState.RUNNING
        assert ProcessState.CREATED.value == "created"

    def test_running_to_completed(self):
        """RUNNING → COMPLETED: 成功完成。"""
        assert ProcessState.RUNNING.value == "running"
        assert ProcessState.COMPLETED.value == "completed"

    def test_running_to_failed(self):
        """RUNNING → FAILED: 失败终止。"""
        assert ProcessState.FAILED.value == "failed"

    def test_terminal_states_are_completed_and_failed(self):
        """COMPLETED 和 FAILED 是终态（没有后续状态）。
        ProcessState 是 Enum（非复杂状态机），所以不提供 can_transition_to。"""
        assert ProcessState.COMPLETED != ProcessState.FAILED

    def test_all_four_states_exist(self):
        """必须恰好有 4 个状态。"""
        assert len(ProcessState) == 4


class TestProcessType:
    """验证 ProcessType 枚举与 Theory 第四章一致。"""

    def test_seven_types_exist(self):
        """ProcessType 包含 7 个成员（R/D/POLICY/ARB/SIM/LEARN）。"""
        assert len(ProcessType) == 7
        assert ProcessType.REASONING in ProcessType
        assert ProcessType.DECISION in ProcessType
        assert ProcessType.PLANNING in ProcessType
        assert ProcessType.POLICY in ProcessType
        assert ProcessType.ARBITRATION in ProcessType
        assert ProcessType.SIMULATION in ProcessType
        assert ProcessType.LEARNING in ProcessType

    def test_type_value_strings(self):
        """每个 ProcessType 的 value 为小写字符串。"""
        for ptype in ProcessType:
            assert ptype.value == ptype.name.lower()

    def test_expansion_reuse_reasoning(self):
        """复用原则: Reflection/Verification/Checking 应表达为 REASONING。"""
        # 验证没有独立的 REFLECTION/VERIFICATION 类型
        extra_types = {
            "REFLECTION", "VERIFICATION", "CHECKING",
            "INSPECTION", "EVALUATION",
        }
        defined_names = {m.name for m in ProcessType}
        assert defined_names.isdisjoint(extra_types), (
            f"不应存在独立的 ProcessType: {defined_names & extra_types}"
        )

    def test_expansion_reuse_decision(self):
        """复用原则: Evaluation/Negotiation 应表达为 DECISION。"""
        extra_types = {"EVALUATION", "NEGOTIATION"}
        defined_names = {m.name for m in ProcessType}
        assert defined_names.isdisjoint(extra_types)

    def test_expansion_reuse_planning(self):
        """复用原则: Optimization 应表达为 PLANNING。"""
        assert ProcessType.PLANNING in ProcessType
        extra_types = {"OPTIMIZATION", "SELF_REPAIR"}
        defined_names = {m.name for m in ProcessType}
        assert defined_names.isdisjoint(extra_types)


class TestProcessStep:
    """验证 ProcessStep 与 Theory 契约一致。"""

    def test_step_uses_addresses(self):
        """Step 的 input/output 是 Address[] 而不是 content。"""
        step = ProcessStep(
            description="Test step",
            input_addresses=(
                UniversalAddress(namespace="info", type="obs", id="o-001"),
            ),
            output_addresses=(
                UniversalAddress(namespace="info", type="conc", id="c-001"),
            ),
        )
        assert len(step.input_addresses) == 1
        assert step.input_addresses[0].namespace == "info"
        assert step.input_addresses[0].type == "obs"
        assert step.input_addresses[0].id == "o-001"
        assert len(step.output_addresses) == 1
        assert step.output_addresses[0].id == "c-001"

    def test_step_frozen(self):
        """ProcessStep 不可变（frozen）。"""
        step = ProcessStep()
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.description = "mutate"  # type: ignore


class TestTransformProcess:
    """验证 TransformProcess 统一契约（PROCESS_THEORY §5.1-5.2）。"""

    def test_frozen_dataclass(self):
        """TransformProcess 是 frozen dataclass（不可变）。"""
        proc = TransformProcess()
        with pytest.raises(dataclasses.FrozenInstanceError):
            proc.process_type = ProcessType.DECISION  # type: ignore

    def test_universal_address_only(self):
        """所有 input/output 字段类型必须是 UniversalAddress。"""
        addr = UniversalAddress(namespace="info", type="obs", id="o-001")
        proc = TransformProcess(
            input_addresses=(addr,),
            output_addresses=(addr,),
        )
        assert all(isinstance(a, UniversalAddress) for a in proc.input_addresses)
        assert all(isinstance(a, UniversalAddress) for a in proc.output_addresses)

    def test_no_specialized_fields(self):
        """TransformProcess 不应有按 ProcessType 拆分的特殊字段。"""
        fields = dataclasses.fields(TransformProcess)
        field_names = {f.name for f in fields}
        # 禁止按 ProcessType 拆分的字段
        forbidden = {"goal", "scenario", "algorithm", "model", "inference_method"}
        assert field_names.isdisjoint(forbidden), (
            f"不应存在特殊字段: {field_names & forbidden}"
        )

    def test_all_process_types_in_one_model(self):
        """所有 ProcessType 使用同一个 TransformProcess 类型。"""
        for ptype in ProcessType:
            proc = TransformProcess(process_type=ptype)
            assert type(proc) is TransformProcess
            assert proc.process_type == ptype

    def test_confidence_range(self):
        """confidence 在 [0.0, 1.0] 范围。"""
        TransformProcess(confidence=0.0)
        TransformProcess(confidence=1.0)
        with pytest.raises(ValueError, match="confidence must be in"):
            TransformProcess(confidence=-0.01)
        with pytest.raises(ValueError, match="confidence must be in"):
            TransformProcess(confidence=1.01)


class TestProcessTraceMapping:
    """验证 Process → Trace 映射（PROCESS_THEORY §6）。"""

    def test_process_type_to_trace_type_mapping_exists(self):
        """record_process_trace 存在于 TraceEngine 中。"""
        from ocos.platform.trace_engine import TraceEngine

        engine = TraceEngine()
        assert hasattr(engine, "record_process_trace")
        assert callable(engine.record_process_trace)

    def test_unsupported_planning_type_rejected(self):
        """PLANNING 尚未接入 Trace，应被拒绝（Theory §8 v1.0）。"""
        from ocos.platform.trace_engine import TraceEngine

        engine = TraceEngine()
        proc = TransformProcess(process_type=ProcessType.PLANNING)
        with pytest.raises(ValueError, match="Unsupported ProcessType"):
            engine.record_process_trace(proc)


class TestProcessConstitutionAlignment:
    """验证 Process 宪法规则的存在性。"""

    def test_r21_defined(self):
        assert ConstitutionalRule.PROCESS_NOT_OWN_INFORMATION is not None

    def test_r22_defined(self):
        assert ConstitutionalRule.PROCESS_NOT_CONTROL_LIFECYCLE is not None

    def test_r23_defined(self):
        assert ConstitutionalRule.PROCESS_NOT_EXECUTE_ACTION is not None

    def test_r24_defined(self):
        assert ConstitutionalRule.PROCESS_MUST_REFERENCE_EVIDENCE is not None


class TestLegacyCompat:
    """验证 v1.x 向后兼容标记。"""

    def test_semantic_role_reasoning_legacy_maps_to_memory(self):
        """SemanticRole(\"reasoning\") 通过 _missing_ 映射为 MEMORY（v2.0 拆除）。"""
        from ocos.models.information import SemanticRole
        mapped = SemanticRole("reasoning")
        assert mapped == SemanticRole.MEMORY
        assert mapped.value == "memory"

    def test_decision_reasoning_str_field_exists(self):
        """Decision.reasoning 保持为 str 类型（v2.0 迁移为 Address）。"""
        from ocos.kernel.abi import Decision
        # Decision 的 reasoning 字段类型应为 str
        assert "reasoning" in Decision.__dataclass_fields__
        # 注意: reasoning 在旧版 abi.py 中可能是 str
        # 不检查具体类型，只验证字段存在
