"""
ReasoningEngine — 推理能力引擎。

Phase 19 Capability Engines 的第一个能力引擎。

职责:
1. 执行推理操作（DEDUCTION, INDUCTION, ABDUCTION, ANALOGY 等）
2. 产生 ReasoningTrace 记录
3. 将推理结果通过 output_addresses 输出
4. 与 ProcessRuntimeEngine 协作 — REASONING Process 启动后调用本引擎

设计原则:
- 无状态：所有推理状态在 ReasoningTrace 中
- 被 ProcessRuntimeEngine 调用，不独立管理生命周期
- 输入输出通过 Information Address 交换
- 每个推理步骤记录前提、结论、操作、置信度
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessState, ProcessType, ProcessStep
from ocos.models.reasoning import (
    InferenceOperation,
    ReasoningStep,
    ReasoningTrace,
)
from ocos.runtime.context_manager import WorkingMemory

from ocos.logging import get_logger

_SOURCE = "reasoning_engine"

logger = get_logger(__name__)


class RuntimeResult:
    """推理引擎的通用结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
        output_addresses: tuple[str, ...] = (),
        steps: int = 0,
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id
        self.output_addresses = output_addresses
        self.steps = steps

    def __repr__(self) -> str:
        return (
            f"RuntimeResult(success={self.success}, trace_id={self.trace_id!r}, "
            f"process_id={self.process_id!r}, steps={self.steps})"
        )


# ── 推理规则注册表 ──────────────────────────────────────────────────────────
# 每个操作对应一个信息处理函数
# 可被引擎外部扩展

_INFERENCE_HANDLERS: dict[InferenceOperation, Callable] = {}


def register_inference_handler(
    operation: InferenceOperation,
    handler: Callable[[list[str], dict[str, Any]], list[str]],
) -> None:
    """注册自定义推理操作处理器。"""
    _INFERENCE_HANDLERS[operation] = handler


# ═══════════════════════════════════════════════════════════════════════════════
# ReasoningEngine
# ═══════════════════════════════════════════════════════════════════════════════

class ReasoningEngine:
    """推理引擎 — 为 ProcessType.REASONING 提供推理能力。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, ReasoningTrace] = {}
        logger.debug("__init__ completed", component="reasoning_engine")

    def __repr__(self) -> str:
        return f"ReasoningEngine(traces={len(self._traces)})"

    # ── 公共 API ─────────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        operation: str | None = None,
        premises: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """基于 TransformProcess 执行推理。

        Args:
            process: 待执行的 REASONING Process
            operation: 推理操作类型（覆盖 Process 的 type）
            premises: 补充前提（可选）

        Returns:
            RuntimeResult 包含 trace_id 和输出地址
        """
        logger.info("execute reasoning", extra=dict(
            process_id=process.process_id, operation=operation,
        ))
        if process.process_type != ProcessType.REASONING.value:
            return RuntimeResult(
                success=False,
                message=f"Not a REASONING process: {process.process_type}",
                process_id=process.process_id,
            )

        # 确定推理操作
        ops = self._resolve_operations(process, operation)
        if not ops:
            return RuntimeResult(
                success=False,
                message="No inference operation specified",
                process_id=process.process_id,
            )

        # 收集输入地址
        input_addrs = list(process.input_addresses)
        if input_addrs and not premises:
            premises = {"inputs": list(input_addrs)}

        # 执行各推理步骤
        reasoning_steps: list[ReasoningStep] = []
        output_addrs: list[str] = []
        total_confidence = 0.0
        errors: list[str] = []

        for idx, op in enumerate(ops):
            step, output_addr, err = self._execute_step(
                step_index=idx,
                operation=op,
                premises=premises,
                existing_outputs=output_addrs,
                process_id=process.process_id,
            )
            if step:
                reasoning_steps.append(step)
                if output_addr:
                    output_addrs.append(output_addr)
                total_confidence += step.confidence
            if err:
                errors.append(err)

        # 发布推理完成事件
        overall_conf = total_confidence / len(ops) if ops else 0.0
        trace = ReasoningTrace(
            process_id=process.process_id,
            steps=tuple(reasoning_steps),
            input_addresses=tuple(str(a) for a in input_addrs),
            output_addresses=tuple(output_addrs),
            overall_confidence=overall_conf,
            error="; ".join(errors) if errors else "",
        )
        self._traces[trace.trace_id] = trace

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "process_type": ProcessType.REASONING.value,
                "input_addresses": list(input_addrs),
                "trace_id": trace.trace_id,
            },
            source=_SOURCE,
        ))

        return RuntimeResult(
            success=not errors,
            message=f"Reasoning complete: {len(reasoning_steps)} steps"
                     + (f", errors: {errors}" if errors else ""),
            trace_id=trace.trace_id,
            process_id=process.process_id,
            output_addresses=tuple(output_addrs),
            steps=len(reasoning_steps),
        )

    def get_trace(self, trace_id: str) -> ReasoningTrace | None:
        """获取推理轨迹。"""
        return self._traces.get(trace_id)

    def list_traces(self) -> list[ReasoningTrace]:
        """列出所有推理轨迹。"""
        return list(self._traces.values())

    def clear_traces(self) -> None:
        """清空推理轨迹。"""
        self._traces.clear()

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _resolve_operations(
        self,
        process: TransformProcess,
        override: str | None,
    ) -> list[InferenceOperation]:
        """从 Process 的 steps 或 override 推断要执行的推理操作列表。"""
        if override:
            op = InferenceOperation(override)
            return [op]

        if process.steps:
            ops: list[InferenceOperation] = []
            for step in process.steps:
                try:
                    ops.append(InferenceOperation(step.operation))
                except ValueError:
                    pass  # 跳过未知操作
            return ops

        # 默认：演绎
        return [InferenceOperation.DEDUCTION]

    def _execute_step(
        self,
        step_index: int,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
        existing_outputs: list[str],
        process_id: str,
    ) -> tuple[ReasoningStep | None, str, str]:
        """执行单个推理步骤。

        Returns:
            (ReasoningStep | None, output_address, error)
        """
        # 检查自定义处理器
        if operation in _INFERENCE_HANDLERS:
            handler = _INFERENCE_HANDLERS[operation]
            try:
                outputs = handler(premises.get("inputs", []) if premises else [], premises or {})
                output_addr = f"addr:reasoning:{uuid.uuid4().hex}"
                step = ReasoningStep(
                    step_index=step_index,
                    operation=operation.value,
                    input_address=",".join(premises.get("inputs", [])) if premises else "",
                    output_address=output_addr,
                    premises=tuple(premises.get("inputs", [])) if premises else (),
                    conclusion=str(outputs),
                    confidence=0.9,
                    metadata={"handler": handler.__name__} if handler else {},
                )
                return step, output_addr, ""
            except Exception as e:
                return None, "", str(e)

        # 默认内置推理
        output_addr = f"addr:reasoning:{uuid.uuid4().hex}"
        conclusion = self._default_reason(operation, premises)
        step = ReasoningStep(
            step_index=step_index,
            operation=operation.value,
            input_address=",".join(premises.get("inputs", [])) if premises else "",
            output_address=output_addr,
            premises=tuple(premises.get("inputs", [])) if premises else (),
            conclusion=conclusion,
            confidence=self._default_confidence(operation),
        )
        return step, output_addr, ""

    def _default_reason(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ) -> str:
        """默认推理逻辑（纯结构化输出，无实际 LLM 调用）。"""
        inputs = premises.get("inputs", []) if premises else []
        input_desc = f"inputs: {inputs}" if inputs else "no explicit inputs"
        return f"[{operation.value}] from {input_desc} → conclusion (trace generated)"

    def _default_confidence(
        self,
        operation: InferenceOperation,
    ) -> float:
        """不同推理操作的默认置信度。"""
        return {
            InferenceOperation.DEDUCTION: 0.95,
            InferenceOperation.INDUCTION: 0.7,
            InferenceOperation.ABDUCTION: 0.6,
            InferenceOperation.ANALOGY: 0.75,
            InferenceOperation.ANALYSIS: 0.9,
            InferenceOperation.SYNTHESIS: 0.8,
            InferenceOperation.COMPARISON: 0.85,
            InferenceOperation.EVALUATION: 0.7,
        }.get(operation, 0.8)

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="reasoning_engine",
    name="Reasoning Engine",
    version="1.0.0",
    engine_class="ocos.engines.reasoning_engine.ReasoningEngine",
    capabilities=['reasoning'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
