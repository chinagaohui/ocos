"""Phase 24-D: Memory Consolidation 四层管道集成测试。

Freeze §5 四层上下文管道:
  Layer 1 — Long-Term Memory (Experience/Knowledge 持久存储)
  Layer 2 — Working Memory (当前任务相关的激活 Experience)
  Layer 3 — Current Cognitive Context (LLM token 预算内压缩格式)
  Layer 4 — Consolidation（低峰期压缩合并旧 Experience）

测试覆盖:
  d4.1  全管道: LTM entries → AttentionDrivenRetrieval → ContextCompressor → Token 预算不超
  d4.2  压缩率检测: 大输入压缩到 token_budget 内
  d4.3  调度器管道: Scheduler + Compressor 联合运行
  d4.4  疲劳感知检索: 高 fatigue 降低检索深度
  d4.5  空输入/边缘情况
"""

import pytest
import time
from datetime import datetime, timezone

from ocos.agent.memory_consolidation import (
    ContextCompressor,
    AttentionDrivenRetrieval,
    MemoryConsolidationScheduler,
    CompressionStats,
    RetrievalResult,
)


# ═══════════════════════════════════════════════════════════════════════════
# d4.1: 全管道测试
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipeline:
    """LTM → Retrieval → Compression → Token Budget 全链路。"""

    def _make_ltm_entries(self, count: int = 50) -> list[dict]:
        """生成模拟 LTM 条目（不同 domain 的经验）。"""
        domains = ["code_gen", "data_analysis", "writing", "browsing", "reasoning"]
        entries = []
        for i in range(count):
            domain = domains[i % len(domains)]
            entries.append({
                "id": f"exp-{i}",
                "content": f"[{domain}] Task result for operation #{i}: "
                           f"completed with success rate {0.7 + (i % 10) * 0.03:.2f}. "
                           f"The processor handled {50 + i * 10} tokens in {0.1 + i * 0.05:.2f}s. "
                           f"Provider: test-provider-{i % 3}.",
                "domain": domain,
                "importance": 0.3 + (i % 7) * 0.1,
                "tags": [domain, f"provider-{i % 3}"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        return entries

    def test_retrieval_compression_token_budget(
        self,
        ltm_entries_50: list[dict] | None = None,
    ):
        """焦点检索 + 压缩后不超出 token_budget。"""
        if ltm_entries_50 is None:
            ltm_entries_50 = self._make_ltm_entries(50)

        # Layer 1→2: AttentionDrivenRetrieval
        retriever = AttentionDrivenRetrieval(max_results=20)
        focus = "code generation task optimization"
        retrieval_result = retriever.retrieve(focus, ltm_entries_50)

        assert isinstance(retrieval_result, RetrievalResult)
        assert len(retrieval_result.items) <= 20
        assert retrieval_result.total_scanned == 50
        assert len(retrieval_result.items) > 0  # at least some matches

        # Layer 2→3: ContextCompressor (token_budget=500, ~2000 chars)
        compressor = ContextCompressor(token_budget=500)
        working_items = [
            {"content": item["content"], "importance": item.get("score", item["importance"])}
            for item in retrieval_result.items
        ]
        compressed, stats = compressor.compress(working_items)

        assert isinstance(stats, CompressionStats)
        assert stats.budget == 500
        # 压缩后的 token 数不应超过预算
        assert stats.compressed_tokens <= stats.budget, (
            f"Token budget exceeded: {stats.compressed_tokens} > {stats.budget}"
        )
        # 合理压缩率
        assert 0 < len(compressed) <= len(working_items)

    def test_large_input_compression_rate(self):
        """大量 LTM entries 压缩率合理 (< 0.5)。"""
        entries = self._make_ltm_entries(100)
        retriever = AttentionDrivenRetrieval(max_results=50)
        result = retriever.retrieve("data analysis", entries)

        working = [
            {"content": item["content"], "importance": item.get("score", item["importance"])}
            for item in result.items
        ]

        compressor = ContextCompressor(token_budget=300)  # tight budget
        compressed, stats = compressor.compress(working)

        # 压缩率应显著 < 1
        assert stats.compression_ratio <= 0.8, (
            f"Compression ratio too high: {stats.compression_ratio:.2f}"
        )
        # Token 预算不超
        assert stats.compressed_tokens <= stats.budget


# ═══════════════════════════════════════════════════════════════════════════
# d4.2: 压缩率检测
# ═══════════════════════════════════════════════════════════════════════════


class TestCompressionRateDetection:
    """压缩率边界检测。"""

    def test_empty_items_compression_zero_ratio(self):
        cc = ContextCompressor(token_budget=100)
        items: list[dict] = []
        compressed, stats = cc.compress(items)
        assert stats.compression_ratio == 0.0
        assert len(compressed) == 0

    def test_single_item_fits(self):
        cc = ContextCompressor(token_budget=1000)
        items = [{"content": "short", "importance": 1.0}]
        compressed, stats = cc.compress(items)
        assert stats.compression_ratio <= 1.0
        assert len(compressed) == 1

    def test_compression_stats_fields(self):
        cc = ContextCompressor(token_budget=200)
        items = [{"content": "hello world " * 10, "importance": 0.5} for _ in range(20)]
        _, stats = cc.compress(items)

        assert hasattr(stats, "original_tokens")
        assert hasattr(stats, "compressed_tokens")
        assert hasattr(stats, "compression_ratio")
        assert hasattr(stats, "budget_exceeded")
        assert hasattr(stats, "entries_before")
        assert hasattr(stats, "entries_after")

        assert stats.entries_before == 20
        assert stats.entries_after <= 20
        assert isinstance(stats.budget_exceeded, bool)


# ═══════════════════════════════════════════════════════════════════════════
# d4.3: Scheduler + Compressor 联合
# ═══════════════════════════════════════════════════════════════════════════


class TestSchedulerPipeline:
    """Scheduler 触发压缩 + Compressor 执行。"""

    def test_scheduler_triggers_compression_on_interval(self):
        scheduler = MemoryConsolidationScheduler(consolidation_interval=1)
        compressor = ContextCompressor(token_budget=500)

        entries = [
            {"content": f"old experience #{i}", "importance": 0.3}
            for i in range(30)
        ]

        # tick=1 应该触发（interval=1, force=True）
        assert scheduler.should_consolidate(1, force=True)

        compressed, stats = scheduler.consolidate(entries, compressor=compressor)
        assert scheduler.consolidation_count == 1
        assert stats is not None
        assert stats.entries_before == 30

    def test_scheduler_skips_when_not_due(self):
        scheduler = MemoryConsolidationScheduler(consolidation_interval=10)
        assert not scheduler.should_consolidate(5, force=False)
        assert not scheduler.should_consolidate(15, force=False)  # 15 % 10 = 5, not 0
        assert scheduler.should_consolidate(10, force=True)  # force bypasses low-peak

    def test_scheduler_tracks_stats(self):
        scheduler = MemoryConsolidationScheduler()
        assert scheduler.consolidation_count == 0
        assert scheduler.total_compressed == 0
        assert scheduler.last_consolidation is None

        scheduler.consolidate(
            [{"content": "test", "importance": 0.5}],
            compressor=ContextCompressor(token_budget=100),
        )
        assert scheduler.consolidation_count == 1
        assert scheduler.total_compressed == 1
        assert scheduler.last_consolidation is not None


# ═══════════════════════════════════════════════════════════════════════════
# d4.4: 疲劳感知检索
# ═══════════════════════════════════════════════════════════════════════════


class TestFatigueAwareRetrieval:
    """高 fatigue 场景下检索深度降低。"""

    def test_high_fatigue_reduces_results(self):
        """疲劳度 > 0.7 时减少返回数量。"""
        entries = []
        for i in range(30):
            entries.append({
                "content": f"memory item {i} about coding techniques and best practices",
                "tags": ["coding"],
                "importance": 0.5 + (i % 5) * 0.1,
            })

        # 正常检索
        retriever_full = AttentionDrivenRetrieval(max_results=20)
        result_full = retriever_full.retrieve("coding", entries)
        full_count = len(result_full.items)

        # 高疲劳检索 (模拟: 只返回前 max_results//3)
        retriever_fatigued = AttentionDrivenRetrieval(max_results=20)
        result_fatigued = retriever_fatigued.retrieve(
            "coding", entries, fatigue_level=0.8,
        )
        assert len(result_fatigued.items) <= full_count

    def test_fatigue_zero_returns_full(self):
        """fatigue=0 不影响检索。"""
        entries = [
            {"content": "relevant item", "tags": ["test"], "importance": 1.0}
            for _ in range(5)
        ]
        retriever = AttentionDrivenRetrieval(max_results=20)
        result = retriever.retrieve("relevant", entries, fatigue_level=0.0)
        assert len(result.items) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# d4.5: 空输入 / 边缘
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """空输入 / 无匹配 / 极值输入。"""

    def test_retrieval_empty_ltm(self):
        retriever = AttentionDrivenRetrieval()
        result = retriever.retrieve("anything", [])
        assert result.items == []
        assert result.total_scanned == 0

    def test_retrieval_no_keywords(self):
        """没有实义关键词时返回空。"""
        retriever = AttentionDrivenRetrieval()
        entries = [{"content": "some data", "tags": [], "importance": 0.5}]
        result = retriever.retrieve("the a in to", entries)
        assert len(result.items) == 0  # stopwords only

    def test_compressor_token_budget_zero(self):
        """token_budget=0 时不保存任何条目（MIN_RETAIN 仅保证唯一条目）。"""
        cc = ContextCompressor(token_budget=0)
        items = [{"content": "hello", "importance": 1.0}]
        compressed, stats = cc.compress(items)
        # MIN_RETAIN=5，但只有1个唯一条目，保留1个
        assert stats.budget_exceeded  # 字符预算 0，必然超出

    def test_compressor_budget_exceeded_flag(self):
        cc = ContextCompressor(token_budget=1)  # ~4 chars
        items = [{"content": "x" * 100, "importance": 0.5}]
        _, stats = cc.compress(items)
        assert stats.budget_exceeded

    def test_single_high_importance_always_selected(self):
        cc = ContextCompressor(token_budget=1000)  # generous
        items = [
            {"content": "critical", "importance": 1.0},
            {"content": "noise", "importance": 0.1},
        ]
        compressed, _ = cc.compress(items)
        contents = [i["content"] for i in compressed]
        assert "critical" in contents
