"""
Retrieval Engine — 跨角色语义查询引擎。

使用 AddressResolver 路由到目标 Store，
支持按地址、语义角色、状态等维度检索，
每次查询发射 INFORMATION_QUERIED 事件。
"""

from __future__ import annotations

from typing import Any

from ocos.engines.address_resolver import AddressResolver, Query
from ocos.kernel.abi import Event, EventType
from ocos.models.information import InformationState, SemanticRole, UniversalAddress

from ocos.logging import get_logger

_SOURCE = "retrieval_engine"

logger = get_logger(__name__)


class RetrievalEngine:
    """检索引擎。

    跨 Store 语义查询，含事件发射。
    AddressResolver 为必选依赖，EventBus 为可选。
    """

    def __init__(
        self,
        resolver: AddressResolver,
        event_bus: Any | None = None,
    ) -> None:
        self._resolver = resolver
        self._event_bus = event_bus
        logger.debug("__init__ completed", component="retrieval_engine")

    # ── 单地址查询 ──────────────────────────────────────────────────────────

    def query(self, address: UniversalAddress) -> Any:
        """按 UniversalAddress 精确查询。"""
        if not isinstance(address, UniversalAddress):
            raise TypeError("address must be a UniversalAddress")
        logger.info("query", extra=dict(
            address_id=address.id, namespace=address.namespace,
        ))
        result = self._resolver.resolve(address)
        self._emit_query_event(
            operation="query",
            namespace=address.namespace,
            address_id=address.id,
        )
        return result

    # ── 语义查询 ────────────────────────────────────────────────────────────

    def query_by_role(
        self,
        role: SemanticRole,
        namespace: str | None = None,
    ) -> list[Any]:
        """按语义角色查询。namespace=None 查所有已注册 namespace。"""
        namespaces = [namespace] if namespace else self._resolver.list_namespaces()
        results: list[Any] = []
        if not namespaces:
            self._emit_query_event(operation="query_by_role", role=role.value)
            return results

        for ns in namespaces:
            if not self._resolver.has_namespace(ns):
                continue
            q = Query(type="by_role", role=role, namespace=ns)
            try:
                self._resolver.route_query(ns, q)
            except TypeError:
                # resolver not QueryHandler-capable; skip
                continue
            results.extend(q.results)

        self._emit_query_event(
            operation="query_by_role",
            namespace=namespace or "*",
            role=role.value,
        )
        return results

    def query_by_state(
        self,
        state: InformationState,
        namespace: str | None = None,
    ) -> list[Any]:
        """按信息状态查询。namespace=None 查所有已注册 namespace。"""
        namespaces = [namespace] if namespace else self._resolver.list_namespaces()
        results: list[Any] = []
        if not namespaces:
            self._emit_query_event(operation="query_by_state", state=state.value)
            return results

        for ns in namespaces:
            if not self._resolver.has_namespace(ns):
                continue
            q = Query(type="by_state", state=state, namespace=ns)
            try:
                self._resolver.route_query(ns, q)
            except TypeError:
                continue
            results.extend(q.results)

        self._emit_query_event(
            operation="query_by_state",
            namespace=namespace or "*",
            state=state.value,
        )
        return results

    def query_all(self, namespace: str) -> list[Any]:
        """列出 namespace 中所有信息。"""
        if not namespace:
            raise ValueError("namespace must not be empty")
        q = Query(type="all", namespace=namespace)
        if self._resolver.has_namespace(namespace):
            try:
                self._resolver.route_query(namespace, q)
            except TypeError:
                pass

        self._emit_query_event(
            operation="query_all",
            namespace=namespace,
        )
        return q.results

    # ── 内部方法 ────────────────────────────────────────────────────────────

    def _emit_query_event(
        self,
        operation: str,
        **extra: Any,
    ) -> None:
        """发射 INFORMATION_QUERIED 事件（EventBus 可选）。"""
        if self._event_bus is None:
            return
        event = Event(
            event_type=EventType.INFORMATION_QUERIED,
            source=_SOURCE,
            payload={"operation": operation, **extra},
        )
        self._event_bus.publish(event, sync=True)

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="retrieval_engine",
    name="Retrieval Engine",
    version="1.0.0",
    engine_class="ocos.engines.retrieval_engine.RetrievalEngine",
    capabilities=['retrieval'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
