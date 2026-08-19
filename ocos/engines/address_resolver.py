"""
AddressResolver — 地址解析引擎。

跨 Store 路由层，不拥有数据，只做路由。
维护 namespace → resolver_fn 映射，强制使用 UniversalAddress。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from ocos.logging import get_logger
from ocos.models.information import InformationState, SemanticRole, UniversalAddress

logger = get_logger(__name__)


@dataclass
class Query:
    """语义查询描述（跨 Store 协议）。

    由 RetrievalEngine 构造，通过 AddressResolver.route_query 路由。
    Store 端根据 type 分发到对应的查询逻辑。
    """

    type: Literal["by_role", "by_state", "all"]
    role: SemanticRole | None = None
    state: InformationState | None = None
    namespace: str = ""
    results: list = field(default_factory=list, hash=False, compare=False)


QueryHandler = Callable[[Query], None]


class AddressResolver:
    """地址解析引擎。

    不拥有数据，只做路由。维护 namespace → resolver_fn 映射，
    所有查询强制使用 UniversalAddress。
    """

    def __init__(self) -> None:
        self._resolvers: dict[str, Callable[[UniversalAddress], Any]] = {}
        logger.debug("__init__ completed", component="address_resolver")

    def register(
        self,
        namespace: str,
        resolver: Callable[[UniversalAddress], Any],
    ) -> None:
        """注册 namespace 对应的解析函数。

        若 namespace 已存在则覆盖。
        """
        logger.info("register", extra=dict(namespace=namespace))
        if not namespace:
            logger.error("register failed: empty namespace")
            raise ValueError("namespace must not be empty")
        self._resolvers[namespace] = resolver

    def unregister(self, namespace: str) -> None:
        """注销 namespace。"""
        if namespace not in self._resolvers:
            raise KeyError(f"namespace '{namespace}' not registered")
        del self._resolvers[namespace]

    def resolve(self, address: UniversalAddress) -> Any:
        """路由到 namespace 对应的解析函数并执行。"""
        if not isinstance(address, UniversalAddress):
            logger.error("resolve failed: invalid address type")
            raise TypeError("address must be a UniversalAddress")
        resolver = self._resolvers.get(address.namespace)
        if resolver is None:
            logger.error("resolve failed: no resolver for namespace", extra=dict(
                namespace=address.namespace,
            ))
            raise KeyError(
                f"no resolver registered for namespace '{address.namespace}'"
            )
        return resolver(address)

    def has_namespace(self, namespace: str) -> bool:
        """检查 namespace 是否已注册。"""
        return namespace in self._resolvers

    def list_namespaces(self) -> list[str]:
        """返回已注册 namespace 的快照列表。"""
        return sorted(self._resolvers.keys())

    def route_query(self, namespace: str, query: Query) -> Query:
        """路由 Query 到 namespace 对应的解析函数。

        QueryHandler 型解析函数会填充 query.results。
        """
        if not namespace:
            raise ValueError("namespace must not be empty")
        resolver = self._resolvers.get(namespace)
        if resolver is None:
            raise KeyError(f"no resolver registered for namespace '{namespace}'")
        resolver(query)  # type: ignore[call-arg, misc]
        return query

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="address_resolver",
    name="Address Resolver",
    version="1.0.0",
    engine_class="ocos.engines.address_resolver.AddressResolver",
    capabilities=['address_resolution'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
