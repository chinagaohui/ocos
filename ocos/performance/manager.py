"""Phase Z: PerformanceManager — 统一性能优化管理。

整合现有性能优化组件：
- RuntimeLoop: 同步/异步双模式循环
- 各类 Lock: 线程安全
- AttentionCache: 注意力缓存

新增能力：
- AsyncBatchProcessor: 异步批处理器
- SmartCache: 智能缓存（LRU/TTL）
- BulkPersistence: 批量持久化
- PerformanceProfiler: 性能分析器

启动方式:
    from ocos.performance.manager import PerformanceManager
    pm = PerformanceManager()
    pm.start()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ── SmartCache ──────────────────────────────────────────────────────────────


class SmartCache:
    """智能缓存（LRU + TTL）。"""

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,  # 5分钟
    ):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }

    def get(self, key: str, ttl: Optional[float] = None) -> Optional[Any]:
        """获取缓存值。"""
        ttl = ttl if ttl is not None else self._default_ttl
        now = time.monotonic()

        if key in self._cache:
            value, expire_at = self._cache[key]
            if now < expire_at:
                # 移动到末尾（最新使用）
                self._cache.move_to_end(key)
                self._stats["hits"] += 1
                return value
            else:
                # 过期，删除
                del self._cache[key]

        self._stats["misses"] += 1
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """设置缓存值。"""
        ttl = ttl if ttl is not None else self._default_ttl
        now = time.monotonic()
        expire_at = now + ttl

        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = (value, expire_at)
        else:
            if len(self._cache) >= self._max_size:
                # 淘汰最旧项
                self._cache.popitem(last=False)
                self._stats["evictions"] += 1
            self._cache[key] = (value, expire_at)

    def delete(self, key: str) -> bool:
        """删除缓存项。"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计。"""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            **self._stats,
            "size": len(self._cache),
            "hit_rate": round(hit_rate, 3),
            "max_size": self._max_size,
            "default_ttl": self._default_ttl,
        }


# ── AsyncBatchProcessor ────────────────────────────────────────────────────


@dataclass
class BatchConfig:
    """批处理配置。"""
    batch_size: int = 10
    flush_interval: float = 1.0  # 秒
    max_queue_size: int = 1000


class AsyncBatchProcessor:
    """异步批处理器。

    将多个小操作批量执行，减少 I/O 次数。
    """

    def __init__(
        self,
        process_fn: Callable[[list[Any]], Any],
        config: Optional[BatchConfig] = None,
    ):
        self._process_fn = process_fn
        self._config = config or BatchConfig()
        self._queue: list[Any] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = {
            "items_processed": 0,
            "batches_sent": 0,
            "total_latency_ms": 0.0,
        }

    async def start(self) -> None:
        """启动批处理循环。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Batch processor started")

    async def stop(self) -> None:
        """停止批处理循环。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Batch processor stopped")

    async def add(self, item: Any) -> None:
        """添加待处理项。"""
        self._queue.append(item)
        if len(self._queue) >= self._config.batch_size:
            await self._flush()

    async def flush(self) -> None:
        """强制刷新队列。"""
        await self._flush()

    async def _process_loop(self) -> None:
        """批处理主循环。"""
        while self._running:
            try:
                await asyncio.sleep(self._config.flush_interval / 2)
                if self._queue:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Batch processing error: %s", e)

    async def _flush(self) -> None:
        """执行批处理。"""
        if not self._queue:
            return

        batch = self._queue[:self._config.batch_size]
        self._queue = self._queue[self._config.batch_size:]

        start = time.monotonic()
        try:
            result = self._process_fn(batch)
            elapsed = (time.monotonic() - start) * 1000
            self._stats["items_processed"] += len(batch)
            self._stats["batches_sent"] += 1
            self._stats["total_latency_ms"] += elapsed
            logger.debug("Batch processed: %d items in %.1fms", len(batch), elapsed)
            return result
        except Exception as e:
            logger.error("Batch processing failed: %s", e)
            # 失败项重新入队
            self._queue = batch + self._queue
            raise

    def get_stats(self) -> dict[str, Any]:
        """获取处理统计。"""
        avg_latency = (
            self._stats["total_latency_ms"] / self._stats["batches_sent"]
            if self._stats["batches_sent"] > 0 else 0
        )
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "avg_latency_ms": round(avg_latency, 1),
            "batch_size": self._config.batch_size,
            "flush_interval": self._config.flush_interval,
        }


# ── BulkPersistence ─────────────────────────────────────────────────────────


class BulkPersistence:
    """批量持久化管理器。"""

    def __init__(
        self,
        save_fn: Callable[[list[dict[str, Any]]], None],
        batch_size: int = 50,
        flush_interval: float = 2.0,
    ):
        self._save_fn = save_fn
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._pending: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()
        self._stats = {
            "items_queued": 0,
            "items_saved": 0,
            "flush_count": 0,
            "errors": 0,
        }

    def enqueue(self, data: dict[str, Any]) -> None:
        """入队待持久化数据。"""
        self._pending.append(data)
        self._stats["items_queued"] += 1

        # 自动触发刷新
        now = time.monotonic()
        if (
            len(self._pending) >= self._batch_size
            or (now - self._last_flush) >= self._flush_interval
        ):
            self.flush()

    def flush(self) -> bool:
        """强制刷新。"""
        if not self._pending:
            return True

        batch = self._pending[:]
        self._pending.clear()
        self._last_flush = time.monotonic()

        try:
            self._save_fn(batch)
            self._stats["items_saved"] += len(batch)
            self._stats["flush_count"] += 1
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Bulk persistence flush failed: %s", e)
            # 重新入队
            self._pending.extend(batch)
            return False

    def get_stats(self) -> dict[str, Any]:
        """获取持久化统计。"""
        return {
            **self._stats,
            "pending_count": len(self._pending),
            "batch_size": self._batch_size,
            "flush_interval": self._flush_interval,
        }


# ── PerformanceProfiler ─────────────────────────────────────────────────────


@dataclass
class ProfilerEntry:
    """性能分析记录。"""
    operation: str
    duration_ms: float
    timestamp: float
    success: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """性能分析器。"""

    def __init__(self, max_entries: int = 1000):
        self._entries: list[ProfilerEntry] = []
        self._max_entries = max_entries
        self._timers: dict[str, float] = {}
        self._stats = {
            "total_operations": 0,
            "total_duration_ms": 0.0,
            "errors": 0,
        }

    def start_timer(self, operation: str) -> None:
        """开始计时。"""
        self._timers[operation] = time.monotonic()

    def stop_timer(self, operation: str, success: bool = True, **kwargs) -> float:
        """停止计时并记录。"""
        if operation not in self._timers:
            return 0.0

        start = self._timers.pop(operation)
        duration_ms = (time.monotonic() - start) * 1000

        entry = ProfilerEntry(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            metadata=kwargs,
        )
        self._record(entry)
        return duration_ms

    def _record(self, entry: ProfilerEntry) -> None:
        """记录分析结果。"""
        self._entries.append(entry)
        self._stats["total_operations"] += 1
        self._stats["total_duration_ms"] += entry.duration_ms

        if not entry.success:
            self._stats["errors"] += 1

        # 限制内存中的条目数
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries // 2:]

    def get_slowest(self, n: int = 10) -> list[ProfilerEntry]:
        """获取最慢的操作。"""
        return sorted(self._entries, key=lambda e: e.duration_ms, reverse=True)[:n]

    def get_stats(self) -> dict[str, Any]:
        """获取性能统计。"""
        entries = self._entries
        if not entries:
            return {**self._stats, "avg_duration_ms": 0, "p99_duration_ms": 0}

        durations = [e.duration_ms for e in entries]
        sorted_durations = sorted(durations)
        p99_idx = int(len(sorted_durations) * 0.99)

        return {
            **self._stats,
            "avg_duration_ms": round(sum(durations) / len(durations), 1),
            "p99_duration_ms": round(sorted_durations[min(p99_idx, len(sorted_durations) - 1)], 1),
            "max_duration_ms": round(max(durations), 1),
            "total_entries": len(entries),
        }

    def reset(self) -> None:
        """重置分析器。"""
        self._entries.clear()
        self._timers.clear()
        self._stats = {
            "total_operations": 0,
            "total_duration_ms": 0.0,
            "errors": 0,
        }


# ── PerformanceManager ──────────────────────────────────────────────────────


class PerformanceManager:
    """统一性能优化管理器。

    职责：
    1. 智能缓存管理
    2. 异步批处理
    3. 批量持久化
    4. 性能分析
    """

    def __init__(
        self,
        cache_max_size: int = 1000,
        cache_ttl: float = 300.0,
        batch_size: int = 10,
        bulk_batch_size: int = 50,
    ):
        self.cache = SmartCache(max_size=cache_max_size, default_ttl=cache_ttl)
        self.profiler = PerformanceProfiler()
        self._batch_size = batch_size
        self._bulk_batch_size = bulk_batch_size

        self._batch_processors: dict[str, AsyncBatchProcessor] = {}
        self._bulk_persistences: dict[str, BulkPersistence] = {}
        self._bulk_batch_size = bulk_batch_size

    def get_cache(self, name: str = "default") -> SmartCache:
        """获取命名缓存。"""
        # 使用同一个 SmartCache 实例（简化设计）
        return self.cache

    def create_batch_processor(
        self,
        name: str,
        process_fn: Callable[[list[Any]], Any],
        batch_size: Optional[int] = None,
    ) -> AsyncBatchProcessor:
        """创建批处理器。"""
        config = BatchConfig(
            batch_size=batch_size or self._batch_size,
        )
        processor = AsyncBatchProcessor(process_fn, config)
        self._batch_processors[name] = processor
        return processor

    def create_bulk_persistence(
        self,
        name: str,
        save_fn: Callable[[list[dict[str, Any]]], None],
        batch_size: Optional[int] = None,
    ) -> BulkPersistence:
        """创建批量持久化器。"""
        persistence = BulkPersistence(
            save_fn=save_fn,
            batch_size=batch_size or self._bulk_batch_size,
        )
        self._bulk_persistences[name] = persistence
        return persistence

    async def start_all(self) -> None:
        """启动所有批处理器。"""
        for name, processor in self._batch_processors.items():
            await processor.start()
            logger.info("Started batch processor: %s", name)

    async def stop_all(self) -> None:
        """停止所有批处理器。"""
        for name, processor in self._batch_processors.items():
            await processor.stop()
            logger.info("Stopped batch processor: %s", name)

    def get_stats(self) -> dict[str, Any]:
        """获取性能统计。"""
        return {
            "cache": self.cache.get_stats(),
            "profiler": self.profiler.get_stats(),
            "batch_processors": {
                name: p.get_stats()
                for name, p in self._batch_processors.items()
            },
            "bulk_persistences": {
                name: p.get_stats()
                for name, p in self._bulk_persistences.items()
            },
        }

    def reset_profiler(self) -> None:
        """重置分析器。"""
        self.profiler.reset()


# ── 工厂函数 ────────────────────────────────────────────────────────────────


def create_performance_manager(
    cache_max_size: int = 1000,
    batch_size: int = 10,
    **kwargs,
) -> PerformanceManager:
    """创建 PerformanceManager。"""
    return PerformanceManager(
        cache_max_size=cache_max_size,
        batch_size=batch_size,
        **kwargs,
    )
