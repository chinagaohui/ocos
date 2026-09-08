"""EngineBridge — Agent ↔ Engine 桥接层。

将 ocos/engines/ 中的真实引擎实例注册到 Agent 运行时，
通过归一化的接口供 CapabilitySelector / DecisionLoop 调用。
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Optional

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.kernel.abi import Event, EventType
from ocos.models.process import TransformProcess, ProcessType, ProcessState

logger = logging.getLogger(__name__)


class EngineAdapter:
    """引擎适配器 — 封装引擎实例并提供归一化调用接口。"""

    def __init__(self, engine_name: str, engine: Any):
        self.name = engine_name
        self._engine = engine
        self._trace_ids: list[str] = []

    def execute(
        self,
        process_type: ProcessType,
        operation: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """统一执行入口。"""
        process = TransformProcess(
            process_type=process_type,
            process_state=ProcessState.RUNNING,
            engine_id=self.name,
        )
        try:
            result = self._engine.execute(
                process=process,
                **self._build_kwargs(process_type, operation, inputs),
            )
            if result.success and result.trace_id:
                self._trace_ids.append(result.trace_id)

            return {
                "success": result.success,
                "message": result.message,
                "trace_id": result.trace_id,
                "process_id": result.process_id,
                "count": getattr(result, "step_count",
                               getattr(result, "steps",
                                       getattr(result, "count", 0))),
                "addresses": result.output_addresses,
            }
        except Exception as e:
            logger.error(f"Engine {self.name} execute failed: {e}")
            return {"success": False, "message": str(e), "trace_id": ""}

    def _build_kwargs(
        self,
        process_type: ProcessType,
        operation: str | None,
        inputs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if process_type == ProcessType.REASONING:
            if operation:
                kwargs["operation"] = operation
            if inputs:
                kwargs["premises"] = inputs
        elif process_type == ProcessType.PLANNING:
            if operation:
                kwargs["strategy"] = operation
            if inputs:
                kwargs["inputs"] = inputs
        else:
            if operation:
                kwargs["operation"] = operation
            if inputs:
                kwargs["inputs"] = inputs
        return kwargs

    @property
    def trace_count(self) -> int:
        return len(self._trace_ids)

    @property
    def last_trace_id(self) -> str:
        return self._trace_ids[-1] if self._trace_ids else ""


ENGINE_REGISTRY: dict[str, type] = {}


def _ensure_engines_registered() -> None:
    """幂等注册内置引擎。

    模块级调用一次 (常规导入顺序); EngineBridge.__init__ 再兜底调用一次 —
    当 ocos.engines 包先于本模块被导入时, 模块级注册会因引擎尚未初始化
    完成而静默失败, 兜底注册保证可用。
    WriterEngine 兜底已随收敛裁决 P1 移除（归档至 ocos/_archive/engines/，
    writer 角色现役由 DecisionBridge/TaskDAG LLM 承担）。
    """
    if "planner" not in ENGINE_REGISTRY:
        try:
            from ocos.engines.planning_engine import PlanningEngine
            ENGINE_REGISTRY["planner"] = PlanningEngine
            ENGINE_REGISTRY["planning_engine"] = PlanningEngine
        except ImportError:
            logger.debug("PlanningEngine not available.")

    if "reasoner" not in ENGINE_REGISTRY:
        try:
            from ocos.engines.reasoning_engine import ReasoningEngine
            ENGINE_REGISTRY["reasoner"] = ReasoningEngine
            ENGINE_REGISTRY["reasoning_engine"] = ReasoningEngine
        except ImportError:
            logger.debug("ReasoningEngine not available.")


_ensure_engines_registered()


class EngineBridge:
    """引擎桥接 — 工厂 + 注册表。

    为 AgentRuntime 提供轻量引擎管理：
    - 自动创建引擎实例（共享 EventBus + WorkingMemory）
    - 按名称查询适配器
    - 支持动态注册
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        working_memory: WorkingMemory | None = None,
    ):
        self._event_bus = event_bus or EventBus()
        self._working_memory = working_memory or WorkingMemory(event_bus=self._event_bus)
        # 兜底: 循环导入 (engines 包先导入) 时模块级注册会静默失败, 此处治愈
        _ensure_engines_registered()
        self._adapters: dict[str, EngineAdapter] = {}
        self._engine_types: dict[str, type] = dict(ENGINE_REGISTRY)
        # Phase 23-A: 延迟创建的 CapabilityRegistry
        self._capability_registry: Any = None

    def register_engine_type(self, name: str, engine_cls: type) -> None:
        """注册引擎类型（可由外部项目扩展）。"""
        self._engine_types[name] = engine_cls

    def register(
        self,
        engine_name: str,
        engine_cls: type | None = None,
        **init_kwargs: Any,
    ) -> EngineAdapter:
        """注册并创建引擎实例。"""
        cls = engine_cls or self._engine_types.get(engine_name)
        if cls is None:
            raise ValueError(
                f"No engine class for '{engine_name}'. "
                f"Available: {list(self._engine_types.keys())}"
            )

        # 自动注入依赖 — 仅传构造函数实际接受的参数
        # 先收集构造函数参数名
        known_params: set[str] = set()
        sig_inspected = False
        try:
            sig = inspect.signature(cls.__init__)
            for p in sig.parameters:
                if p not in ("self", "args", "kwargs"):
                    known_params.add(p)
            sig_inspected = True
        except (ValueError, TypeError):
            pass  # 无法检查签名时 fallback 到通用方式

        kwargs = dict(init_kwargs)
        if sig_inspected:
            # 精确注入：仅当构造函数声明了对应参数时才传入
            if "event_bus" in known_params:
                kwargs.setdefault("event_bus", self._event_bus)
            if "working_memory" in known_params:
                kwargs.setdefault("working_memory", self._working_memory)
        else:
            # fallback：无法检查签名时保守注入
            kwargs.setdefault("event_bus", self._event_bus)
            kwargs.setdefault("working_memory", self._working_memory)

        engine = cls(**kwargs)
        adapter = EngineAdapter(engine_name, engine)
        self._adapters[engine_name] = adapter
        logger.info(f"EngineBridge: registered '{engine_name}' ({cls.__name__})")
        return adapter

    def get_adapter(self, engine_name: str) -> EngineAdapter | None:
        """获取已注册的引擎适配器。"""
        return self._adapters.get(engine_name)

    def execute(
        self,
        engine_name: str,
        process_type: ProcessType,
        operation: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """便捷执行。"""
        adapter = self.get_adapter(engine_name)
        if adapter is None:
            return {"success": False, "message": f"Engine '{engine_name}' not found"}
        return adapter.execute(process_type, operation, inputs)

    def get_available_engines(self) -> list[str]:
        """获取已注册的引擎名称列表。"""
        return list(self._adapters.keys())

    def register_all(self) -> None:
        """注册所有已知引擎类型（懒惰注册，仅可用者）。"""
        for name in list(self._engine_types.keys()):
            if name not in self._adapters:
                try:
                    self.register(name)
                except Exception as e:
                    logger.warning(f"EngineBridge: cannot register '{name}': {e}")

    @property
    def count(self) -> int:
        return len(self._adapters)

    @property
    def capability_registry(self) -> Any:
        """Phase 23-A: 延迟构建的 CapabilityRegistry。

        将 ENGINE_REGISTRY 中的类型注册为能力。
        ENGINE_REGISTRY 保留为 deprecated alias。
        """
        if self._capability_registry is None:
            from ocos.capability.registry import CapabilityRegistry
            from ocos.capability.descriptor import CapabilityDescriptor, CapabilityCategory
            from ocos.capability.provider import ProviderDescriptor, ProviderType

            self._capability_registry = CapabilityRegistry()
            for name, cls in self._engine_types.items():
                # 从 ENGINE_REGISTRY 映射到 CapabilityDescriptor
                cap_id = f"ocos.{name}"
                desc = CapabilityDescriptor(
                    capability_id=cap_id,
                    name=cls.__name__,
                    category=CapabilityCategory.CUSTOM,
                    tags=[name, "engine"],
                )
                prov = ProviderDescriptor(
                    provider_id=name,
                    name=cls.__name__,
                    provider_type=ProviderType.ENGINE,
                    class_path=f"{cls.__module__}.{cls.__name__}",
                    capabilities=[cap_id],
                )
                self._capability_registry.register_capability(desc)
                self._capability_registry.register_provider(prov)
                self._capability_registry.bind(cap_id, name)
        return self._capability_registry
