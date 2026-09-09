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
    """推理引擎 — 为 ProcessType.REASONING 提供推理能力。

    L1 真实化（升级方案）:
      - _real_reason:      episode 证据检索（记忆前提）+ LLM 推理，
                           结论携带 evidence[]（episode id）可追溯
      - _fallback_reason:  确定性结构化输出（LLM/记忆不可用时降级，
                           诚实标注 degraded）
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        memory_store: Any | None = None,
        text_generator: Any | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, ReasoningTrace] = {}
        # L1: 可选注入 — 缺省时懒加载（生产路径 get_text_generator 缓存）
        self._memory_store = memory_store
        self._text_generator = text_generator
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

        # 默认内置推理 — L1 真实化: 真分支优先，降级保留诚实标注
        output_addr = f"addr:reasoning:{uuid.uuid4().hex}"
        conclusion, evidence_ids, degraded = self._reason(
            operation, premises)
        step = ReasoningStep(
            step_index=step_index,
            operation=operation.value,
            input_address=",".join(premises.get("inputs", [])) if premises else "",
            output_address=output_addr,
            premises=tuple(premises.get("inputs", [])) if premises else (),
            conclusion=conclusion,
            confidence=self._default_confidence(operation)
            if not degraded else min(0.5, self._default_confidence(operation)),
            metadata={"evidence": evidence_ids, "degraded": degraded},
        )
        return step, output_addr, ""

    # ── L1 真实化: 统一入口 _reason → _real/_fallback ───────────────────

    def _reason(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ) -> tuple[str, list[str], bool]:
        """符号推理优先 → LLM 推理 → 确定性降级。

        PHASE-LIFE: 先跑 SymbolicReasoner（零 LLM），confidence 够高时
        直接用其结论、**跳过 LLM 调用**。不够时把 symbolic prediction
        作为 prior 上下文注入 LLM prompt。
        """
        # Step 1: SymbolicReasoner（零 LLM）
        sym_prior = self._symbolic_predict(operation, premises)
        if sym_prior and sym_prior.verdict == "symbolic_skip_llm":
            # OCOS 自己想清楚了 → 跳过 LLM
            conclusion = self._format_symbolic_conclusion(sym_prior)
            logger.info(
                "PHASE-LIFE: symbolic-only reasoning "
                "(conf=%.2f succ=%.2f, source_count=%d)",
                sym_prior.confidence, sym_prior.expected_success,
                sym_prior.source_count,
            )
            return (conclusion, [], False)

        # Step 2: LLM（可能注入 symbolic prior）
        try:
            if sym_prior:
                # 把 symbolic prediction 作为 prior 上下文传给 _real_reason
                enhanced_premises = dict(premises or {})
                enhanced_premises["_symbolic_prior"] = sym_prior.to_dict()
                return self._real_reason(operation, enhanced_premises)
            return self._real_reason(operation, premises)
        except Exception as e:
            logger.warning("real reasoning unavailable, degraded: %s", e)
            conclusion = self._fallback_reason(operation, premises)
            return (conclusion, [], True)

    # ── PHASE-LIFE: SymbolicReasoner 接入 ─────────────────────────────────

    def _symbolic_predict(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ):
        """懒加载 SymbolicReasoner 做符号预测。失败返回 None（不阻塞 LLM 路径）。"""
        try:
            from ocos.reasoning.symbolic import SymbolicReasoner

            # 任务描述：优先从 operation，退化到 premises
            task_text = (
                getattr(operation, "goal", None)
                or getattr(operation, "input_text", None)
                or (premises or {}).get("goal", "")
                or (premises or {}).get("task", "")
                or ""
            )
            if not task_text:
                return None

            agent_type = (
                (premises or {}).get("agent_type")
                or (premises or {}).get("agent")
            )

            sr = SymbolicReasoner()
            return sr.predict(str(task_text), agent_type)
        except Exception as e:
            logger.debug("SymbolicReasoner unavailable: %s", e)
            return None

    @staticmethod
    def _format_symbolic_conclusion(pred) -> str:
        """SymbolicPrediction → 自然语言结论（零 LLM）。"""
        succ_pct = round(pred.expected_success * 100)
        lines = [
            f"[符号推理] 预期成功率 {succ_pct}%（置信度 {round(pred.confidence * 100)}%）",
        ]
        if pred.suggested_procedure:
            lines.append(f"💡 建议程序：{pred.suggested_procedure}")
        if pred.similar_experiences:
            lines.append("相似历史：")
            for s in pred.similar_experiences[:3]:
                succ_mark = "✓" if s.get("success") else "✗"
                lines.append(f"  [{succ_mark}] {s.get('goal', '')[:60]}")
        return "\n".join(lines)

    def _retrieve_evidence(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
        limit: int = 5,
    ) -> list[tuple[str, str]]:
        """episode 证据检索 — 推理前提来自真实记忆而非凭空。

        Returns:
            [(episode_id, 摘要文本), ...]
        """
        if self._memory_store is None:
            return []
        keywords = self._premise_keywords(operation, premises)
        episodes = self._memory_store.query_by_time(limit=30)
        scored: list[tuple[int, str, str]] = []
        for ep in episodes:
            text = " ".join(filter(None, (
                getattr(ep, "goal", "") or "",
                getattr(ep, "decision", "") or "",
                getattr(ep, "action", "") or "",
            )))
            hits = sum(1 for kw in keywords if kw and kw in text)
            if hits:
                scored.append((hits, getattr(ep, "id", ""), text[:200]))
        scored.sort(key=lambda x: -x[0])
        return [(eid, text) for _, eid, text in scored[:limit]]

    @staticmethod
    def _premise_keywords(
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ) -> list[str]:
        """从前提提取检索关键词（地址型前提剥离协议前缀）。"""
        inputs = (premises or {}).get("inputs", []) or []
        keywords: list[str] = []
        for item in inputs:
            if not isinstance(item, str):
                keywords.append(str(item))
                continue
            # addr:goal:xxx / 自由文本 均取尾部语义段
            tail = item.split(":")[-1].strip()
            if tail and len(tail) >= 2:
                keywords.append(tail)
        return keywords[:8]

    def _real_reason(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ) -> tuple[str, list[str], bool]:
        """真推理 — episode 证据作为前提 + LLM 推理。

        Raises:
            Exception: LLM 不可用/调用失败（调用方 _reason 统一降级）
        """
        import asyncio

        if self._text_generator is None:
            from ocos.engines.text_generator import get_text_generator
            self._text_generator = get_text_generator()
        provider = self._text_generator.provider
        if not getattr(provider, "available", False):
            raise RuntimeError("LLM provider unavailable")

        evidence = self._retrieve_evidence(operation, premises)
        evidence_block = "\n".join(
            f"- [{eid}] {text}" for eid, text in evidence
        ) or "（无相关记忆条目）"
        inputs = (premises or {}).get("inputs", []) or []
        prompt = (
            f"推理操作: {operation.value}\n"
            f"前提: {inputs}\n"
            f"相关经验证据（来自记忆库）:\n{evidence_block}\n\n"
            "基于以上前提与证据进行推理，输出结论。要求：结论必须引用"
            "至少一条真实证据编号（格式 [EPI-...]），不得虚构。"
        )
        text = asyncio.run(provider.generate(
            prompt,
            system_prompt="你是 OCOS 的推理引擎。只输出结论本身，简洁、可追溯。",
            temperature=0.2, max_tokens=800))
        conclusion = (text or "").strip()
        if not conclusion:
            raise RuntimeError("empty LLM conclusion")
        evidence_ids = [eid for eid, _ in evidence]
        return conclusion, evidence_ids, False

    def _fallback_reason(
        self,
        operation: InferenceOperation,
        premises: dict[str, Any] | None,
    ) -> str:
        """降级推理 — 确定性结构化输出（诚实标注降级）。"""
        inputs = premises.get("inputs", []) if premises else []
        input_desc = f"inputs: {inputs}" if inputs else "no explicit inputs"
        return (f"[degraded:{operation.value}] from {input_desc} → "
                "conclusion (trace generated, LLM unavailable)")

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
