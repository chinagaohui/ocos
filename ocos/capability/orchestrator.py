"""Phase 28: Capability Orchestrator (§4.4 #10)。

Freeze §9.8 — 能力编排层：连接 SelectionEngine → Provider 执行 → ResultUnderstanding 反馈闭环。

区别于 SkillGraphExecutor:
  - SkillGraphExecutor 通过 CognitiveBridge 硬编码路由 5 个认知能力
  - CapabilityOrchestrator 通过 SelectionEngine 动态选择 Provider，
    支持任意能力链编排 + 结果学习反馈

核心流程:
  1. dispatch(capability_id, input) → select_top → execute → learn
  2. chain([...]) → 顺序执行多能力，输出→输入管道
  3. 结果自动反馈到 ExperienceMemory + KnowledgeGraph
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 数据类型 ─────────────────────────────────────────────────────────────────


@dataclass
class OrchestrationResult:
    """编排执行结果。"""
    success: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_duration_ms: float = 0.0
    selected_providers: list[str] = field(default_factory=list)  # 实际使用的 Provider 列表

    @property
    def output(self) -> dict[str, Any]:
        """最后一个成功步骤的输出。"""
        for r in reversed(self.results):
            if r.get("success"):
                return r.get("output", {})
        return {}

    @property
    def last_output(self) -> Any:
        """最后一个成功步骤的原始输出值。"""
        for r in reversed(self.results):
            if r.get("success"):
                return r.get("raw_output")
        return None


@dataclass
class DispatchResult:
    """单次 dispatch 结果。"""
    success: bool
    capability_id: str
    provider_id: str
    output: Any
    error: str = ""
    duration_ms: float = 0.0
    selection_score: float = 0.0
    pipeline: dict[str, Any] = field(default_factory=dict)  # ResultUnderstandingLayer 管道结果


# ── CapabilityOrchestrator ───────────────────────────────────────────────────


class CapabilityOrchestrator:
    """能力编排器。

    将 SelectionEngine、Provider 注册表、ResultUnderstandingLayer
    整合为一个统一编排接口。

    用法:
        orch = CapabilityOrchestrator(
            selection_engine=engine,
            providers={"codex": codex_instance, "local_python": py_instance},
            result_layer=ResultUnderstandingLayer(exp, kg),
        )
        result = orch.dispatch("code_gen", {"action": "generate", "prompt": "..."})
        chain = orch.chain([
            {"capability_id": "code_gen", "input": {...}},
            {"capability_id": "code_review", "input_from": "prev"},
            {"capability_id": "test_gen", "input_from": "prev"},
        ])
    """

    def __init__(
        self,
        selection_engine: Any = None,  # SelectionEngine
        providers: dict[str, Any] | None = None,  # provider_id → callable
        result_layer: Any = None,  # ResultUnderstandingLayer
        *,
        auto_learn: bool = True,
        timeout: float = 30.0,
    ):
        from ocos.capability.selection_engine import SelectionEngine

        self._selection: SelectionEngine = selection_engine or SelectionEngine()
        self._providers: dict[str, Any] = providers or {}
        self._result_layer: Any = result_layer  # ResultUnderstandingLayer | None
        self._auto_learn = auto_learn
        self._timeout = timeout

        # 统计
        self._dispatch_count: int = 0
        self._error_count: int = 0
        self._chain_history: list[OrchestrationResult] = []

    # ── Provider 管理 ────────────────────────────────────────────────────

    def register_provider(self, provider_id: str, instance: Any) -> None:
        """注册 Provider 实例。"""
        self._providers[provider_id] = instance

    def unregister_provider(self, provider_id: str) -> None:
        """注销 Provider 实例。"""
        self._providers.pop(provider_id, None)

    @property
    def registered_providers(self) -> list[str]:
        return list(self._providers.keys())

    # ── 核心 dispatch ────────────────────────────────────────────────────

    def dispatch(
        self,
        capability_id: str,
        inputs: dict[str, Any] | None = None,
        *,
        task_type: str | None = None,
        preferred_protocol: str | None = None,
    ) -> DispatchResult:
        """单次能力分发：选最佳 Provider → 执行 → 学习。

        Args:
            capability_id: 能力 ID (e.g. "code_gen")
            inputs: 输入参数
            task_type: 任务类型（不指定则从 inputs 推断）
            preferred_protocol: 优先协议
        """
        inp = inputs or {}
        task = task_type or capability_id
        start = time.monotonic()

        # Step 1: Selection
        best = self._selection.select_top(
            task_type=task,
            capability_id=capability_id,
            preferred_protocol=preferred_protocol,
        )

        if best is None:
            self._dispatch_count += 1
            return DispatchResult(
                success=False,
                capability_id=capability_id,
                provider_id="",
                output=None,
                error=f"No provider found for {capability_id}/{task}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        selected_pid = best.provider_id

        # Step 2: Execute
        provider = self._providers.get(selected_pid)
        if provider is None:
            self._dispatch_count += 1
            return DispatchResult(
                success=False,
                capability_id=capability_id,
                provider_id=selected_pid,
                output=None,
                error=f"Provider '{selected_pid}' registered but instance not found",
                selection_score=best.score,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            raw_output = self._execute_provider(provider, inp)
            success = True
            error = ""
        except Exception as e:
            raw_output = None
            success = False
            error = str(e)
            self._error_count += 1

        duration_ms = (time.monotonic() - start) * 1000
        self._dispatch_count += 1

        # Step 3: Result Understanding pipeline
        pipeline: dict[str, Any] = {}
        if success and self._result_layer and self._auto_learn:
            try:
                processed = self._result_layer.process_result(
                    raw_output,
                    capability_id=capability_id,
                    provider_id=selected_pid,
                    outcome="success" if success else "failure",
                    duration_ms=duration_ms,
                    task_type=task,
                )
                pipeline = {
                    "validated": processed.validated,
                    "experience_stored": processed.experience_stored,
                    "kg_updated": processed.kg_updated,
                }
            except Exception as e:
                pipeline = {"error": str(e)}
                logger.warning("ResultUnderstanding pipeline failed: %s", e)

        return DispatchResult(
            success=success,
            capability_id=capability_id,
            provider_id=selected_pid,
            output=raw_output,
            error=error,
            duration_ms=duration_ms,
            selection_score=best.score,
            pipeline=pipeline,
        )

    def _execute_provider(self, provider: Any, inputs: dict[str, Any]) -> Any:
        """执行 Provider — 兼容多种接口。"""
        if hasattr(provider, "execute"):
            return provider.execute(**inputs)
        elif callable(provider):
            return provider(**inputs)
        else:
            raise TypeError(f"Provider is neither callable nor has execute()")

    # ── 链式编排 ─────────────────────────────────────────────────────────

    def chain(
        self,
        steps: list[dict[str, Any]],
        *,
        fallback: str = "abort",
    ) -> OrchestrationResult:
        """顺序执行多个能力，输出→输入管道连接。

        Args:
            steps: 步骤列表，每项:
                {
                    "capability_id": str,
                    "input": dict | None,      # 显式输入（覆盖管道值）
                    "input_from": "prev" | str,  # "prev" = 上一步输出, 或指定步骤名
                    "name": str | None,         # 步骤名（用于 input_from 引用）
                }
            fallback: "abort" | "skip" | "continue"

        Returns:
            OrchestrationResult
        """
        start = time.monotonic()
        results: list[dict[str, Any]] = []
        errors: list[str] = []
        selected: list[str] = []
        last_output: Any = None

        for i, step in enumerate(steps):
            capability_id = step.get("capability_id", "")
            step_name = step.get("name", f"step_{i}")
            input_from = step.get("input_from", "")

            # 确定输入
            if input_from == "prev":
                inputs = {"input": last_output} if last_output is not None else step.get("input", {})
            elif input_from and input_from != "prev":
                # 从命名步骤获取输出
                target = next((r for r in results if r.get("name") == input_from), None)
                if target:
                    inputs = {"input": target.get("raw_output")} if target.get("raw_output") is not None else step.get("input", {})
                else:
                    inputs = step.get("input", {})
            else:
                inputs = step.get("input", {})

            # dispatch
            r = self.dispatch(capability_id=capability_id, inputs=inputs)

            step_result = {
                "step": i,
                "name": step_name,
                "capability_id": capability_id,
                "provider_id": r.provider_id,
                "success": r.success,
                "output": r.output,
                "raw_output": r.output,
                "error": r.error,
                "duration_ms": r.duration_ms,
            }

            if r.selection_score > 0:
                selected.append(r.provider_id)

            if r.success:
                last_output = r.output
                results.append(step_result)
            else:
                errors.append(f"{step_name}: {r.error}")
                step_result["output"] = None
                step_result["raw_output"] = None
                results.append(step_result)

                if fallback == "abort":
                    break
                elif fallback == "skip":
                    continue
                # "continue" = 不管失败继续下一步

        orch_result = OrchestrationResult(
            success=len(errors) == 0,
            results=results,
            errors=errors,
            total_duration_ms=(time.monotonic() - start) * 1000,
            selected_providers=selected,
        )
        self._chain_history.append(orch_result)
        return orch_result

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """关闭资源。"""
        if hasattr(self._selection, "shutdown"):
            self._selection.shutdown()
        self._providers.clear()
        self._chain_history.clear()

    # ── stats ─────────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "dispatch_count": self._dispatch_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._dispatch_count, 1),
            "chain_count": len(self._chain_history),
            "registered_providers": len(self._providers),
        }
