"""OCOS engines/address_resolver 测试。"""

import pytest
from ocos.engines.address_resolver import AddressResolver, Query


class TestAddressResolver:
    def test_empty_resolver(self):
        resolver = AddressResolver()
        assert resolver.list_namespaces() == []
        assert resolver.has_namespace("foo") is False

    def test_register_and_resolve(self):
        resolver = AddressResolver()

        def my_resolver(address):
            return {"resolved": address.namespace}

        resolver.register("ns1", my_resolver)
        assert resolver.has_namespace("ns1") is True
        assert resolver.list_namespaces() == ["ns1"]

    def test_unregister(self):
        resolver = AddressResolver()
        resolver.register("ns1", lambda a: None)
        assert resolver.has_namespace("ns1") is True
        resolver.unregister("ns1")
        assert resolver.has_namespace("ns1") is False

    def test_unregister_missing_raises(self):
        resolver = AddressResolver()
        with pytest.raises(KeyError):
            resolver.unregister("missing")

    def test_empty_namespace_raises(self):
        resolver = AddressResolver()
        with pytest.raises(ValueError):
            resolver.register("", lambda a: None)

    def test_resolve_missing_namespace_raises(self):
        resolver = AddressResolver()
        from ocos.models.information import UniversalAddress
        addr = UniversalAddress(namespace="missing", type="info", id="a")
        with pytest.raises(KeyError):
            resolver.resolve(addr)

    def test_resolve_invalid_type_raises(self):
        resolver = AddressResolver()
        resolver.register("ns1", lambda a: "ok")
        with pytest.raises(TypeError):
            resolver.resolve("not_an_address")  # type: ignore

    def test_route_query(self):
        resolver = AddressResolver()

        def handler(query):
            query.results.append("result")

        resolver.register("ns1", handler)
        query = Query(type="all", namespace="ns1")
        result = resolver.route_query("ns1", query)
        assert result.results == ["result"]

    def test_route_query_missing_namespace_raises(self):
        resolver = AddressResolver()
        with pytest.raises(KeyError):
            resolver.route_query("missing", Query(type="all"))

    def test_route_query_empty_namespace_raises(self):
        resolver = AddressResolver()
        with pytest.raises(ValueError):
            resolver.route_query("", Query(type="all"))