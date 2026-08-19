"""Phase 24-D: Memory Consolidation Pipeline — LTM→Working→Context 压缩管道。

Freeze §5: 四层记忆上下文模型
  Long-Term Memory → Working Memory → Current Cognitive Context

功能:
  24d1: MemoryConsolidationScheduler — 定时调度（夜间低峰期触发）
  24d2: AttentionDrivenRetrieval — 注意力焦点驱动 LTM 检索
  24d3: ContextCompressor — Working Memory → LLM Token 预算内格式
  24d4: 压缩率统计 + Token 预算不超

约束:
  - 不改变现有 MemoryConsolidator 行为
  - 仅新增压缩/检索能力
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 数据类 ──────────────────────────────────────────────────────────────────────


@dataclass
class CompressionStats:
    """24d4: 压缩统计。"""
    original_tokens: int = 0
    compressed_tokens: int = 0
    compression_ratio: float = 1.0
    budget_exceeded: bool = False
    budget: int = 4096
    entries_before: int = 0
    entries_after: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetrievalResult:
    """24d2: 检索结果。"""
    items: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    total_scanned: int = 0
    retrieval_time_ms: float = 0.0


# ── ContextCompressor ───────────────────────────────────────────────────────────


class ContextCompressor:
    """24d3: Working Memory → LLM Token 预算内的压缩格式。

    策略:
      1. 按 importance 倒序排列
      2. 截取到 token 预算（粗略: 1 token ≈ 4 字符）
      3. 合并相似条目去重
      4. 保留最近 N 条底线（recency bias）
    """

    CHARS_PER_TOKEN = 4  # 粗略估算
    MIN_RETAIN = 5       # 至少保留 5 条

    def __init__(self, token_budget: int = 4096) -> None:
        self.token_budget = token_budget
        self._last_stats: CompressionStats | None = None

    @property
    def last_stats(self) -> CompressionStats | None:
        return self._last_stats

    def compress(self, working_items: list[dict[str, Any]]) -> tuple[list[dict], CompressionStats]:
        """压缩 Working Memory 到 Token 预算内。

        Args:
            working_items: [{"content":..., "importance":..., ...}, ...]

        Returns:
            (compressed_items, stats)
        """
        original_count = len(working_items)
        char_budget = self.token_budget * self.CHARS_PER_TOKEN

        # 1. 按重要性排序
        sorted_items = sorted(
            working_items,
            key=lambda x: x.get("importance", 0.5),
            reverse=True,
        )

        # 2. 截取到字符预算
        selected: list[dict] = []
        char_used = 0

        for item in sorted_items:
            content = str(item.get("content", ""))
            item_chars = len(content)
            if char_used + item_chars <= char_budget:
                selected.append(item)
                char_used += item_chars
            else:
                break

        # 3. 去重（先于 min_retain，避免重复条目浪费预算）
        selected = self._deduplicate(selected)
        seen_keys: set[str] = {str(s.get("content", ""))[:200] for s in selected}

        # 4. 底线: 至少保留 MIN_RETAIN 条唯一条目
        needed = min(self.MIN_RETAIN, original_count) - len(selected)
        if needed > 0:
            for item in sorted_items:
                if needed <= 0:
                    break
                key = str(item.get("content", ""))[:200]
                if key not in seen_keys:
                    selected.append(item)
                    seen_keys.add(key)
                    needed -= 1

        # 统计
        original_chars = sum(len(str(x.get("content", ""))) for x in working_items)
        compressed_chars = sum(len(str(x.get("content", ""))) for x in selected)
        budget_exceeded = compressed_chars > char_budget

        self._last_stats = CompressionStats(
            original_tokens=original_chars // self.CHARS_PER_TOKEN,
            compressed_tokens=compressed_chars // self.CHARS_PER_TOKEN,
            compression_ratio=compressed_chars / max(original_chars, 1),
            budget_exceeded=budget_exceeded,
            budget=self.token_budget,
            entries_before=original_count,
            entries_after=len(selected),
        )

        if budget_exceeded:
            logger.warning(
                "ContextCompressor: budget exceeded (%d > %d chars)",
                compressed_chars, char_budget,
            )

        return selected, self._last_stats

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        """去重：删除 content 完全相同的重复项。"""
        seen: set[str] = set()
        result: list[dict] = []
        for item in items:
            key = str(item.get("content", ""))[:200]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result


# ── AttentionDrivenRetrieval ────────────────────────────────────────────────────


class AttentionDrivenRetrieval:
    """24d2: 注意力焦点驱动 LTM 检索。

    根据当前注意力焦点，从 Long-Term Memory 检索相关经验/知识。

    检索管道:
      1. 从 focus 提取关键词
      2. 模糊匹配 LTM 条目
      3. 按 relevance 排序
      4. 返回 top-N
    """

    def __init__(self, max_results: int = 20) -> None:
        self.max_results = max_results

    def retrieve(
        self,
        focus_description: str,
        ltm_entries: list[dict[str, Any]],
        fatigue_level: float = 0.0,
    ) -> RetrievalResult:
        """检索与焦点相关的 LTM 条目。

        Args:
            focus_description: 注意力焦点描述文本
            ltm_entries: LTM 条目 [{content, tags, importance, ...}, ...]
            fatigue_level:  注意力疲劳度 0.0-1.0，>0.7 时减少返回数量

        Returns:
            RetrievalResult(items=top_n)
        """
        t0 = time.monotonic()

        if not focus_description or not ltm_entries:
            return RetrievalResult(
                query=focus_description,
                total_scanned=0,
                retrieval_time_ms=0.0,
            )

        # 疲劳时减少检索深度
        effective_max = self.max_results
        if fatigue_level > 0.7:
            effective_max = max(1, self.max_results // 3)

        # 提取关键词
        keywords = self._extract_keywords(focus_description)

        # 打分
        scored: list[tuple[float, dict]] = []
        for entry in ltm_entries:
            score = self._relevance(entry, keywords)
            if score > 0:
                scored.append((score, entry))

        # 排序 + 截取
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:effective_max]
        items = [{"score": s, **e} for s, e in top]

        elapsed = (time.monotonic() - t0) * 1000

        return RetrievalResult(
            items=items,
            query=focus_description,
            total_scanned=len(ltm_entries),
            retrieval_time_ms=round(elapsed, 2),
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """简单关键词提取（按空格/标点分割 + 去停用词）。"""
        import re
        words = re.findall(r"[a-zA-Z\u4e00-\u9fff]+", text.lower())
        stopwords = {"the", "a", "an", "is", "of", "in", "to", "and", "or",
                     "的", "是", "在", "和", "了", "不", "我", "有"}
        return [w for w in words if w not in stopwords][:10]  # 最多 10 个关键词

    def _relevance(self, entry: dict, keywords: list[str]) -> float:
        """计算 LTM 条目与关键词的相关度。"""
        if not keywords:
            return 0.0

        content = str(entry.get("content", "")).lower()
        tags = [t.lower() for t in entry.get("tags", [])]
        text = content + " " + " ".join(tags)

        matches = sum(1 for kw in keywords if kw in text)
        if matches == 0:
            return 0.0

        # 基础分 + 重要性加权
        base = matches / len(keywords)
        importance = entry.get("importance", 0.5)
        return base * importance


# ── MemoryConsolidationScheduler ────────────────────────────────────────────────


class MemoryConsolidationScheduler:
    """24d1: 夜间低峰期自动压缩旧 Experience 的定时调度器。

    策略:
      - 每 N 个 tick 执行一次检查
      - 低峰期定义: tick 计数在指定范围（模拟夜间）
      - 旧 Experience 阈值: 超过 max_age_seconds 的 entries
    """

    def __init__(
        self,
        consolidation_interval: int = 100,   # 每 100 tick 检查一次
        max_age_seconds: float = 86400.0,    # 24 小时
        low_peak_hours: tuple[int, int] = (2, 5),  # 凌晨 2-5 点
    ) -> None:
        self.interval = consolidation_interval
        self.max_age_seconds = max_age_seconds
        self.low_peak_range = low_peak_hours
        self._tick_count = 0
        self._consolidation_count = 0
        self._last_consolidation: datetime | None = None
        self._total_compressed = 0

    @property
    def consolidation_count(self) -> int:
        return self._consolidation_count

    @property
    def total_compressed(self) -> int:
        return self._total_compressed

    @property
    def last_consolidation(self) -> datetime | None:
        return self._last_consolidation

    def should_consolidate(self, tick_count: int, *, force: bool = False) -> bool:
        """判断是否应该执行压缩。

        条件:
          1. force=True 时绕过所有限制
          2. tick 间隔到达
          3. 当前小时在低峰范围内

        Args:
            tick_count: 当前 tick
            force: 强制触发（用于测试/手动压缩）
        """
        self._tick_count = tick_count
        if force:
            return True
        if tick_count % self.interval != 0:
            return False

        current_hour = datetime.now(timezone.utc).hour
        if not (self.low_peak_range[0] <= current_hour < self.low_peak_range[1]):
            return False

        return True

    def consolidate(
        self,
        experiences: list[dict[str, Any]],
        compressor: ContextCompressor | None = None,
    ) -> tuple[list[dict], CompressionStats | None]:
        """执行压缩。

        Args:
            experiences: 旧 Experience 列表
            compressor: 可选压缩器（默认创建新实例）

        Returns:
            (compressed_items, stats)
        """
        comp = compressor or ContextCompressor(token_budget=2048)
        compressed, stats = comp.compress(experiences)

        self._consolidation_count += 1
        self._total_compressed += len(experiences)
        self._last_consolidation = datetime.now(timezone.utc)

        logger.info(
            "Consolidation #%d: %d→%d entries (ratio=%.2f)",
            self._consolidation_count,
            len(experiences), len(compressed),
            stats.compression_ratio,
        )

        return compressed, stats
