"""Phase 23-A: Capability 子系统集成测试 (23a7)。

覆盖: Descriptor/Provider/Registry/Discovery/Adapter 全链路。
"""
import pytest

from ocos.capability.descriptor import (
    CapabilityDescriptor,
    CapabilityCategory,
    CapabilityStatus,
)
from ocos.capability.provider import (
    ProviderDescriptor,
    ProviderType,
    ProviderStatus,
)
from ocos.capability.registry import CapabilityRegistry
from ocos.capability.discovery import CapabilityDiscovery
from ocos.capability.adapter import (
    CapabilityAdapter,
    AdapterResult,
    AdapterStatus,
    RetryPolicy,
)


# ── CapabilityDescriptor ─────────────────────────────────────────────


class TestCapabilityDescriptor:
    def test_create_minimal(self):
        desc = CapabilityDescriptor(
            capability_id="test.reasoning",
            name="Test Reasoning",
            category=CapabilityCategory.REASONING,
        )
        assert desc.capability_id == "test.reasoning"
        assert desc.status == CapabilityStatus.DISCOVERED
        assert desc.version == "1.0.0"

    def test_frozen_immutable(self):
        desc = CapabilityDescriptor(capability_id="x", name="x")
        # frozen=True prevents reassignment of attributes
        with pytest.raises(Exception):
            desc.tags = ["bad"]  # type: ignore  # frozen dataclass prevents this
        # But list mutation on existing reference is still possible (CPython behavior)
        # This test verifies that field-reassignment is blocked
        desc2 = CapabilityDescriptor(capability_id="x", name="x")
        assert desc == desc2  # equality works

    def test_match_tag(self):
        desc = CapabilityDescriptor(capability_id="t1", name="T1", tags=["nlp", "text"])
        assert desc.match_tag("nlp") is True
        assert desc.match_tag("vision") is False

    def test_match_category(self):
        desc = CapabilityDescriptor(capability_id="t2", name="T2", category=CapabilityCategory.PLANNING)
        assert desc.match_category(CapabilityCategory.PLANNING) is True
        assert desc.match_category(CapabilityCategory.REASONING) is False

    def test_with_schema(self):
        desc = CapabilityDescriptor(
            capability_id="t3", name="T3",
            input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
        )
        assert desc.input_schema["type"] == "object"


# ── ProviderDescriptor ──────────────────────────────────────────────


class TestProviderDescriptor:
    def test_create_engine_provider(self):
        prov = ProviderDescriptor(
            provider_id="engines.reasoning",
            name="Reasoning Engine",
            provider_type=ProviderType.ENGINE,
            class_path="ocos.engines.reasoning_engine.ReasoningEngine",
            capabilities=["ocos.reasoning"],
        )
        assert prov.provider_type == ProviderType.ENGINE
        assert prov.is_local is True
        assert prov.is_external is False
        assert prov.singleton is True

    def test_create_external_provider(self):
        prov = ProviderDescriptor(
            provider_id="api.openai",
            name="OpenAI API",
            provider_type=ProviderType.EXTERNAL,
            capabilities=["ocos.reasoning", "ocos.creativity"],
        )
        assert prov.is_external is True
        assert prov.is_local is False


# ── CapabilityRegistry ───────────────────────────────────────────────


class TestCapabilityRegistry:
    @pytest.fixture
    def registry(self):
        return CapabilityRegistry()

    def test_register_capability(self, registry):
        desc = CapabilityDescriptor(capability_id="c1", name="C1")
        registry.register_capability(desc)
        assert registry.capability_count == 1
        assert registry.get_capability("c1") is desc

    def test_register_provider(self, registry):
        prov = ProviderDescriptor(provider_id="p1", name="P1")
        registry.register_provider(prov)
        assert registry.provider_count == 1

    def test_bind_resolve(self, registry):
        desc = CapabilityDescriptor(capability_id="c2", name="C2")
        prov = ProviderDescriptor(provider_id="p2", name="P2")
        registry.register_capability(desc)
        registry.register_provider(prov)
        registry.bind("c2", "p2")

        providers = registry.resolve("c2")
        assert len(providers) == 1
        assert providers[0].provider_id == "p2"

    def test_unregister_capability(self, registry):
        desc = CapabilityDescriptor(capability_id="c3", name="C3")
        registry.register_capability(desc)
        assert registry.unregister_capability("c3") is True
        assert registry.capability_count == 0

    def test_unregister_provider(self, registry):
        prov = ProviderDescriptor(provider_id="p3", name="P3")
        registry.register_provider(prov)
        assert registry.unregister_provider("p3") is True
        assert registry.provider_count == 0

    def test_list_by_category(self, registry):
        for i, cat in enumerate([CapabilityCategory.REASONING, CapabilityCategory.PLANNING]):
            registry.register_capability(
                CapabilityDescriptor(capability_id=f"c{i}", name=f"C{i}", category=cat)
            )
        result = registry.list_capabilities(category=CapabilityCategory.REASONING)
        assert len(result) == 1

    def test_list_by_tag(self, registry):
        registry.register_capability(
            CapabilityDescriptor(capability_id="c5", name="C5", tags=["nlp"])
        )
        registry.register_capability(
            CapabilityDescriptor(capability_id="c6", name="C6", tags=["vision"])
        )
        assert len(registry.find_by_tag("nlp")) == 1

    def test_clear(self, registry):
        registry.register_capability(CapabilityDescriptor(capability_id="c", name="c"))
        registry.register_provider(ProviderDescriptor(provider_id="p", name="p"))
        registry.clear()
        assert registry.capability_count == 0
        assert registry.provider_count == 0


# ── CapabilityDiscovery ──────────────────────────────────────────────


class TestCapabilityDiscovery:
    def test_discovery_creates_registry(self):
        discovery = CapabilityDiscovery()
        assert discovery.registry is not None
        assert discovery.registry.capability_count == 0

    def test_scan_all_engines(self):
        """验证 scan_all 至少不崩溃。"""
        discovery = CapabilityDiscovery()
        registry = discovery.scan_all()
        assert registry is not None

    def test_register_external_capability(self):
        discovery = CapabilityDiscovery()
        desc = discovery.register_external_capability(
            capability_id="ext.test",
            name="External Test",
            category=CapabilityCategory.CUSTOM,
            provider_id="ext.provider",
            provider_name="External Provider",
        )
        assert desc.capability_id == "ext.test"
        assert discovery.registry.capability_count == 1
        assert discovery.registry.provider_count == 1


# ── CapabilityAdapter ────────────────────────────────────────────────


class TestCapabilityAdapter:
    def test_execute_with_callable(self):
        """callable 实例作为 provider。"""
        def dummy_execute(**kwargs):
            return {"status": "ok"}

        adapter = CapabilityAdapter(
            capability_id="test.func",
            provider_id="p.func",
            instance=dummy_execute,
        )
        result = adapter.execute()
        assert result.success is True
        assert result.output["status"] == "ok"
        assert result.attempt == 1

    def test_execute_with_object(self):
        """对象实例有 execute() 方法。"""
        class FakeEngine:
            def execute(self, **kwargs):
                return {"result": 42}

        adapter = CapabilityAdapter(
            capability_id="test.obj",
            provider_id="p.obj",
            instance=FakeEngine(),
        )
        result = adapter.execute()
        assert result.success is True
        assert result.output["result"] == 42

    def test_execute_no_instance_raises(self):
        adapter = CapabilityAdapter(capability_id="x", provider_id="p")
        result = adapter.execute()
        assert result.success is False

    def test_retry_with_fallback(self):
        call_count = [0]

        def failing_engine(**kwargs):
            call_count[0] += 1
            raise RuntimeError("always fail")

        def fallback(inputs):
            return AdapterResult(success=True, capability_id="test.fb", output={"fb": "used"})

        adapter = CapabilityAdapter(
            capability_id="test.fb",
            provider_id="p.fb",
            instance=failing_engine,
            retry_policy=RetryPolicy.FIXED,
            max_retries=2,
            retry_base_delay=0.01,
            fallback=fallback,
        )
        result = adapter.execute()
        assert result.success is True
        assert result.output["fb"] == "used"
        assert adapter.status == AdapterStatus.ERROR

    def test_exponential_backoff(self):
        adapter = CapabilityAdapter(
            capability_id="test.exp",
            provider_id="p.exp",
            retry_policy=RetryPolicy.EXPONENTIAL,
            max_retries=2,
            retry_base_delay=0.01,
        )
        assert adapter._compute_delay(1) == 0.01
        assert adapter._compute_delay(2) == 0.02
        assert adapter._compute_delay(3) == 0.04

    def test_linear_backoff(self):
        adapter = CapabilityAdapter(
            capability_id="test.lin",
            provider_id="p.lin",
            retry_policy=RetryPolicy.LINEAR,
            max_retries=2,
            retry_base_delay=0.1,
        )
        assert abs(adapter._compute_delay(1) - 0.1) < 0.001
        assert abs(adapter._compute_delay(3) - 0.3) < 0.001
