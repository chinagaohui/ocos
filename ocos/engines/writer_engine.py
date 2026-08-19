"""WriterEngine — 叙事写作引擎。

Phase 27 — OpenTale 叙事引擎集成。

职责:
1. 接受 Narrative Contract 参数，生成章节规划/内容
2. opentale 可用时委托给 AutonomousNovelSystem
3. 不可用时生成结构化占位内容
4. 产出 WriterTrace 记录
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessState
from ocos.runtime.context_manager import WorkingMemory
from ocos.agent.retry_policy import safe_execute, CircuitBreakerState, RetryPolicy, CircuitBreakerOpenError
from ocos.engines.narrative_pipeline import derive_policy, apply_budget_constraints
from ocos.engines.text_generator import TextGenerator

from ocos.logging import get_logger

logger = get_logger(__name__)


class RuntimeResult:
    """WriterEngine 的通用结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
        count: int = 0,
        output_addresses: tuple[str, ...] = (),
        content: Optional[list[dict[str, Any]]] = None,
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id
        self.count = count
        self.output_addresses = output_addresses
        self.content = content or []

    def __repr__(self) -> str:
        return (
            f"RuntimeResult(success={self.success}, trace_id={self.trace_id!r}, "
            f"process_id={self.process_id!r}, count={self.count})"
        )


# ── WriterTrace：记录每次写作操作 ───────────────────────────────


class WriterTrace:
    """写作操作的完整记录。"""
    def __init__(
        self,
        trace_id: str,
        process_id: str,
        strategy: str,
        genre: str,
        chapter_count: int,
        started_at: float,
        completed_at: float,
        success: bool,
        error: str = "",
    ):
        self.trace_id = trace_id
        self.process_id = process_id
        self.strategy = strategy
        self.genre = genre
        self.chapter_count = chapter_count
        self.started_at = started_at
        self.completed_at = completed_at
        self.duration = completed_at - started_at
        self.success = success
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "process_id": self.process_id,
            "strategy": self.strategy,
            "genre": self.genre,
            "chapter_count": self.chapter_count,
            "duration": round(self.duration, 3),
            "success": self.success,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════
# WriterEngine
# ═══════════════════════════════════════════════════════════════


class WriterEngine:
    """叙事写作引擎 — 为 narrative 场景提供写作/规划能力。

    支持策略:
      - plan:     从 Narrative Contract 生成章节大纲
      - generate: 生成完整章节内容（需 opentale 可用）
      - resume:   从检查点续写
      - rewrite:  重写指定章节
      - status:   当前写作状态
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, WriterTrace] = {}
        self._cb_state = CircuitBreakerState()
        self._retry_policy = RetryPolicy(max_retries=2, base_delay=0.5)
        self._text_generator = TextGenerator()  # auto-selects mock when no API key
        self._generation_state: dict[str, Any] = {
            "genre": "",
            "status": "idle",
            "chapter_count": 0,
            "last_operation": None,
            "error": "",
        }

        # 尝试导入 OpenTale（外部依赖，可能不可用或不可运行）
        self._opentale_available = False
        self._opentale_system = None
        self._opentale_init_error = ""
        self._init_opentale()
        logger.debug("__init__ completed", component="writer_engine")

    def _init_opentale(self) -> None:
        """检查 OpenTale 是否可用（仅导入检查，不初始化 LLM 运行时）。"""
        try:
            import opentale  # noqa: F401
            self._opentale_available = True
            logger.info("WriterEngine: opentale package found, available for delegation.")
        except ImportError:
            self._opentale_available = False
            self._opentale_init_error = "opentale package not installed"
            logger.info("WriterEngine: opentale not available, using plan-based generation.")
        except Exception as e:
            self._opentale_available = False
            self._opentale_init_error = str(e)
            logger.warning(f"WriterEngine: opentale check failed: {e}")

    def __repr__(self) -> str:
        return (
            f"WriterEngine(traces={len(self._traces)}, "
            f"opentale={self._opentale_available}, "
            f"circuit={self._cb_state.state.name})"
        )

    @property
    def circuit_state(self) -> dict[str, Any]:
        """断路器当前状态。"""
        return self._cb_state.to_dict()

    # ── 公共 API ─────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        strategy: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """基于 TransformProcess 执行写作操作。

        Args:
            process: 待执行的 WRITING Process
            strategy: 写作策略（plan/generate/resume/rewrite/status）
            inputs: 输入数据（genre, contract, chapter_index 等）

        Returns:
            RuntimeResult: 执行结果
        """
        trace_id = uuid.uuid4().hex
        started_at = time.time()
        strategy = strategy or "plan"
        inputs = inputs or {}
        genre = inputs.get("genre", "general")
        contract = inputs.get("contract", {})
        proc_id = process.process_id if process else "status"
        logger.info("execute writer", extra=dict(
            process_id=proc_id, strategy=strategy,
        ))

        # 发射 EXECUTION_STARTED 事件
        self._emit(EventType.EXECUTION_STARTED, {
            "trace_id": trace_id,
            "process_id": proc_id,
            "strategy": strategy,
            "genre": genre,
        })

        # 安全执行（含重试 + 断路器）
        def _run() -> dict[str, Any]:
            """内部执行闭包（给 safe_execute）。"""
            if strategy == "plan":
                r = self._do_plan(process, genre, contract, inputs)
            elif strategy == "generate":
                r = self._do_generate(process, genre, inputs)
            elif strategy == "resume":
                r = self._do_resume(process, genre, contract, inputs)
            elif strategy == "rewrite":
                r = self._do_rewrite(process, genre, inputs)
            elif strategy == "status":
                r = self._do_status()
            else:
                r = RuntimeResult(
                    success=False,
                    message=f"Unsupported strategy: {strategy}",
                    process_id=proc_id,
                )
            return {"success": True, "result": r}

        exec_result = safe_execute(
            _run,
            self._cb_state,
            self._retry_policy,
            logger=logger,
            engine_name=f"WriterEngine/{strategy}",
        )

        if exec_result["success"]:
            result: RuntimeResult = exec_result["result"]  # type: ignore[assignment]
        else:
            result = RuntimeResult(
                success=False,
                message=exec_result.get("message", "Execution failed"),
                process_id=proc_id,
            )

        # 记录 trace
        completed_at = time.time()
        trace = WriterTrace(
            trace_id=trace_id,
            process_id=proc_id,
            strategy=strategy,
            genre=genre,
            chapter_count=result.count,
            started_at=started_at,
            completed_at=completed_at,
            success=result.success,
        )
        self._traces[trace_id] = trace

        # 发射完成/失败事件
        if result.success:
            self._emit(EventType.EXECUTION_COMPLETED, {
                "trace_id": trace_id,
                "success": result.success,
                "chapter_count": result.count,
                "duration": round(completed_at - started_at, 3),
            })
        else:
            self._emit(EventType.EXECUTION_FAILED, {
                "trace_id": trace_id,
                "error": result.message,
            })

        return result

    # ── 内部策略 ────────────────────────────────────────────────

    def _do_plan(
        self,
        process: TransformProcess,
        genre: str,
        contract: dict[str, Any],
        inputs: dict[str, Any],
    ) -> RuntimeResult:
        """生成章节大纲（集成 NarrativePipeline Contract → Policy 推导）。"""
        chapter_count = inputs.get("chapter_count", 10)
        primary_driver = contract.get("primary_driver", genre)
        chapter_focus = contract.get("chapter_focus", {})
        proc_id = process.process_id

        # 1. Contract → Policy 推导
        policy = derive_policy(contract)

        # 2. 生成基础章节大纲
        chapters: list[dict[str, Any]] = []
        for i in range(1, chapter_count + 1):
            chapters.append({
                "chapter": i,
                "title": f"第{i}章",
                "focus": self._pick_chapter_focus(chapter_focus, i),
                "scene_types": self._distribute_scenes(
                    contract.get("scene_distribution", {}), i
                ),
                "conflict_type": self._pick_conflict(
                    contract.get("conflict_priority", {}), i
                ),
                "intensity": 0.5,
                "pacing_type": "balanced",
                "dialogue_ratio": 0.35,
                "description_ratio": 0.25,
            })

        # 3. 应用 Policy 约束（pacing/voice/emotion）
        chapters = apply_budget_constraints(chapters, policy)

        # 4. 结果存入工作记忆
        addr = f"writer/plan/{proc_id}"
        self._wm.set_preference(
            addr,
            {
                "chapters": chapters,
                "genre": genre,
                "policy": policy,
                "contract": contract,
            },
        )

        return RuntimeResult(
            success=True,
            message=f"Planned {chapter_count} chapters for {genre} "
                    f"(driver={primary_driver})",
            trace_id=uuid.uuid4().hex,
            process_id=proc_id,
            count=chapter_count,
            output_addresses=(addr,),
            content=chapters,
        )

    def _do_resume(
        self,
        process: TransformProcess,
        genre: str,
        contract: dict[str, Any],
        inputs: dict[str, Any],
    ) -> RuntimeResult:
        """从检查点续写。

        从工作记忆读取上一个 planning session 的状态，
        基于 progress 恢复规划。
        """
        proc_id = process.process_id
        checkpoint_id = inputs.get("checkpoint_id", proc_id)

        # 尝试从工作记忆恢复
        try:
            previous = self._wm.get_preference(f"writer/plan/{checkpoint_id}", None)
        except Exception:
            previous = None

        if previous and "chapters" in previous:
            chapters_raw = previous["chapters"]
            completed = sum(1 for ch in chapters_raw if ch.get("intensity", 0) > 0.3)
            remaining_count = inputs.get("chapter_count", max(10, len(chapters_raw)))

            # 重规划剩余章节，从 completed 处继续
            chapters = []
            for i in range(1, remaining_count + 1):
                chapters.append({
                    "chapter": i,
                    "title": f"第{i}章",
                    "focus": self._pick_chapter_focus(
                        contract.get("chapter_focus", {}), i
                    ),
                    "scene_types": self._distribute_scenes(
                        contract.get("scene_distribution", {}), i
                    ),
                    "conflict_type": self._pick_conflict(
                        contract.get("conflict_priority", {}), i
                    ),
                    "intensity": 0.5,
                    "pacing_type": "balanced",
                    "dialogue_ratio": 0.35,
                    "description_ratio": 0.25,
                    "resumed_from": checkpoint_id,
                    "completed_before_resume": completed,
                })

            # 应用 Policy
            policy = previous.get("policy", derive_policy(contract))
            chapters = apply_budget_constraints(chapters, policy)

            addr = f"writer/plan/{proc_id}"
            self._wm.set_preference(
                addr,
                {
                    "chapters": chapters,
                    "genre": genre,
                    "resumed": True,
                    "completed_before_resume": completed,
                },
            )

            return RuntimeResult(
                success=True,
                message=f"Resumed from {checkpoint_id}: {completed} chapters "
                        f"completed, {remaining_count} planned",
                trace_id=uuid.uuid4().hex,
                process_id=proc_id,
                count=remaining_count,
                output_addresses=(addr,),
                content=chapters,
            )

        # 无检查点时退化为 plan
        return self._do_plan(process, genre, contract, inputs)

    def _do_rewrite(
        self,
        process: TransformProcess,
        genre: str,
        inputs: dict[str, Any],
    ) -> RuntimeResult:
        """重写指定章节。"""
        proc_id = process.process_id
        chapter_index = inputs.get("chapter_index", 1)
        replacement_plan = inputs.get("replacement_plan", {})
        source_addr = inputs.get("source_addr", f"writer/plan/{proc_id}")

        # 读取现有规划
        try:
            existing = self._wm.get_preference(source_addr, None)
        except Exception:
            existing = None

        chapters_new: list[dict[str, Any]] = []
        if existing and "chapters" in existing:
            for ch in existing["chapters"]:
                if ch.get("chapter") == chapter_index:
                    ch.update(replacement_plan)
                    ch["rewritten"] = True
                chapters_new.append(ch)

        if not chapters_new:
            # 无现有规划则创建单章
            chapters_new = [replacement_plan]
            chapters_new[0]["chapter"] = chapter_index
            chapters_new[0]["rewritten"] = True

        new_addr = f"writer/rewrite/{proc_id}"
        self._wm.set_preference(new_addr, {"chapters": chapters_new, "genre": genre})

        return RuntimeResult(
            success=True,
            message=f"Rewritten chapter {chapter_index} ({len(chapters_new)} chapters)",
            trace_id=uuid.uuid4().hex,
            process_id=proc_id,
            count=len(chapters_new),
            output_addresses=(new_addr,),
            content=chapters_new,
        )

    # ── 内部策略 ────────────────────────────────────────────────

    def _do_generate(
        self,
        process: TransformProcess,
        genre: str,
        inputs: dict[str, Any],
    ) -> RuntimeResult:
        """生成章节内容（真实 LLM → MockProvider → opentale 三层降级）。"""
        if self._opentale_available:
            return self._delegate_to_opentale(process, genre, inputs)

        chapter_index = inputs.get("chapter_index", 1)
        proc_id = process.process_id
        source_addr = inputs.get("source_addr", f"writer/plan/{proc_id}")

        # 从工作记忆读取规划
        try:
            plan = self._wm.get_preference(source_addr, {})
        except Exception:
            plan = {}

        chapters_plan: list[dict[str, Any]] = plan.get("chapters", [])
        contract: dict[str, Any] = plan.get("contract", {})
        policy: dict[str, Any] = plan.get("policy", {})

        # 找出目标章节的规划
        target_chapter: dict[str, Any] = {"chapter": chapter_index, "title": f"第{chapter_index}章"}
        for ch in chapters_plan:
            if ch.get("chapter") == chapter_index:
                target_chapter = ch
                break

        # 使用 TextGenerator 生成章节内容
        try:
            import asyncio

            result = asyncio.run(
                self._text_generator.generate_chapter(
                    chapter=target_chapter,
                    contract=contract or {"genre": genre},
                    policy=policy,
                )
            )
            generated_text = result.text
            provider = result.provider
        except Exception as e:
            logger.warning(f"TextGenerator failed, falling back to template: {e}")
            generated_text = (
                f"[{genre}] Chapter {chapter_index} content (generated by {self._text_generator.provider.name}).\n"
                f"Focus: {target_chapter.get('focus', 'general')}\n"
                f"Scenes: {', '.join(target_chapter.get('scene_types', ['dialogue', 'action']))}"
            )
            provider = "fallback"

        chapters = [{
            "chapter": chapter_index,
            "title": target_chapter.get("title", f"第{chapter_index}章"),
            "generated": True,
            "word_count": len(generated_text.split()),
            "content": generated_text,
            "provider": provider,
        }]

        addr = f"writer/generated/{proc_id}"
        self._wm.set_preference(addr, {"chapters": chapters})

        return RuntimeResult(
            success=True,
            message=f"Generated chapter {chapter_index} via {provider} ({len(generated_text)} chars)",
            trace_id=uuid.uuid4().hex,
            process_id=proc_id,
            count=1,
            output_addresses=(addr,),
            content=chapters,
        )

    def _delegate_to_opentale(
        self,
        process: TransformProcess,
        genre: str,
        inputs: dict[str, Any],
    ) -> RuntimeResult:
        """委托给 OpenTale AutonomousNovelSystem 生成真实内容。"""
        try:
            result = self._opentale_system.generate(
                request={"genre": genre, "chapter_count": 1}
            )
            count = getattr(result, "chapter_count", 1)
            addr = f"writer/opentale/{process.process_id}"
            self._wm.set_preference(addr, {"result": result})

            return RuntimeResult(
                success=True,
                message=f"OpenTale generated {count} chapter(s)",
                trace_id=uuid.uuid4().hex,
                process_id=process.process_id,
                count=count,
                output_addresses=(addr,),
            )
        except Exception as e:
            logger.error(f"OpenTale delegation failed: {e}")
            return RuntimeResult(
                success=False,
                message=f"OpenTale error: {e}",
                process_id=process.process_id,
            )

    def _do_status(self) -> RuntimeResult:
        """返回当前写作状态。"""
        return RuntimeResult(
            success=True,
            message="Status OK",
            count=0,
            content=[{
                "state": self._generation_state,
                "traces": len(self._traces),
                "opentale_available": self._opentale_available,
            }],
        )

    # ── 辅助方法 ────────────────────────────────────────────────

    def _pick_chapter_focus(
        self,
        focus_weights: dict[str, float],
        chapter_index: int,
    ) -> str:
        """基于权重选取章节焦点。"""
        if not focus_weights:
            return "general"
        foci = list(focus_weights.keys())
        if not foci:
            return "general"
        # 简单轮转
        return foci[(chapter_index - 1) % len(foci)]

    def _distribute_scenes(
        self,
        scene_dist: dict[str, float],
        chapter_index: int,
    ) -> list[str]:
        """分配场景类型。"""
        if not scene_dist:
            return ["action", "interpersonal"]
        scenes = [s for s in scene_dist if s != "_normalized"]
        return scenes or ["interpersonal"]

    def _pick_conflict(
        self,
        conflict_priority: dict[str, float],
        chapter_index: int,
    ) -> str:
        """选择冲突类型。"""
        if not conflict_priority:
            return "interpersonal"
        conflicts = list(conflict_priority.keys())
        return conflicts[(chapter_index - 1) % len(conflicts)]

    def _emit(self, event_type: EventType, data: dict[str, Any]) -> None:
        """发射引擎事件。"""
        try:
            event = Event(
                event_id=uuid.uuid4().hex,
                event_type=event_type,
                source="writer_engine",
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload=data,
            )
            self._event_bus.publish(event)
        except Exception as e:
            logger.debug(f"Event emission failed (non-fatal): {e}")

    # ── 属性 ────────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> WriterTrace | None:
        return self._traces.get(trace_id)

    def get_all_traces(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._traces.values()]

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def last_trace(self) -> WriterTrace | None:
        if not self._traces:
            return None
        return list(self._traces.values())[-1]
