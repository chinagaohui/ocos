"""Phase 40: ExperienceProfile — 经验特征投影。

回答: "我过去经历形成了什么认知特征？"

不是 Memory（事件记录），而是从 Memory 中抽象出的统计性认知模式。
Memory = 发生过什么，ExperienceProfile = 我是什么样的认知主体。

支持:
    - successful_patterns:     成功模式
    - failure_patterns:        失败模式
    - behavioral_tendencies:   行为倾向
    - learning_rate_estimate:  学习速率估计
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.self.self_types import ExperiencePattern


@dataclass
class ExperienceProfile:
    """SelfModel 的经验特征投影。

    从 Memory Consolidation 产出中提取的统计性认知特征。
    """

    successful_patterns: list[ExperiencePattern] = field(default_factory=list)
    """成功的行为模式。"""

    failure_patterns: list[ExperiencePattern] = field(default_factory=list)
    """失败的行为模式。"""

    behavioral_tendencies: list[str] = field(default_factory=list)
    """观察到的行为倾向（中性描述）。"""

    total_experiences: int = 0
    """抽象的经验总量。"""

    learning_rate_estimate: float = 0.5
    """学习速率估计 [0, 1]。"""

    # ── 查询 ──

    @property
    def success_count(self) -> int:
        return len(self.successful_patterns)

    @property
    def failure_count(self) -> int:
        return len(self.failure_patterns)

    @property
    def success_ratio(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5
        return self.success_count / total

    @property
    def top_success_patterns(self) -> list[ExperiencePattern]:
        """按置信度排序的成功模式。"""
        return sorted(self.successful_patterns, key=lambda p: p.confidence, reverse=True)

    @property
    def top_failure_patterns(self) -> list[ExperiencePattern]:
        """按置信度排序的失败模式。"""
        return sorted(self.failure_patterns, key=lambda p: p.confidence, reverse=True)

    # ── 操作 ──

    def add_pattern(self, pattern: ExperiencePattern) -> None:
        """添加经验模式。"""
        if pattern.category == "successful":
            self.successful_patterns.append(pattern)
        elif pattern.category == "failure":
            self.failure_patterns.append(pattern)
        # neutral patterns go to behavioral_tendencies
        else:
            self.behavioral_tendencies.append(f"{pattern.label}: {pattern.note}")

    def update_learning_rate(self, delta: float) -> None:
        """调整学习速率估计。"""
        self.learning_rate_estimate = max(0.0, min(1.0,
            self.learning_rate_estimate + delta))

    def remove_stale(self, before_tick: int) -> int:
        """移除过期的经验模式，返回移除数量。"""
        before_len_succ = len(self.successful_patterns)
        before_len_fail = len(self.failure_patterns)

        self.successful_patterns = [
            p for p in self.successful_patterns
            if p.abstracted_at_tick >= before_tick
        ]
        self.failure_patterns = [
            p for p in self.failure_patterns
            if p.abstracted_at_tick >= before_tick
        ]

        return (before_len_succ - len(self.successful_patterns) +
                before_len_fail - len(self.failure_patterns))

    def summary(self) -> str:
        return (
            f"ExperienceProfile: {self.total_experiences} total, "
            f"{self.success_count} successes, {self.failure_count} failures "
            f"(ratio={self.success_ratio:.2f}), lr={self.learning_rate_estimate:.2f}"
        )
