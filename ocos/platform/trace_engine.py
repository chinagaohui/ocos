"""
C1 Explainability Trace 引擎 — 可解释性追踪记录器。

职责：
- 4 类 Trace 数据模型（Decision / Reasoning / Simulation / Learning）
- InMemory TraceStore（环形缓冲区，可配置上限）
- 注入接口：record_decision/reasoning/simulation/learning_trace
- 查询接口：query_traces / get_trace
- 可选 Event Bus 集成（TRACE_RECORDED 事件）
- 只写日志，不参与运行时决策

架构定位：
  Trace 引擎是 Audit Engine (C2) 的数据源，不是 Runtime 的依赖。
  即使 TraceStore 故障，也不影响 Reasoning / Decision 的正常运行。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.models.process import ProcessType, TransformProcess


# ── 枚举 ────────────────────────────────────────────────────────────────────

class TraceType(str, Enum):
    """6 类可解释性 Trace。"""
    DECISION = "decision"
    REASONING = "reasoning"
    SIMULATION = "simulation"
    LEARNING = "learning"
    MEMORY = "memory"
    EXECUTION = "execution"
    GOAL = "goal"


# ── 默认配置 ────────────────────────────────────────────────────────────────

DEFAULT_TRACE_STORE_SIZE: int = 10_000
QUERY_MAX_LIMIT: int = 500
QUERY_DEFAULT_LIMIT: int = 50


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionTrace:
    """决策 Trace：记录 Decision 的形成与选择过程。

    alternatives 为候选方案的 proposal_type 字符串列表（轻量，足够 Audit 使用）。
    """
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.DECISION
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Decision-specific
    decision_id: str = ""
    goal_id: str = ""
    status: str = ""  # 承诺态变更时的状态值
    previous_status: str = ""  # 前一个状态（空表示初始创建）
    reasoning_chain: list[str] = field(default_factory=list)
    confidence: float = 0.0
    outcome: str = ""  # accepted | rejected | deferred
    alternatives: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReasoningTrace:
    """推理 Trace：记录 Reasoning Engine 的中间步骤链。"""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.REASONING
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Reasoning-specific
    reasoning_id: str = ""
    observation_ids: list[str] = field(default_factory=list)
    knowledge_ids_used: list[str] = field(default_factory=list)
    reasoning_steps: list[str] = field(default_factory=list)
    conclusion: str = ""


@dataclass(frozen=True)
class SimulationTrace:
    """模拟 Trace：记录 Simulation Engine 的推演路径。

    state_delta 记录模拟前后的关键状态差异（dict），非完整快照。
    """
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.SIMULATION
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Simulation-specific
    simulation_id: str = ""
    scenario: str = ""
    depth: int = 0
    branches_explored: int = 0
    outcome: str = ""  # success | failure | inconclusive
    state_delta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningTrace:
    """学习 Trace：记录 Learning Engine 的知识更新。"""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.LEARNING
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Learning-specific
    learning_id: str = ""
    source_observation_id: str = ""
    previous_knowledge: str = ""
    new_knowledge: str = ""
    learning_rate_delta: float = 0.0


@dataclass(frozen=True)
class MemoryTrace:
    """记忆 Trace：记录 WorkingMemory 的存储/检索/遗忘操作。

    对应 TraceType.MEMORY。内容摘要（content_summary）存储语义摘要，
    不存全量内容，控制 TraceStore 体积。
    """
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.MEMORY
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Memory-specific
    address: str = ""  # UniversalAddress 字符串，如 "working:goal:g1"
    operation: str = ""  # store | retrieve | forget | consolidate | clear
    content_summary: str = ""


@dataclass(frozen=True)
class ExecutionTrace:
    """执行 Trace：记录 Execution 从创建到完成的全过程。

    对应 TraceType.EXECUTION。附带时间信息以支持执行耗时分析。
    """
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.EXECUTION
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Execution-specific
    execution_id: str = ""
    decision_id: str = ""
    status: str = ""  # final status: succeeded | failed | interrupted | cancelled
    started_at: str = ""
    completed_at: str = ""
    action_ids: tuple[str, ...] = field(default_factory=tuple)
    observation_addresses: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GoalTrace:
    """Goal Trace：记录 Goal 的生命周期变更。

    对应 TraceType.GOAL。记录 Goal 从创建到终止的完整状态转移。
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_type: TraceType = TraceType.GOAL
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    # Goal-specific
    goal_id: str = ""
    status: str = ""  # GoalStatus value: active | paused | completed | failed | ...
    previous_status: str = ""
    source_type: str = ""  # user | agent_generated | decomposition | external_event | system
    parent_goal_id: str = ""
    observation_addresses: tuple[str, ...] = field(default_factory=tuple)
    started_at: str = ""
    completed_at: str = ""


# 所有 Trace 类型的联合
TraceRecord = DecisionTrace | ReasoningTrace | SimulationTrace | LearningTrace | MemoryTrace | ExecutionTrace | GoalTrace


# ── 存储 ────────────────────────────────────────────────────────────────────

class InMemoryTraceStore:
    """内存 Trace 存储。

    - 环形缓冲区，max_size 可配置（默认 10,000）
    - FIFO 淘汰：超上限时移除最旧记录
    - 按 trace_id / decision_id / trace_type / source 过滤查询
    """

    def __init__(self, max_size: int = DEFAULT_TRACE_STORE_SIZE):
        self._max_size = max(max_size, 1)
        self._traces: dict[str, TraceRecord] = {}
        self._order: list[str] = []  # FIFO 顺序

    def store(self, trace: TraceRecord) -> None:
        """写入一条 Trace。超过上限时淘汰最旧记录。"""
        if len(self._order) >= self._max_size:
            oldest_id = self._order.pop(0)
            self._traces.pop(oldest_id, None)
        self._traces[trace.trace_id] = trace
        self._order.append(trace.trace_id)

    def get(self, trace_id: str) -> Optional[TraceRecord]:
        """按 trace_id 查询。"""
        return self._traces.get(trace_id)

    def query(
        self,
        trace_type: Optional[TraceType] = None,
        source: Optional[str] = None,
        decision_id: Optional[str] = None,
        limit: int = QUERY_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[TraceRecord]:
        """查询 Trace，按存储顺序逆序（最新优先）。

        Args:
            trace_type: 按类型过滤
            source: 按来源过滤
            decision_id: 仅对 DecisionTrace 有效（按 decision_id 过滤）
            limit: 最多返回条数（上限 QUERY_MAX_LIMIT）
            offset: 跳过的条数

        Returns:
            匹配的 Trace 列表（最新优先）
        """
        limit = min(max(limit, 1), QUERY_MAX_LIMIT)
        offset = max(offset, 0)

        results: list[TraceRecord] = []
        # 逆序遍历（最新优先）
        for tid in reversed(self._order):
            trace = self._traces[tid]
            if trace_type is not None and trace.trace_type != trace_type:
                continue
            if source is not None and trace.source != source:
                continue
            if decision_id is not None:
                if not isinstance(trace, DecisionTrace):
                    continue
                if trace.decision_id != decision_id:
                    continue
            results.append(trace)

        return results[offset:offset + limit]

    def count(self) -> int:
        """当前存储的 Trace 总数。"""
        return len(self._order)

    def clear(self) -> None:
        """清空所有 Trace。"""
        self._traces.clear()
        self._order.clear()


# ── Trace 引擎 ──────────────────────────────────────────────────────────────

class TraceEngine:
    """Explainability Trace 引擎主入口。

    提供 4 类 Trace 的注入接口和查询服务。
    Event Bus 集成可选（默认不发射事件，由调用方显式控制）。
    """

    def __init__(
        self,
        store: Optional[InMemoryTraceStore] = None,
        event_bus: Any = None,
        max_size: int = DEFAULT_TRACE_STORE_SIZE,
    ):
        self._store = store or InMemoryTraceStore(max_size=max_size)
        self._event_bus = event_bus

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def store(self) -> InMemoryTraceStore:
        """暴露底层存储（供 Audit Engine 直接访问）。"""
        return self._store

    # ── 注入接口 ────────────────────────────────────────────────────────────

    def record_decision_trace(
        self,
        decision_id: str = "",
        goal_id: str = "",
        source: str = "",
        status: str = "",
        previous_status: str = "",
        reasoning_chain: Optional[list[str]] = None,
        confidence: float = 0.0,
        outcome: str = "",
        alternatives: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 DecisionTrace。

        Args:
            decision_id: 对应的 Decision ID
            goal_id: 关联的目标 ID
            source: 来源模块名
            status: 承诺态变更时的状态值
            previous_status: 前一个状态（空表示初始创建）
            reasoning_chain: 推理步骤摘要
            confidence: 置信度 (0.0 ~ 1.0)
            outcome: 结果 (accepted / rejected / deferred)
            alternatives: 备选方案列表
            metadata: 附加元数据
            emit_event: 是否发射 TRACE_RECORDED 事件

        Returns:
            新创建的 trace_id
        """
        trace = DecisionTrace(
            source=source,
            decision_id=decision_id,
            goal_id=goal_id,
            status=status,
            previous_status=previous_status,
            reasoning_chain=list(reasoning_chain or []),
            confidence=confidence,
            outcome=outcome,
            alternatives=list(alternatives or []),
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def record_reasoning_trace(
        self,
        reasoning_id: str = "",
        source: str = "",
        observation_ids: Optional[list[str]] = None,
        knowledge_ids_used: Optional[list[str]] = None,
        reasoning_steps: Optional[list[str]] = None,
        conclusion: str = "",
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 ReasoningTrace。"""
        trace = ReasoningTrace(
            source=source,
            reasoning_id=reasoning_id,
            observation_ids=list(observation_ids or []),
            knowledge_ids_used=list(knowledge_ids_used or []),
            reasoning_steps=list(reasoning_steps or []),
            conclusion=conclusion,
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def record_simulation_trace(
        self,
        simulation_id: str = "",
        source: str = "",
        scenario: str = "",
        depth: int = 0,
        branches_explored: int = 0,
        outcome: str = "",
        state_delta: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 SimulationTrace。"""
        trace = SimulationTrace(
            source=source,
            simulation_id=simulation_id,
            scenario=scenario,
            depth=depth,
            branches_explored=branches_explored,
            outcome=outcome,
            state_delta=dict(state_delta or {}),
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def record_learning_trace(
        self,
        learning_id: str = "",
        source: str = "",
        source_observation_id: str = "",
        previous_knowledge: str = "",
        new_knowledge: str = "",
        learning_rate_delta: float = 0.0,
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 LearningTrace。"""
        trace = LearningTrace(
            source=source,
            learning_id=learning_id,
            source_observation_id=source_observation_id,
            previous_knowledge=previous_knowledge,
            new_knowledge=new_knowledge,
            learning_rate_delta=learning_rate_delta,
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def record_memory_trace(
        self,
        address: str = "",
        source: str = "",
        operation: str = "",
        content_summary: str = "",
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 MemoryTrace。

        Args:
            address: UniversalAddress 字符串，如 "working:goal:g1"
            source: 来源模块名（如 context_manager, forgetting_engine）
            operation: 操作类型（store | retrieve | forget | consolidate | clear）
            content_summary: 内容摘要（语义摘要，非全量）
            metadata: 附加元数据
            emit_event: 是否发射 TRACE_RECORDED 事件

        Returns:
            新创建的 trace_id
        """
        trace = MemoryTrace(
            source=source,
            address=address,
            operation=operation,
            content_summary=content_summary,
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    # ── Process 统一入口 (Phase 15 — Process Foundation) ─────────────────

    def record_process_trace(
        self,
        process: TransformProcess,
        source: str = "process",
        emit_event: bool = True,
    ) -> str:
        """根据 process_type 自动分发到对应的 Trace 记录方法。

        统一入口，避免外部调用方需要按 ProcessType 手动 dispatch。
        ProcessType 扩展时只需更新内部路由表，调用方代码不变。

        Args:
            process: 已完成/已失败的 TransformProcess 实例
            source: 来源模块名
            emit_event: 是否发射 TRACE_RECORDED 事件

        Returns:
            新创建的 trace_id

        Raises:
            ValueError: 不支持的 ProcessType
        """
        dispatch = {
            ProcessType.REASONING: self._record_reasoning_from_process,
            ProcessType.DECISION: self._record_decision_from_process,
            ProcessType.SIMULATION: self._record_simulation_from_process,
            ProcessType.LEARNING: self._record_learning_from_process,
        }
        method = dispatch.get(process.process_type)
        if method is None:
            raise ValueError(
                f"Unsupported ProcessType: {process.process_type}. "
                f"Supported types: {list(dispatch.keys())}"
            )
        return method(process, source=source, emit_event=emit_event)

    # ── Process 内部路由方法 ─────────────────────────────────────────────

    def _record_reasoning_from_process(
        self,
        process: TransformProcess,
        source: str = "process",
        emit_event: bool = True,
    ) -> str:
        """从 ReasoningProcess 构造 ReasoningTrace。"""
        trace = ReasoningTrace(
            source=source,
            reasoning_id=process.process_id,
            observation_ids=[
                str(addr.id) for addr in process.input_addresses
            ],
            knowledge_ids_used=[],
            reasoning_steps=[
                step.description for step in process.steps
            ],
            conclusion=str(
                [str(addr.id) for addr in process.output_addresses]
            ),
            metadata=dict(process.metadata),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def _record_decision_from_process(
        self,
        process: TransformProcess,
        source: str = "process",
        emit_event: bool = True,
    ) -> str:
        """从 DecisionProcess 构造 DecisionTrace。"""
        trace = DecisionTrace(
            source=source,
            decision_id=process.process_id,
            reasoning_chain=[
                step.description for step in process.steps
            ],
            confidence=process.confidence,
            metadata=dict(process.metadata),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def _record_simulation_from_process(
        self,
        process: TransformProcess,
        source: str = "process",
        emit_event: bool = True,
    ) -> str:
        """从 SimulationProcess 构造 SimulationTrace。"""
        trace = SimulationTrace(
            source=source,
            simulation_id=process.process_id,
            scenario=process.metadata.get("scenario", ""),
            outcome=process.metadata.get("outcome", ""),
            state_delta=process.metadata.get("state_delta", {}),
            metadata=dict(process.metadata),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    def _record_learning_from_process(
        self,
        process: TransformProcess,
        source: str = "process",
        emit_event: bool = True,
    ) -> str:
        """从 LearningProcess 构造 LearningTrace。"""
        trace = LearningTrace(
            source=source,
            learning_id=process.process_id,
            previous_knowledge=process.metadata.get("previous_knowledge", ""),
            new_knowledge=process.metadata.get("new_knowledge", ""),
            learning_rate_delta=process.metadata.get("learning_rate_delta", 0.0),
            metadata=dict(process.metadata),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    # ── Execution Trace (Phase 17.1 — Execution Theory → Code Alignment) ───

    def record_execution(
        self,
        execution_id: str = "",
        decision_id: str = "",
        source: str = "",
        status: str = "",
        started_at: str = "",
        completed_at: str = "",
        action_ids: Optional[list[str]] = None,
        observation_addresses: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 ExecutionTrace。

        Args:
            execution_id: Execution ID
            decision_id: 引用的 Decision ID
            source: 来源模块名
            status: 最终状态 (succeeded | failed | interrupted | cancelled)
            started_at: 开始时间
            completed_at: 完成时间
            action_ids: 执行的 Action ID 列表
            observation_addresses: 产出的 Observation Address 列表
            metadata: 附加元数据
            emit_event: 是否发射 TRACE_RECORDED 事件

        Returns:
            新创建的 trace_id
        """
        trace = ExecutionTrace(
            execution_id=execution_id,
            decision_id=decision_id,
            source=source,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            action_ids=tuple(action_ids or []),
            observation_addresses=tuple(observation_addresses or []),
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    # ── Goal Trace (Phase 17.2 — Goal Theory → Code Alignment) ─────

    def record_goal(
        self,
        goal_id: str = "",
        source: str = "",
        status: str = "",
        previous_status: str = "",
        source_type: str = "",
        parent_goal_id: str = "",
        observation_addresses: Optional[list[str]] = None,
        started_at: str = "",
        completed_at: str = "",
        metadata: Optional[dict[str, Any]] = None,
        emit_event: bool = False,
    ) -> str:
        """记录一条 GoalTrace。

        Args:
            goal_id: Goal ID
            source: 来源模块名
            status: 当前 GoalStatus 值
            previous_status: 前一状态（用于状态转移分析）
            source_type: Goal 来源类型
            parent_goal_id: 父 Goal ID
            observation_addresses: 关联的 Observation Address 列表
            started_at: 创建时间
            completed_at: 完成时间
            metadata: 附加元数据
            emit_event: 是否发射 TRACE_RECORDED 事件

        Returns:
            新创建的 trace_id
        """
        trace = GoalTrace(
            goal_id=goal_id,
            source=source,
            status=status,
            previous_status=previous_status,
            source_type=source_type,
            parent_goal_id=parent_goal_id,
            observation_addresses=tuple(observation_addresses or []),
            started_at=started_at,
            completed_at=completed_at,
            metadata=dict(metadata or {}),
        )
        self._store.store(trace)
        if emit_event:
            self._emit(trace)
        return trace.trace_id

    # ── 查询接口 ────────────────────────────────────────────────────────────

    def query_traces(
        self,
        trace_type: Optional[TraceType] = None,
        source: Optional[str] = None,
        decision_id: Optional[str] = None,
        limit: int = QUERY_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[TraceRecord]:
        """查询 Trace 记录。"""
        return self._store.query(
            trace_type=trace_type,
            source=source,
            decision_id=decision_id,
            limit=limit,
            offset=offset,
        )

    def get_trace(self, trace_id: str) -> Optional[TraceRecord]:
        """按 trace_id 获取单条 Trace。"""
        return self._store.get(trace_id)

    def get_trace_count(self) -> int:
        """当前存储的 Trace 总数。"""
        return self._store.count()

    # ── 重置 ────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """清空所有 Trace 记录。"""
        self._store.clear()

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _emit(self, trace: TraceRecord) -> None:
        """发射 TRACE_RECORDED 事件。"""
        if self._event_bus is None:
            return
        event = Event(
            event_type=EventType.TRACE_RECORDED,
            source="trace_engine",
            payload={
                "trace_id": trace.trace_id,
                "trace_type": trace.trace_type.value,
                "source": trace.source,
            },
        )
        self._event_bus.publish(event, sync=True)
