"""AddressResolver Engine 测试（Phase 4）。"""

from __future__ import annotations

import pytest

from ocos.engines.address_resolver import AddressResolver, Query
from ocos.models.information import UniversalAddress


class TestAddressResolver:

    @pytest.fixture
    def resolver(self) -> AddressResolver:
        return AddressResolver()

    def test_register_and_resolve(self, resolver):
        """注册后能正确路由解析。"""
        calls = []

        def my_resolver(addr: UniversalAddress) -> str:
            calls.append(addr)
            return f"resolved:{addr.id}"

        resolver.register("working", my_resolver)
        addr = UniversalAddress(namespace="working", type="goal", id="g1")
        result = resolver.resolve(addr)
        assert result == "resolved:g1"
        assert len(calls) == 1
        assert calls[0] == addr

    def test_resolve_unregistered_raises(self, resolver):
        """未注册的 namespace 引发 KeyError。"""
        addr = UniversalAddress(namespace="unknown", type="x", id="1")
        with pytest.raises(KeyError, match="unknown"):
            resolver.resolve(addr)

    def test_reregister_overwrites(self, resolver):
        """重复注册同一 namespace 会覆盖。"""

        def fn1(_):
            return "old"

        def fn2(_):
            return "new"

        resolver.register("ns", fn1)
        resolver.register("ns", fn2)
        addr = UniversalAddress(namespace="ns", type="x", id="1")
        assert resolver.resolve(addr) == "new"

    def test_unregister_removes(self, resolver):
        """注销后无法再解析。"""

        def fn(_):
            return "ok"

        resolver.register("ns", fn)
        resolver.unregister("ns")
        assert not resolver.has_namespace("ns")
        addr = UniversalAddress(namespace="ns", type="x", id="1")
        with pytest.raises(KeyError):
            resolver.resolve(addr)

    def test_unregister_nonexistent_raises(self, resolver):
        """注销不存在的 namespace 引发 KeyError。"""
        with pytest.raises(KeyError, match="nonexistent"):
            resolver.unregister("nonexistent")

    def test_has_namespace_true(self, resolver):
        """已注册的 namespace 返回 True。"""

        def fn(_):
            return None

        resolver.register("active", fn)
        assert resolver.has_namespace("active")

    def test_has_namespace_false(self, resolver):
        """未注册的 namespace 返回 False。"""
        assert not resolver.has_namespace("bogus")

    def test_list_namespaces_snapshot(self, resolver):
        """list_namespaces 返回排序快照。"""

        def fn(_):
            return None

        resolver.register("z", fn)
        resolver.register("a", fn)
        resolver.register("m", fn)
        assert resolver.list_namespaces() == ["a", "m", "z"]

    def test_list_namespaces_isolated(self, resolver):
        """快照不受后续变更影响。"""

        def fn(_):
            return None

        resolver.register("x", fn)
        snapshot = resolver.list_namespaces()
        resolver.unregister("x")
        # snapshot 是变更前的快照
        assert snapshot == ["x"]
        assert resolver.list_namespaces() == []

    def test_resolve_requires_universal_address(self, resolver):
        """非 UniversalAddress 参数引发 TypeError。"""
        with pytest.raises(TypeError, match="UniversalAddress"):
            resolver.resolve("not-an-address")  # type: ignore[arg-type]

    def test_register_empty_namespace_raises(self, resolver):
        """空 namespace 字符串引发 ValueError。"""

        def fn(_):
            return None

        with pytest.raises(ValueError, match="namespace"):
            resolver.register("", fn)

    def test_multiple_namespaces_independent(self, resolver):
        """多个 namespace 独立路由互不干扰。"""

        def fn_a(_):
            return "from-a"

        def fn_b(_):
            return "from-b"

        resolver.register("ns_a", fn_a)
        resolver.register("ns_b", fn_b)
        addr_a = UniversalAddress(namespace="ns_a", type="x", id="1")
        addr_b = UniversalAddress(namespace="ns_b", type="y", id="2")
        assert resolver.resolve(addr_a) == "from-a"
        assert resolver.resolve(addr_b) == "from-b"

    def test_resolver_receives_correct_address(self, resolver):
        """解析函数接收到完整的 UniversalAddress。"""
        captured = None

        def my_resolver(addr: UniversalAddress) -> str:
            nonlocal captured
            captured = addr
            return "ok"

        resolver.register("test", my_resolver)
        addr = UniversalAddress(namespace="test", type="goal", id="g99", version=2)
        resolver.resolve(addr)
        assert captured is not None
        assert captured.namespace == "test"
        assert captured.type == "goal"
        assert captured.id == "g99"
        assert captured.version == 2


# ── Query routing ──────────────────────────────────────────────────────────


class TestAddressResolverQuery:

    @pytest.fixture
    def resolver(self) -> AddressResolver:
        return AddressResolver()

    def test_route_query_delegates(self, resolver):
        """route_query 路由到 QueryHandler。"""
        items: list[str] = []

        def handler(q: Query) -> None:
            q.results = ["a", "b", "c"]

        resolver.register("ns", handler)
        q = Query(type="all", namespace="ns")
        result = resolver.route_query("ns", q)
        assert result.results == ["a", "b", "c"]

    def test_route_query_unregistered_raises(self, resolver):
        """未注册的 namespace 引发 KeyError。"""
        q = Query(type="all", namespace="missing")
        with pytest.raises(KeyError, match="missing"):
            resolver.route_query("missing", q)

    def test_route_query_empty_namespace_raises(self, resolver):
        """空 namespace 引发 ValueError。"""
        q = Query(type="all", namespace="")
        with pytest.raises(ValueError, match="namespace"):
            resolver.route_query("", q)

    def test_route_query_does_not_affect_resolve(self, resolver):
        """QueryHandler 注册后不影响 UniversalAddress resolve。"""

        def handler(q: Query) -> None:
            q.results = ["from-query"]

        def resolver_fn(addr: UniversalAddress) -> str:
            return f"resolved:{addr.id}"

        resolver.register("hybrid", handler)
        resolver.register("hybrid2", resolver_fn)

        q = Query(type="all", namespace="hybrid")
        result = resolver.route_query("hybrid", q)
        assert result.results == ["from-query"]

        addr = UniversalAddress(namespace="hybrid2", type="x", id="99")
        assert resolver.resolve(addr) == "resolved:99"
