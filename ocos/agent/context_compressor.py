"""Phase 24-D — ContextCompressor: Working Memory → LLM token 预算内格式。

职责:
  - 给定 token budget，压缩 working memory 到紧凑格式
  - 分层压缩: 优先保留高重要性项目
  - 输出压缩报告（摘要 + 选择详情）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CompressionConfig:
    token_budget: int = 2000         # 目标 token 数
    chars_per_token: int = 4         # 粗略 char→token 估算
    importance_threshold: float = 0.3  # 低重要性条目截断
    max_entries: int = 50
    summary_ratio: float = 0.1       # 摘要占比


@dataclass
class CompressionResult:
    compressed_text: str
    original_chars: int
    compressed_chars: int
    entries_kept: int
    entries_dropped: int
    budget_used_pct: float

    @property
    def compression_ratio(self) -> float:
        if self.original_chars == 0:
            return 1.0
        return self.compressed_chars / self.original_chars


@dataclass
class ContextCompressor:
    """Working Memory → Token Budget 压缩器。

    用法:
        cc = ContextCompressor(config=CompressionConfig(token_budget=2000))
        result = cc.compress(working_items)
        print(f"压缩率: {result.compression_ratio:.2%}")
    """

    config: CompressionConfig = field(default_factory=CompressionConfig)

    def compress(self, items: list[Any]) -> CompressionResult:
        """将 working memory 条目压缩到 token budget 内。

        Args:
            items: working memory 条目列表（支持 dict 或对象）

        Returns:
            CompressionResult
        """
        if not items:
            return CompressionResult(
                compressed_text="",
                original_chars=0,
                compressed_chars=0,
                entries_kept=0,
                entries_dropped=0,
                budget_used_pct=0,
            )

        budget_chars = self.config.token_budget * self.config.chars_per_token
        original_chars = sum(len(self._extract_text(it)) for it in items)

        # 按重要性排序
        scored = [(it, self._importance(it)) for it in items]
        scored.sort(key=lambda x: x[1], reverse=True)

        kept: list[str] = []
        total = 0
        entries_kept = 0

        for item, imp in scored:
            if entries_kept >= self.config.max_entries:
                break
            if imp < self.config.importance_threshold and entries_kept > 10:
                continue
            text = self._extract_text(item)
            overhead = len(text) + 1  # +1 for separator
            if total + overhead > budget_chars * (1 - self.config.summary_ratio):
                break
            kept.append(text)
            total += overhead
            entries_kept += 1

        compressed_text = "\n".join(kept)
        compressed_chars = len(compressed_text)

        return CompressionResult(
            compressed_text=compressed_text,
            original_chars=original_chars,
            compressed_chars=compressed_chars,
            entries_kept=entries_kept,
            entries_dropped=len(items) - entries_kept,
            budget_used_pct=compressed_chars / budget_chars * 100,
        )

    @staticmethod
    def _extract_text(item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return item.get("content", str(item))
        if hasattr(item, "content"):
            return str(item.content)
        return str(item)

    @staticmethod
    def _importance(item: Any) -> float:
        if isinstance(item, dict):
            return float(item.get("importance", 0.5))
        if hasattr(item, "importance"):
            return float(item.importance)
        return 0.5
