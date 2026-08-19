"""Phase 40: CognitiveState — 实时认知状态。

回答: "我当前认知状态怎样？"

连接 Phase 39 Attention — 提供 Attention 数据的 SelfModel 投影。
不是控制 Attention，而是观察和报告认知状态。

结构:
    active_focus       — 当前关注的 focus_id
    workload           — 当前工作负载 [0, 1]
    memory_load        — Memory 负载 [0, 1]
    uncertainty_level  — 不确定性水平 [0, 1]
    attention_health   — Attention 健康状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class AttentionHealth(Enum):
    """Attention 健康状态。"""
    NORMAL = "normal"           # 正常
    OVERLOADED = "overloaded"   # 过载
    SCATTERED = "scattered"     # 分散
    FATIGUED = "fatigued"       # 疲劳（高频切换）


@dataclass
class CognitiveLoad:
    """认知负载快照。"""

    workload: float = 0.0            # [0, 1]
    memory_load: float = 0.0         # [0, 1]
    uncertainty_level: float = 0.0   # [0, 1]
    attention_health: AttentionHealth = AttentionHealth.NORMAL
    tick_id: int = 0


@dataclass
class CognitiveState:
    """SelfModel 的实时认知状态组件。

    不控制 Attention（那是 Phase 39 的职责），
    只投影和报告认知状态给 SelfModel。
    """

    active_focus: str = ""
    """当前关注的 focus_id。"""

    current_load: CognitiveLoad = field(default_factory=lambda: CognitiveLoad())
    """当前认知负载。"""

    load_history: list[CognitiveLoad] = field(default_factory=list)
    """最近 N 个 tick 的负载快照。"""

    max_history: int = 20
    """负载历史最大保留量。"""

    total_ticks_observed: int = 0
    attention_switch_count: int = 0
    """注意力切换次数。"""

    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 更新 ──

    def update(
        self,
        tick_id: int,
        workload: float = 0.0,
        memory_load: float = 0.0,
        uncertainty_level: float = 0.0,
        focus_id: str = "",
    ) -> None:
        """从 Runtime 观察更新认知状态。"""
        if focus_id and focus_id != self.active_focus:
            self.attention_switch_count += 1
        self.active_focus = focus_id

        health = AttentionHealth.NORMAL
        if self.attention_switch_count > 5:
            health = AttentionHealth.SCATTERED
        if workload > 0.8:
            health = AttentionHealth.OVERLOADED

        load = CognitiveLoad(
            workload=workload,
            memory_load=memory_load,
            uncertainty_level=uncertainty_level,
            attention_health=health,
            tick_id=tick_id,
        )

        self.current_load = load
        self.load_history.append(load)
        if len(self.load_history) > self.max_history:
            self.load_history = self.load_history[-self.max_history:]

        self.total_ticks_observed += 1
        self.last_updated = datetime.now(timezone.utc)

    # ── 查询 ──

    @property
    def attention_health(self) -> AttentionHealth:
        return self.current_load.attention_health

    @property
    def is_overloaded(self) -> bool:
        return self.current_load.workload > 0.8

    @property
    def is_scattered(self) -> bool:
        return self.attention_switch_count > 5

    @property
    def average_workload(self) -> float:
        if not self.load_history:
            return 0.0
        return sum(l.workload for l in self.load_history) / len(self.load_history)

    @property
    def switch_rate_per_tick(self) -> float:
        if self.total_ticks_observed == 0:
            return 0.0
        return self.attention_switch_count / self.total_ticks_observed

    def summary(self) -> str:
        return (
            f"CognitiveState: focus={self.active_focus}, "
            f"workload={self.current_load.workload:.2f}, "
            f"health={self.current_load.attention_health.value}, "
            f"switches={self.attention_switch_count}"
        )
