"""Process 数据模型测试。

对应 Phase 15 — Process Foundation 的 Process 数据模型。
覆盖：ProcessType, ProcessState, ProcessStep, TransformProcess。
"""

import pytest

from ocos.kernel.abi import SCHEMA_VERSION
from ocos.models.information import UniversalAddress
from ocos.models.process import (
    ProcessState,
    ProcessStep,
    ProcessType,
    TransformProcess,
)


class TestProcessType:
    """ProcessType 枚举的基本行为验证。"""

    def test_enum_values(self):
        assert ProcessType.REASONING.value == "reasoning"
        assert ProcessType.DECISION.value == "decision"
        assert ProcessType.PLANNING.value == "planning"
        assert ProcessType.SIMULATION.value == "simulation"
        assert ProcessType.LEARNING.value == "learning"

    def test_all_members_available(self):
        """验证所有 7 个 ProcessType 成员存在且可枚举。"""
        members = list(ProcessType)
        assert len(members) == 7
        assert ProcessType.REASONING in members
        assert ProcessType.DECISION in members


class TestProcessState:
    """ProcessState 枚举的基本行为验证。"""

    def test_enum_values(self):
        assert ProcessState.CREATED.value == "created"
        assert ProcessState.RUNNING.value == "running"
        assert ProcessState.COMPLETED.value == "completed"
        assert ProcessState.FAILED.value == "failed"


class TestProcessStep:
    """ProcessStep 数据模型的基本行为验证。"""

    def test_default_construction(self):
        step = ProcessStep()
        assert step.step_id != ""
        assert step.description == ""
        assert step.input_addresses == ()
        assert step.output_addresses == ()
        assert step.operation == ""
        assert step.confidence == 0.0

    def test_custom_construction(self):
        addr1 = UniversalAddress(namespace="info", type="observation", id="obs-001")
        addr2 = UniversalAddress(namespace="info", type="conclusion", id="con-001")
        step = ProcessStep(
            description="Infer from observation",
            input_addresses=(addr1,),
            output_addresses=(addr2,),
            operation="infer",
            confidence=0.85,
        )
        assert step.description == "Infer from observation"
        assert len(step.input_addresses) == 1
        assert step.input_addresses[0] == addr1
        assert len(step.output_addresses) == 1
        assert step.output_addresses[0] == addr2
        assert step.operation == "infer"
        assert step.confidence == 0.85

    def test_confidence_range(self):
        """confidence 必须在 [0.0, 1.0] 范围内。"""
        ProcessStep(confidence=0.0)
        ProcessStep(confidence=1.0)
        with pytest.raises(ValueError, match="confidence must be in"):
            ProcessStep(confidence=-0.1)
        with pytest.raises(ValueError, match="confidence must be in"):
            ProcessStep(confidence=1.1)


class TestTransformProcess:
    """TransformProcess 数据模型的基本行为验证。"""

    def test_default_construction(self):
        proc = TransformProcess()
        assert proc.process_id != ""
        assert proc.process_type == ProcessType.REASONING
        assert proc.process_state == ProcessState.CREATED
        assert proc.input_addresses == ()
        assert proc.output_addresses == ()
        assert proc.steps == ()
        assert proc.confidence == 0.0
        assert proc.metadata == {}
        assert proc.schema_version == SCHEMA_VERSION

    def test_custom_construction(self):
        addr1 = UniversalAddress(namespace="info", type="observation", id="obs-001")
        addr2 = UniversalAddress(namespace="info", type="knowledge", id="know-001")
        addr3 = UniversalAddress(namespace="info", type="conclusion", id="con-001")
        step = ProcessStep(
            description="Deductive inference",
            input_addresses=(addr1, addr2),
            output_addresses=(addr3,),
            operation="deduce",
            confidence=0.92,
        )
        proc = TransformProcess(
            process_type=ProcessType.REASONING,
            process_state=ProcessState.COMPLETED,
            input_addresses=(addr1, addr2),
            output_addresses=(addr3,),
            steps=(step,),
            confidence=0.92,
            metadata={"method": "deduction", "model": "default"},
        )
        assert proc.process_type == ProcessType.REASONING
        assert proc.process_state == ProcessState.COMPLETED
        assert len(proc.input_addresses) == 2
        assert len(proc.output_addresses) == 1
        assert len(proc.steps) == 1
        assert proc.steps[0].description == "Deductive inference"
        assert proc.confidence == 0.92
        assert proc.metadata["method"] == "deduction"

    def test_all_process_types(self):
        """验证所有 ProcessType 都可以构建 TransformProcess。"""
        for ptype in ProcessType:
            proc = TransformProcess(process_type=ptype)
            assert proc.process_type == ptype

    def test_all_process_states(self):
        """验证所有 ProcessState 都可以设置。"""
        for state in ProcessState:
            proc = TransformProcess(process_state=state)
            assert proc.process_state == state

    def test_confidence_range(self):
        """confidence 必须在 [0.0, 1.0] 范围内。"""
        TransformProcess(confidence=0.0)
        TransformProcess(confidence=1.0)
        with pytest.raises(ValueError, match="confidence must be in"):
            TransformProcess(confidence=-0.01)
        with pytest.raises(ValueError, match="confidence must be in"):
            TransformProcess(confidence=1.01)

    def test_frozen_and_immutable(self):
        """TransformProcess 必须不可变（frozen dataclass）。"""
        import dataclasses
        proc = TransformProcess()
        with pytest.raises(dataclasses.FrozenInstanceError):
            proc.process_type = ProcessType.DECISION  # type: ignore
        # metadata dict 是 mutable field，所以不要求 hashable

    def test_process_id_uniqueness(self):
        """每次构造应生成唯一的 process_id。"""
        p1 = TransformProcess()
        p2 = TransformProcess()
        assert p1.process_id != p2.process_id
