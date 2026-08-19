"""
B5 Resource Manager — 完整测试套件。

覆盖：
- Dataclass 冻结（ResourceUsage / ResourceSlot / ResourceRequestResult / ResourceQuota）
- request 分配 / 超限拒绝 / 配额拒绝
- release / release_by_holder
- get_usage / get_slots 查询
- 配额管理（set_quota / get_quota / remove_quota）
- TTL 过期回收（惰性 + 主动清理）
- Event Bus 事件集成
- 无 Event Bus 降级
- reset
- 边界条件
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from ocos.runtime.resource_manager import (
    DEFAULT_CAPACITY,
    ResourceManager,
    ResourceQuota,
    ResourceRequestResult,
    ResourceSlot,
    ResourceType,
    ResourceUsage,
    _now_iso,
    _slot_is_expired,
)
from ocos.kernel.abi import EventType, SCHEMA_VERSION


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mgr() -> ResourceManager:
    """默认资源管理器（完整容量，无配额，无 Event Bus）。"""
    return ResourceManager()


@pytest.fixture
def mgr_with_quotas() -> ResourceManager:
    """带引擎配额的资源管理器。"""
    return ResourceManager(quotas={
        "engine-alpha": {"cpu": 4.0, "memory": 4096.0},
        "engine-beta": {"cpu": 2.0},
    })


@pytest.fixture
def mgr_with_event_bus() -> ResourceManager:
    """带 Mock Event Bus 的资源管理器。"""
    event_bus = Mock()
    return ResourceManager(event_bus=event_bus)


@pytest.fixture
def mgr_custom_capacity() -> ResourceManager:
    """自定义容量。"""
    return ResourceManager(capacities={"cpu": 2.0, "memory": 512.0})


# ══════════════════════════════════════════════════════════════════════════════
# Dataclass Frozen
# ══════════════════════════════════════════════════════════════════════════════


class TestDataclassFrozen:
    """所有 dataclass 必须是 frozen 不可变的。"""

    def test_resource_usage_frozen(self):
        with pytest.raises(AttributeError):
            ResourceUsage().total = 99

    def test_resource_slot_frozen(self):
        with pytest.raises(AttributeError):
            ResourceSlot().amount = 99

    def test_resource_request_result_frozen(self):
        with pytest.raises(AttributeError):
            ResourceRequestResult().allowed = True

    def test_resource_quota_frozen(self):
        with pytest.raises(AttributeError):
            ResourceQuota().engine_id = "x"

    def test_resource_usage_defaults(self):
        u = ResourceUsage()
        assert u.resource_type == ""
        assert u.total == 0.0
        assert u.reserved == 0.0
        assert u.available == 0.0
        assert u.unit == ""
        assert u.schema_version == SCHEMA_VERSION

    def test_resource_slot_defaults(self):
        s = ResourceSlot()
        assert s.amount == 0.0
        assert s.holder == ""
        assert s.priority == 0
        assert s.ttl_seconds is None
        assert s.schema_version == SCHEMA_VERSION

    def test_resource_request_result_defaults(self):
        r = ResourceRequestResult()
        assert not r.allowed
        assert r.slot is None
        assert r.reason == ""

    def test_resource_quota_defaults(self):
        q = ResourceQuota()
        assert q.engine_id == ""
        assert q.quotas == {}


# ══════════════════════════════════════════════════════════════════════════════
# ResourceManager — 构造与初始化
# ══════════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_default_capacities(self, mgr):
        for rt in ["cpu", "memory", "gpu", "token", "storage"]:
            assert mgr._capacities[rt] == DEFAULT_CAPACITY[rt]

    def test_custom_capacities(self, mgr_custom_capacity):
        assert mgr_custom_capacity._capacities["cpu"] == 2.0
        assert mgr_custom_capacity._capacities["memory"] == 512.0
        # 其余类型使用默认值
        assert mgr_custom_capacity._capacities["gpu"] == 1.0

    def test_initial_usage_all_available(self, mgr):
        usages = mgr.get_usage()
        assert len(usages) == 5
        for u in usages:
            assert u.reserved == 0.0
            assert u.available == u.total

    def test_initial_slots_empty(self, mgr):
        assert mgr.get_slots() == []
        assert mgr.request_count == 0
        assert mgr.release_count == 0


# ══════════════════════════════════════════════════════════════════════════════
# request 核心功能
# ══════════════════════════════════════════════════════════════════════════════


class TestRequest:
    def test_simple_allocation(self, mgr):
        result = mgr.request("cpu", 2.0, holder="engine-x")
        assert result.allowed
        assert result.slot is not None
        assert result.slot.resource_type == "cpu"
        assert result.slot.amount == 2.0
        assert result.slot.holder == "engine-x"
        assert result.slot.ttl_seconds is None
        assert result.reason == ""

    def test_available_decreases_after_request(self, mgr):
        mgr.request("cpu", 4.0, holder="engine-x")
        usage = mgr.get_usage("cpu")[0]
        assert usage.reserved == 4.0
        assert usage.available == 4.0  # 8-4

    def test_exhausted_rejected(self, mgr):
        mgr.request("cpu", 8.0, holder="engine-x")
        result = mgr.request("cpu", 1.0, holder="engine-y")
        assert not result.allowed
        assert result.slot is None
        assert "insufficient" in result.reason
        assert "cpu" in result.reason

    def test_exact_capacity_allowed(self, mgr):
        result = mgr.request("cpu", 8.0, holder="engine-x")
        assert result.allowed

    def test_unknown_resource_type_rejected(self, mgr):
        result = mgr.request("quantum", 1.0, holder="engine-x")
        assert not result.allowed
        assert "unknown resource type" in result.reason

    def test_zero_amount_rejected(self, mgr):
        result = mgr.request("cpu", 0.0, holder="engine-x")
        assert not result.allowed
        assert "invalid amount" in result.reason

    def test_negative_amount_rejected(self, mgr):
        result = mgr.request("cpu", -1.0, holder="engine-x")
        assert not result.allowed

    def test_ttl_slot_created(self, mgr):
        result = mgr.request("memory", 1024, holder="engine-x", ttl=30.0)
        assert result.allowed
        assert result.slot.ttl_seconds == 30.0


# ══════════════════════════════════════════════════════════════════════════════
# 配额管理
# ══════════════════════════════════════════════════════════════════════════════


class TestQuota:
    def test_quota_allows_within_limit(self, mgr_with_quotas):
        result = mgr_with_quotas.request("cpu", 3.0, holder="engine-alpha")
        assert result.allowed

    def test_quota_rejects_exceeded(self, mgr_with_quotas):
        mgr_with_quotas.request("cpu", 4.0, holder="engine-alpha")
        result = mgr_with_quotas.request("cpu", 0.5, holder="engine-alpha")
        assert not result.allowed
        assert "quota exceeded" in result.reason
        assert "engine-alpha" in result.reason

    def test_different_engines_independent_quotas(self, mgr_with_quotas):
        mgr_with_quotas.request("cpu", 4.0, holder="engine-alpha")
        # engine-beta 有 2.0 配额
        result = mgr_with_quotas.request("cpu", 1.0, holder="engine-beta")
        assert result.allowed

    def test_engine_without_quota_unlimited(self, mgr_with_quotas):
        # engine-gamma 没有配额限制
        result = mgr_with_quotas.request("cpu", 8.0, holder="engine-gamma")
        assert result.allowed

    def test_set_quota_dynamic(self, mgr):
        mgr.set_quota("engine-x", {"cpu": 2.0})
        mgr.request("cpu", 2.0, holder="engine-x")
        result = mgr.request("cpu", 0.1, holder="engine-x")
        assert not result.allowed

    def test_set_quota_overwrites(self, mgr_with_quotas):
        mgr_with_quotas.set_quota("engine-alpha", {"cpu": 2.0, "memory": 8192.0})
        # 新配额 cpu=2.0
        mgr_with_quotas.request("cpu", 2.0, holder="engine-alpha")
        result = mgr_with_quotas.request("cpu", 0.1, holder="engine-alpha")
        assert not result.allowed

    def test_get_quota(self, mgr_with_quotas):
        q = mgr_with_quotas.get_quota("engine-alpha")
        assert q["cpu"] == 4.0
        assert q["memory"] == 4096.0

    def test_get_quota_nonexistent(self, mgr_with_quotas):
        assert mgr_with_quotas.get_quota("ghost-engine") == {}

    def test_remove_quota(self, mgr_with_quotas):
        mgr_with_quotas.remove_quota("engine-alpha")
        assert mgr_with_quotas.get_quota("engine-alpha") == {}

    def test_quota_applies_to_release_and_re_request(self, mgr_with_quotas):
        """释放后应能从配额中恢复。"""
        slot = mgr_with_quotas.request("cpu", 4.0, holder="engine-alpha").slot
        mgr_with_quotas.release(slot.slot_id)
        result = mgr_with_quotas.request("cpu", 4.0, holder="engine-alpha")
        assert result.allowed


# ══════════════════════════════════════════════════════════════════════════════
# release 核心功能
# ══════════════════════════════════════════════════════════════════════════════


class TestRelease:
    def test_release_restores_available(self, mgr):
        slot = mgr.request("cpu", 4.0, holder="engine-x").slot
        assert mgr.release(slot.slot_id)
        usage = mgr.get_usage("cpu")[0]
        assert usage.reserved == 0.0
        assert usage.available == 8.0
        assert mgr.release_count == 1

    def test_release_nonexistent_returns_false(self, mgr):
        assert not mgr.release("ghost-slot")

    def test_double_release_returns_false(self, mgr):
        slot = mgr.request("cpu", 1.0, holder="engine-x").slot
        assert mgr.release(slot.slot_id)
        assert not mgr.release(slot.slot_id)

    def test_release_by_holder(self, mgr):
        mgr.request("cpu", 2.0, holder="engine-x")
        mgr.request("memory", 1024, holder="engine-x")
        mgr.request("cpu", 1.0, holder="engine-y")
        count = mgr.release_by_holder("engine-x")
        assert count == 2
        assert mgr.get_slots("engine-x") == []
        # engine-y 的 slot 应仍在
        assert len(mgr.get_slots("engine-y")) == 1

    def test_release_by_holder_nonexistent(self, mgr):
        count = mgr.release_by_holder("ghost")
        assert count == 0


# ══════════════════════════════════════════════════════════════════════════════
# 查询
# ══════════════════════════════════════════════════════════════════════════════


class TestQuery:
    def test_get_usage_single_type(self, mgr):
        mgr.request("cpu", 3.0, holder="engine-x")
        usages = mgr.get_usage("cpu")
        assert len(usages) == 1
        u = usages[0]
        assert u.resource_type == "cpu"
        assert u.total == 8.0
        assert u.reserved == 3.0
        assert u.available == 5.0

    def test_get_usage_all_types(self, mgr):
        usages = mgr.get_usage()
        assert len(usages) == 5
        types = {u.resource_type for u in usages}
        assert types == {"cpu", "memory", "gpu", "token", "storage"}

    def test_get_usage_unknown_type_returns_empty(self, mgr):
        assert mgr.get_usage("quantum") == []

    def test_get_slots_all(self, mgr):
        s1 = mgr.request("cpu", 1.0, holder="engine-x").slot
        s2 = mgr.request("memory", 512, holder="engine-y").slot
        slots = mgr.get_slots()
        assert len(slots) == 2

    def test_get_slots_by_holder(self, mgr):
        s1 = mgr.request("cpu", 1.0, holder="engine-x").slot
        mgr.request("memory", 512, holder="engine-y").slot
        slots = mgr.get_slots("engine-x")
        assert len(slots) == 1
        assert slots[0].slot_id == s1.slot_id

    def test_get_slots_empty_holder(self, mgr):
        assert mgr.get_slots("engine-x") == []

    def test_request_count_tracking(self, mgr):
        mgr.request("cpu", 1.0, holder="x")
        mgr.request("memory", 512, holder="x")
        assert mgr.request_count == 2

    def test_release_count_tracking(self, mgr):
        s1 = mgr.request("cpu", 1.0, holder="x").slot
        s2 = mgr.request("memory", 512, holder="x").slot
        mgr.release(s1.slot_id)
        mgr.release(s2.slot_id)
        assert mgr.release_count == 2


# ══════════════════════════════════════════════════════════════════════════════
# TTL 过期回收
# ══════════════════════════════════════════════════════════════════════════════


class TestTTL:
    def test_slot_not_expired_without_ttl(self):
        slot = ResourceSlot(ttl_seconds=None)
        assert not _slot_is_expired(slot)

    def test_slot_not_expired_recent(self):
        slot = ResourceSlot(ttl_seconds=60.0)
        assert not _slot_is_expired(slot)

    def test_slot_expired_past_ttl(self):
        """手动构造一个早于 TTL 的 slot。"""
        # 设置 5 秒前的时间
        old_ts = (
            datetime.now(timezone.utc).timestamp() - 10
        )
        old_iso = datetime.fromtimestamp(old_ts, tz=timezone.utc).isoformat()
        slot = ResourceSlot(
            acquired_at=old_iso,
            ttl_seconds=2.0,
        )
        # 10 秒 > 2 秒 TTL → 已过期
        assert _slot_is_expired(slot)

    def test_cleanup_expired_during_request(self, mgr):
        """惰性清理：request 时自动清理过期 slot。"""
        old_ts = datetime.now(timezone.utc).timestamp() - 10
        old_iso = datetime.fromtimestamp(old_ts, tz=timezone.utc).isoformat()
        # 直接注入一个过期 slot
        expired_slot = ResourceSlot(
            slot_id="expired-1",
            resource_type="cpu",
            amount=4.0,
            holder="engine-old",
            acquired_at=old_iso,
            ttl_seconds=1.0,
        )
        mgr._slots["expired-1"] = expired_slot

        # request 应触发清理
        result = mgr.request("cpu", 6.0, holder="engine-new")
        assert result.allowed, "不允许：清理过期 slot 后的可用资源应为 8.0"
        assert "expired-1" not in mgr._slots

    def test_cleanup_expired_during_get_usage(self, mgr):
        """惰性清理：get_usage 时自动清理过期 slot。"""
        old_ts = datetime.now(timezone.utc).timestamp() - 10
        old_iso = datetime.fromtimestamp(old_ts, tz=timezone.utc).isoformat()
        expired_slot = ResourceSlot(
            slot_id="expired-2",
            resource_type="memory",
            amount=8000,
            holder="engine-old",
            acquired_at=old_iso,
            ttl_seconds=1.0,
        )
        mgr._slots["expired-2"] = expired_slot

        usages = mgr.get_usage("memory")
        assert usages[0].reserved == 0.0  # 过期 slot 已被清理
        assert "expired-2" not in mgr._slots

    def test_cleanup_expired_external(self, mgr):
        """主动清理：外部直接调用 _cleanup_expired。"""
        old_ts = datetime.now(timezone.utc).timestamp() - 10
        old_iso = datetime.fromtimestamp(old_ts, tz=timezone.utc).isoformat()
        mgr._slots["expired-3"] = ResourceSlot(
            slot_id="expired-3",
            resource_type="cpu",
            amount=2.0,
            holder="engine-old",
            acquired_at=old_iso,
            ttl_seconds=1.0,
        )
        count = mgr._cleanup_expired()
        assert count == 1
        assert "expired-3" not in mgr._slots

    def test_cleanup_expired_slot_emits_release_event(self, mgr_with_event_bus):
        """过期清理时发送 RESOURCE_RELEASED 事件。"""
        old_ts = datetime.now(timezone.utc).timestamp() - 10
        old_iso = datetime.fromtimestamp(old_ts, tz=timezone.utc).isoformat()
        mgr_with_event_bus._slots["expired-4"] = ResourceSlot(
            slot_id="expired-4",
            resource_type="cpu",
            amount=1.0,
            holder="engine-old",
            acquired_at=old_iso,
            ttl_seconds=1.0,
        )
        mgr_with_event_bus._cleanup_expired()
        # 验证发送 RESOURCE_RELEASED
        emitted = [c.args[0] for c in mgr_with_event_bus._event_bus.emit.call_args_list]
        released_events = [e for e in emitted if e.event_type == EventType.RESOURCE_RELEASED]
        assert len(released_events) >= 1
        assert released_events[0].payload["reason"] == "ttl_expired"


# ══════════════════════════════════════════════════════════════════════════════
# Event Bus 集成
# ══════════════════════════════════════════════════════════════════════════════


class TestEventBus:
    def test_release_sends_resource_released_event(self, mgr_with_event_bus):
        slot = mgr_with_event_bus.request("cpu", 1.0, holder="engine-x").slot
        mgr_with_event_bus.release(slot.slot_id)
        emitted = mgr_with_event_bus._event_bus.emit.call_args[0][0]
        assert emitted.event_type == EventType.RESOURCE_RELEASED
        assert emitted.payload["slot_id"] == slot.slot_id

    def test_exhausted_sends_resource_exhausted_event(self, mgr_with_event_bus):
        # 全部占用
        mgr_with_event_bus.request("gpu", 1.0, holder="engine-x")
        result = mgr_with_event_bus.request("gpu", 0.5, holder="engine-y")
        assert not result.allowed
        emitted = mgr_with_event_bus._event_bus.emit.call_args[0][0]
        assert emitted.event_type == EventType.RESOURCE_EXHAUSTED
        assert "insufficient" in emitted.payload["reason"]

    def test_exhausted_event_carries_precise_reason(self, mgr_with_event_bus):
        """拒绝原因应包含精确数字信息。"""
        mgr_with_event_bus.request("gpu", 1.0, holder="engine-x")
        result = mgr_with_event_bus.request("gpu", 0.5, holder="engine-y")
        assert result.reason  # 非空
        assert "gpu" in result.reason
        assert "0.5" in result.reason or "0.50" in result.reason

    def test_quota_exhausted_event_emitted(self, mgr_with_event_bus):
        """配额超限时也发送 RESOURCE_EXHAUSTED 事件。"""
        mgr_with_event_bus.set_quota("engine-x", {"cpu": 2.0})
        mgr_with_event_bus.request("cpu", 2.0, holder="engine-x")
        mgr_with_event_bus.request("cpu", 0.1, holder="engine-x")
        # 最后一次应触发配额超限事件
        calls = mgr_with_event_bus._event_bus.emit.call_args_list
        exhausted = [c.args[0] for c in calls if c.args[0].event_type == EventType.RESOURCE_EXHAUSTED]
        assert len(exhausted) >= 1
        assert "quota exceeded" in exhausted[-1].payload["reason"]

    def test_no_event_bus_graceful_degradation(self, mgr):
        """无 Event Bus 时 request/release 正常运作。"""
        result = mgr.request("cpu", 1.0, holder="engine-x")
        assert result.allowed
        assert mgr.release(result.slot.slot_id)
        assert mgr.release_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# reset
# ══════════════════════════════════════════════════════════════════════════════


class TestReset:
    def test_reset_clears_all_slots(self, mgr):
        mgr.request("cpu", 1.0, holder="x")
        mgr.request("memory", 512, holder="y")
        mgr.reset()
        assert mgr.get_slots() == []
        assert mgr.request_count == 0

    def test_reset_clears_quotas(self, mgr):
        mgr.set_quota("engine-x", {"cpu": 1.0})
        mgr.reset()
        assert mgr.get_quota("engine-x") == {}
        assert mgr.release_count == 0

    def test_reset_restores_all_capacity(self, mgr):
        mgr.request("cpu", 8.0, holder="x")
        mgr.reset()
        assert mgr.get_usage("cpu")[0].available == 8.0


# ══════════════════════════════════════════════════════════════════════════════
# 多引擎共存
# ══════════════════════════════════════════════════════════════════════════════


class TestMultiEngine:
    def test_separate_holders_independent(self, mgr):
        mgr.request("cpu", 4.0, holder="alpha")
        mgr.request("cpu", 4.0, holder="beta")
        # 全部容量被占
        result = mgr.request("cpu", 0.1, holder="gamma")
        assert not result.allowed

    def test_mixed_types_independent(self, mgr):
        mgr.request("cpu", 4.0, holder="alpha")
        mgr.request("memory", 8192, holder="alpha")
        # cpu 还剩 4.0, memory 还剩 8192
        assert mgr.get_usage("cpu")[0].available == 4.0
        assert mgr.get_usage("memory")[0].available == 8192.0

    def test_multi_holder_release_frees_capacity(self, mgr):
        s1 = mgr.request("cpu", 4.0, holder="alpha").slot
        s2 = mgr.request("cpu", 3.0, holder="beta").slot
        mgr.release(s1.slot_id)
        # 释放后 cpu 可用 5.0（8-3）
        assert mgr.get_usage("cpu")[0].available == 5.0


# ══════════════════════════════════════════════════════════════════════════════
# 边界条件
# ══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_empty_holder(self, mgr):
        result = mgr.request("cpu", 1.0, holder="")
        assert result.allowed

    def test_request_amount_equal_total(self, mgr_custom_capacity):
        result = mgr_custom_capacity.request("cpu", 2.0, holder="x")
        assert result.allowed

    def test_request_slightly_above_total(self, mgr_custom_capacity):
        result = mgr_custom_capacity.request("cpu", 2.001, holder="x")
        assert not result.allowed

    def test_custom_capacity_other_types_default(self, mgr_custom_capacity):
        """自定义容量不影响未指定的类型。"""
        result = mgr_custom_capacity.request("gpu", 1.0, holder="x")
        assert result.allowed

    def test_usage_unit_matches(self, mgr):
        u = mgr.get_usage("memory")[0]
        assert u.unit == "MB"
        u = mgr.get_usage("cpu")[0]
        assert u.unit == "cores"
