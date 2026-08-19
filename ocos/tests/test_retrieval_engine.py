"""Retrieval Engine 测试（Phase 5）。"""

from __future__ import annotations

import pytest

from ocos.engines.address_resolver import AddressResolver, Query
from ocos.engines.retrieval_engine import RetrievalEngine
from ocos.kernel.abi import EventType
from ocos.models.information import InformationState, SemanticRole, UniversalAddress


# ── 辅助 QueryHandler 工厂 ────────────────────────────────────────────────


def _make_list_handler(items: list[str]) -> callable:
    """创建返回固定 items 的 QueryHandler。"""
    def handler(q: Query) -> None:
        q.results = items
    return handler


def _make_role_handler(items: list[tuple[str, str]]) -> callable:
    """按 role 过滤的 QueryHandler。items = [(id, role), ...]。"""
    def handler(q: Query) -> None:
        if q.type == "by_role":
            q.results = [item_id for item_id, role in items if role == q.role.value]
        elif q.type == "by_state":
            q.results = [item_id for item_id, _state in items]
        else:
            q.results = [item_id for item_id, _ in items]
    return handler


def _make_state_handler(items: list[tuple[str, str]]) -> callable:
    """按 state 过滤的 QueryHandler。items = [(id, state), ...]。"""
    def handler(q: Query) -> None:
        if q.type == "by_state" and q.state is not None:
            q.results = [item_id for item_id, state in items if state == q.state.value]
        elif q.type == "all":
            q.results = [item_id for item_id, _ in items]
        else:
            q.results = [item_id for item_id, _ in items]
    return handler


class TestRetrievalEngine:

    @pytest.fixture
    def resolver(self) -> AddressResolver:
        return AddressResolver()

    @pytest.fixture
    def engine(self, resolver: AddressResolver) -> RetrievalEngine:
        return RetrievalEngine(resolver)

    # ── 单地址查询 ──────────────────────────────────────────────────────────

    def test_query_resolves_address(self, resolver, engine):
        def my_resolver(addr: UniversalAddress) -> str:
            return f"resolved:{addr.id}"
        resolver.register("ns", my_resolver)
        addr = UniversalAddress(namespace="ns", type="x", id="42")
        assert engine.query(addr) == "resolved:42"

    def test_query_unknown_address_raises(self, engine):
        addr = UniversalAddress(namespace="unknown", type="x", id="1")
        with pytest.raises(KeyError):
            engine.query(addr)

    def test_query_non_universal_address_raises(self, engine):
        with pytest.raises(TypeError, match="UniversalAddress"):
            engine.query("not-ua")  # type: ignore[arg-type]

    def test_query_emits_information_queried(self, resolver):
        """query 通过 EventBus 发射 INFORMATION_QUERIED。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)

        def my_resolver(addr: UniversalAddress) -> str:
            return "ok"
        resolver.register("ns", my_resolver)

        events_received: list = []

        def on_event(event):
            events_received.append(event)

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        addr = UniversalAddress(namespace="ns", type="x", id="99")
        engine.query(addr)
        assert len(events_received) == 1
        ev = events_received[0]
        assert ev.event_type == EventType.INFORMATION_QUERIED
        assert ev.payload["operation"] == "query"

    def test_query_no_event_bus_works(self, engine, resolver):
        """无 EventBus 时 query 正常执行。"""
        def my_resolver(addr: UniversalAddress) -> str:
            return "ok"
        resolver.register("ns", my_resolver)
        addr = UniversalAddress(namespace="ns", type="x", id="1")
        assert engine.query(addr) == "ok"

    def test_multiple_queries_increment_events(self, resolver):
        """多次 query 产生多次事件。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)

        def my_resolver(addr: UniversalAddress) -> str:
            return f"item:{addr.id}"
        resolver.register("ns", my_resolver)

        count = 0

        def on_event(event):
            nonlocal count
            count += 1

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        addrs = [
            UniversalAddress(namespace="ns", type="x", id=str(i))
            for i in range(3)
        ]
        for a in addrs:
            engine.query(a)
        assert count == 3

    # ── 语义查询 ────────────────────────────────────────────────────────────

    def test_query_by_role_returns_filtered(self, resolver, engine):
        """按 SemanticRole 过滤。"""
        handler = _make_role_handler([
            ("goal1", "goal"),
            ("goal2", "goal"),
            ("face1", "observation"),
        ])
        resolver.register("ns", handler)
        result = engine.query_by_role(SemanticRole.GOAL, namespace="ns")
        assert result == ["goal1", "goal2"]

    def test_query_by_role_all_namespaces(self, resolver, engine):
        """跨多个 namespace 按 role 查询。"""
        handler_a = _make_role_handler([("a1", "goal"), ("a2", "observation")])
        handler_b = _make_role_handler([("b1", "goal")])
        resolver.register("ns_a", handler_a)
        resolver.register("ns_b", handler_b)
        result = engine.query_by_role(SemanticRole.GOAL)
        assert sorted(result) == ["a1", "b1"]

    def test_query_by_role_skips_non_handler(self, resolver, engine):
        """不支持 Query 的 resolver 被跳过不报错。"""
        def my_resolver(addr: UniversalAddress) -> str:
            return "plain"
        resolver.register("ns_plain", my_resolver)
        handler = _make_role_handler([("i1", "goal")])
        resolver.register("ns_handler", handler)
        result = engine.query_by_role(SemanticRole.GOAL)
        assert result == ["i1"]

    def test_query_by_role_emits_event(self, resolver):
        """query_by_role 发射 INFORMATION_QUERIED。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)
        handler = _make_role_handler([("g1", "goal")])
        resolver.register("ns", handler)

        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        engine.query_by_role(SemanticRole.GOAL, namespace="ns")
        assert len(events) == 1
        assert events[0].payload["operation"] == "query_by_role"
        assert events[0].payload["role"] == "goal"

    def test_query_by_state_returns_filtered(self, resolver, engine):
        """按 InformationState 过滤。"""
        handler = _make_state_handler([("d1", "created"), ("a1", "validated")])
        resolver.register("ns", handler)
        result = engine.query_by_state(InformationState.CREATED, namespace="ns")
        assert result == ["d1"]

    def test_query_by_state_emits_event(self, resolver):
        """query_by_state 发射 INFORMATION_QUERIED。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)
        handler = _make_state_handler([("a1", "validated")])
        resolver.register("ns", handler)

        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        engine.query_by_state(InformationState.VALIDATED, namespace="ns")
        assert len(events) == 1
        assert events[0].payload["operation"] == "query_by_state"

    def test_query_all_returns_all(self, resolver, engine):
        """query_all 列出 namespace 中所有信息。"""
        handler = _make_list_handler(["item1", "item2", "item3"])
        resolver.register("ns", handler)
        result = engine.query_all("ns")
        assert result == ["item1", "item2", "item3"]

    def test_query_all_empty_namespace_raises(self, engine):
        """空 namespace 引发 ValueError。"""
        with pytest.raises(ValueError, match="namespace"):
            engine.query_all("")

    def test_query_all_emits_event(self, resolver):
        """query_all 发射 INFORMATION_QUERIED。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)
        handler = _make_list_handler(["x"])
        resolver.register("ns", handler)

        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        engine.query_all("ns")
        assert len(events) == 1
        assert events[0].payload["operation"] == "query_all"

    def test_query_all_no_results_for_unregistered(self, engine, resolver):
        """未注册的 namespace 返回空列表。"""
        result = engine.query_all("nonexistent")
        assert result == []

    def test_event_payload_contains_address_info(self, resolver):
        """query 事件 payload 包含 namespace 和 address_id。"""
        from ocos.events.event_bus import EventBus

        bus = EventBus()
        engine = RetrievalEngine(resolver, event_bus=bus)

        def my_resolver(addr: UniversalAddress) -> str:
            return "ok"
        resolver.register("ns", my_resolver)

        events = []

        def on_event(event):
            events.append(event)

        bus.subscribe(EventType.INFORMATION_QUERIED, on_event)
        addr = UniversalAddress(namespace="ns", type="goal", id="g42")
        engine.query(addr)
        assert events[0].payload["namespace"] == "ns"
        assert events[0].payload["address_id"] == "g42"
