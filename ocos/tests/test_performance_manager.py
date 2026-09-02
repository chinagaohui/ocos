"""Phase Z: PerformanceManager 单元测试。"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.performance.manager import (
    PerformanceManager,
    SmartCache,
    AsyncBatchProcessor,
    BulkPersistence,
    PerformanceProfiler,
    BatchConfig,
)


class TestSmartCache:
    """SmartCache 测试。"""

    def test_set_and_get(self):
        cache = SmartCache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_miss(self):
        cache = SmartCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = SmartCache(default_ttl=0.1)  # 100ms TTL
        cache.set("key", "value")
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_lru_eviction(self):
        cache = SmartCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # 应该淘汰最旧的 a

        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_delete(self):
        cache = SmartCache()
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None
        assert cache.delete("missing") is False

    def test_clear(self):
        cache = SmartCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_get_stats(self):
        cache = SmartCache(max_size=100)
        cache.set("k", "v")
        cache.get("k")
        cache.get("missing")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["max_size"] == 100

    def test_custom_ttl(self):
        cache = SmartCache(default_ttl=60)
        cache.set("key", "value", ttl=0.05)  # 50ms TTL
        time.sleep(0.06)
        # 自定义 TTL 50ms 已过期
        assert cache.get("key") is None


class TestAsyncBatchProcessor:
    """AsyncBatchProcessor 测试。"""

    @pytest.mark.asyncio
    async def test_basic_processing(self):
        results = []

        def process_fn(batch):
            results.extend(batch)
            return len(batch)

        processor = AsyncBatchProcessor(process_fn, BatchConfig(batch_size=3, flush_interval=0.05))
        await processor.start()

        await processor.add(1)
        await processor.add(2)
        await processor.add(3)  # 触发批量处理

        await asyncio.sleep(0.2)  # 等待处理
        await processor.stop()

        assert len(results) == 3
        assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_flush(self):
        results = []

        def process_fn(batch):
            results.extend(batch)

        processor = AsyncBatchProcessor(process_fn, BatchConfig(batch_size=10))
        await processor.start()

        await processor.add(1)
        await processor.add(2)
        await processor.flush()

        await processor.stop()

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self):
        async def process_fn(batch):
            return len(batch)

        processor = AsyncBatchProcessor(process_fn)
        stats = processor.get_stats()
        assert stats["items_processed"] == 0
        assert stats["batches_sent"] == 0


class TestBulkPersistence:
    """BulkPersistence 测试。"""

    def test_enqueue_and_flush(self):
        saved = []

        def save_fn(batch):
            saved.extend(batch)

        bp = BulkPersistence(save_fn, batch_size=5)
        bp.enqueue({"id": 1})
        bp.enqueue({"id": 2})
        bp.flush()

        assert len(saved) == 2
        assert saved[0]["id"] == 1

    def test_auto_flush_on_batch_size(self):
        saved = []

        def save_fn(batch):
            saved.extend(batch)

        bp = BulkPersistence(save_fn, batch_size=3)
        bp.enqueue({"id": 1})
        bp.enqueue({"id": 2})
        bp.enqueue({"id": 3})  # 达到 batch_size，自动刷新

        assert len(saved) == 3

    def test_flush_failure_requeues(self):
        call_count = [0]

        def save_fn(batch):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Simulated failure")

        bp = BulkPersistence(save_fn, batch_size=10)
        bp.enqueue({"id": 1})
        bp.flush()  # 第一次失败

        # 数据应该重新入队
        assert len(bp._pending) == 1
        assert bp._pending[0]["id"] == 1

    def test_get_stats(self):
        def save_fn(batch):
            pass

        bp = BulkPersistence(save_fn)
        bp.enqueue({"id": 1})
        stats = bp.get_stats()
        assert stats["items_queued"] == 1
        assert stats["pending_count"] == 1


class TestPerformanceProfiler:
    """PerformanceProfiler 测试。"""

    def test_record_operation(self):
        profiler = PerformanceProfiler()
        profiler.start_timer("test_op")
        time.sleep(0.05)
        duration = profiler.stop_timer("test_op")

        assert duration > 40  # 至少 40ms
        stats = profiler.get_stats()
        assert stats["total_operations"] == 1

    def test_get_slowest(self):
        profiler = PerformanceProfiler()
        profiler.start_timer("slow")
        time.sleep(0.1)
        profiler.stop_timer("slow")

        profiler.start_timer("fast")
        time.sleep(0.01)
        profiler.stop_timer("fast")

        slowest = profiler.get_slowest(1)
        assert slowest[0].operation == "slow"

    def test_get_stats_empty(self):
        profiler = PerformanceProfiler()
        stats = profiler.get_stats()
        assert stats["total_operations"] == 0
        assert stats["avg_duration_ms"] == 0

    def test_reset(self):
        profiler = PerformanceProfiler()
        profiler.start_timer("op")
        time.sleep(0.01)
        profiler.stop_timer("op")

        profiler.reset()
        stats = profiler.get_stats()
        assert stats["total_operations"] == 0

    def test_error_tracking(self):
        profiler = PerformanceProfiler()
        profiler.start_timer("failing_op")
        time.sleep(0.01)
        profiler.stop_timer("failing_op", success=False)

        stats = profiler.get_stats()
        assert stats["errors"] == 1


class TestPerformanceManager:
    """PerformanceManager 测试。"""

    def test_create(self):
        pm = PerformanceManager()
        assert pm.cache is not None
        assert pm.profiler is not None

    def test_get_cache(self):
        pm = PerformanceManager()
        cache = pm.get_cache()
        assert isinstance(cache, SmartCache)

    def test_create_batch_processor(self):
        pm = PerformanceManager()

        def process_fn(batch):
            return len(batch)

        processor = pm.create_batch_processor("test", process_fn)
        assert processor is not None
        # 验证处理器有 stats
        stats = processor.get_stats()
        assert "items_processed" in stats

    def test_get_stats(self):
        pm = PerformanceManager()
        stats = pm.get_stats()
        assert "cache" in stats
        assert "profiler" in stats

    def test_reset_profiler(self):
        pm = PerformanceManager()
        pm.profiler.start_timer("op")
        time.sleep(0.01)
        pm.profiler.stop_timer("op")

        pm.reset_profiler()
        assert pm.profiler.get_stats()["total_operations"] == 0

    @pytest.mark.asyncio
    async def test_start_stop_all(self):
        pm = PerformanceManager()

        def process_fn(batch):
            return len(batch)

        processor = pm.create_batch_processor("test", process_fn)
        await processor.start()
        await asyncio.sleep(0.05)
        await processor.stop()
        # 不崩溃即通过


class TestEdgeCases:
    """边界条件测试。"""

    def test_cache_with_many_keys(self):
        cache = SmartCache(max_size=10)
        for i in range(100):
            cache.set(f"key{i}", i)

        # 只有最后 10 个应该保留
        assert cache.get("key99") == 99
        assert cache.get("key90") == 90
        # 最老的应该被淘汰
        assert cache.get("key0") is None

    def test_profiler_max_entries(self):
        profiler = PerformanceProfiler(max_entries=5)
        for i in range(20):
            profiler.start_timer(f"op{i}")
            time.sleep(0.001)
            profiler.stop_timer(f"op{i}")

        stats = profiler.get_stats()
        assert stats["total_entries"] <= 5

    def test_bulk_persistence_large_batch(self):
        saved = []

        def save_fn(batch):
            saved.extend(batch)

        bp = BulkPersistence(save_fn, batch_size=100)
        for i in range(250):
            bp.enqueue({"id": i})
            if (i + 1) % 100 == 0:
                bp.flush()  # 定期手动刷新

        # 确保最后的数据也被刷新
        bp.flush()

        assert len(saved) == 250
