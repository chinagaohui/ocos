"""Phase 50: MemoryGrowthValidator — 记忆质量验证。

不是检测记忆量，而是检测记忆质量。

OS50-04: Memory Growth ≠ Accumulation
    质量评估维度:
        - 高价值比例 (importance >= 0.7)
        - 引用率 (被引用的记忆比例)
        - 老化分布 (fresh/current/aging/legacy/archived 分布)
        - 增长趋势 (记忆量增长但质量是否同步提升)

OCOS 长期运行后，记忆应该:
    更多 ≠ 更好
    更有价值 ✓
    更相关 ✓
    更低噪音 ✓
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.os_v1.os_types import MemoryHealthReport


@dataclass
class MemoryGrowthValidator:
    """记忆质量验证器。

    定期评估记忆的健康状况。
    """

    # 历史报告用于趋势分析
    history: list[MemoryHealthReport] = field(default_factory=list)

    def validate(
        self,
        tick_id: int,
        total_experiences: int,
        high_quality: int,
        stale: int,
        aging_count: int,
        archived_count: int,
    ) -> MemoryHealthReport:
        """生成记忆健康报告。

        OS50-04: 质量 > 数量。
        """
        # 质量分计算
        quality = 0.0
        if total_experiences > 0:
            # 高价值比例 (40%)
            quality += (high_quality / total_experiences) * 0.4
            # 不陈旧比例 (30%)
            active = total_experiences - stale
            quality += (active / total_experiences) * 0.3
            # 活跃比例 (30%) — aging+archived 越少越好
            if total_experiences > 0:
                fresh_ratio = 1.0 - ((aging_count + archived_count) / total_experiences)
                quality += max(0.0, fresh_ratio) * 0.3

        # 趋势分析
        growth_trend = self._determine_trend()

        report = MemoryHealthReport(
            tick_id=tick_id,
            total_experiences=total_experiences,
            high_quality_count=high_quality,
            stale_count=stale,
            aging_count=aging_count,
            archived_count=archived_count,
            quality_score=round(min(1.0, quality), 3),
            growth_trend=growth_trend,
        )
        self.history.append(report)
        if len(self.history) > 100:
            self.history = self.history[-100:]
        return report

    def _determine_trend(self) -> str:
        """从历史中判断趋势。"""
        if len(self.history) < 2:
            return "stable"
        last_two = self.history[-2:]
        diff = last_two[1].quality_score - last_two[0].quality_score
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "declining"
        return "stable"

    def quality_over_time(self) -> list[float]:
        """返回历史质量分序列。"""
        return [r.quality_score for r in self.history]

    @property
    def latest_quality(self) -> float:
        if self.history:
            return self.history[-1].quality_score
        return 0.0


__all__ = ["MemoryGrowthValidator"]
