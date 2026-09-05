"""Tests for ocos.capability.registry - 能力注册表。"""
import pytest


class TestCapabilityRegistry:
    def test_import(self):
        from ocos.capability.registry import CapabilityRegistry
        assert CapabilityRegistry is not None

    def test_create(self):
        from ocos.capability.registry import CapabilityRegistry
        registry = CapabilityRegistry()
        assert registry is not None

    def test_list_capabilities(self):
        from ocos.capability.registry import CapabilityRegistry
        registry = CapabilityRegistry()
        caps = registry.list_capabilities()
        assert isinstance(caps, list)
