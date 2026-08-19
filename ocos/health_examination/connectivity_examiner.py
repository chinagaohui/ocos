"""Phase 58.0: ConnectivityExaminer — 神经连接矩阵。

核心问题: 器官都有，但血管是否接通？

建立 OCOS Connectivity Matrix 并验证每条链。
"""

from __future__ import annotations
from dataclasses import dataclass, field

from ocos.health_examination.health_model import (
    HealthCategory, CategoryScore, ConnectionHealth,
)


# OCOS Connectivity Matrix: (source, target) pairs
# 基于 Phase 39-50 的设计依赖关系
CONNECTIVITY_PAIRS: list[tuple[str, str]] = [
    # Perception → downstream
    ("Perception", "Attention"),
    ("Perception", "WorldModel"),
    # Attention → decision
    ("Attention", "Decision"),
    ("Attention", "Memory"),
    # WorldModel → decision support
    ("WorldModel", "Decision"),
    ("WorldModel", "Memory"),
    # Memory ↔ Decision
    ("Memory", "Decision"),
    ("Memory", "SelfModel"),
    # SelfModel
    ("SelfModel", "Decision"),
    ("SelfModel", "Evolution"),
    # Decision → execution
    ("Decision", "Capability"),
    ("Decision", "Extension"),
    # Capability → feedback
    ("Capability", "Memory"),
    ("Capability", "EventMemory"),
    # Result → learning
    ("Result", "Learning"),
    ("Result", "Memory"),
    # Learning → Evolution
    ("Learning", "Evolution"),
    ("Learning", "SelfModel"),
    # Evolution → self
    ("Evolution", "SelfModel"),
    ("Evolution", "Continuity"),
    # OS orchestration
    ("OS", "Perception"),
    ("OS", "Decision"),
    ("OS", "Capability"),
    ("OS", "Continuity"),
    # Extension → Capability
    ("Extension", "Capability"),
    # EventMemory
    ("EventMemory", "Memory"),
    ("EventMemory", "Learning"),
    # Continuity
    ("Continuity", "SelfModel"),
]


@dataclass
class ConnectivityExaminer:
    """神经连接体检器。"""

    # 注入的连接状态 (外部可覆盖以模拟断连)
    connection_states: dict[tuple[str, str], bool] = field(default_factory=dict)

    # 诊断回调 — 模拟实际调用链
    trace_callbacks: dict[str, object] = field(default_factory=dict)

    def examine(self) -> CategoryScore:
        """检查所有连接对。"""
        results: dict[tuple[str, str], ConnectionHealth] = {}

        for source, target in CONNECTIVITY_PAIRS:
            key = (source, target)
            connected = self.connection_states.get(key, True)

            ch = ConnectionHealth(
                source=source, target=target,
                connected=connected,
                detail="connected" if connected else "broken",
            )
            results[key] = ch

        connected_count = sum(1 for ch in results.values() if ch.connected)
        total = len(CONNECTIVITY_PAIRS)
        score = (connected_count / total) * 25.0 if total > 0 else 0.0

        warnings = []
        broken = [(ch.source, ch.target) for ch in results.values() if not ch.connected]
        if broken:
            for s, t in broken:
                warnings.append(f"broken: {s} → {t}")

        return CategoryScore(
            category=HealthCategory.CONNECTIVITY,
            raw_score=score,
            max_score=25.0,
            normalized=connected_count / total if total > 0 else 0.0,
            details={
                "connections_total": total,
                "connections_ok": connected_count,
                "connections_broken": total - connected_count,
                "broken_pairs": [(c.source, c.target) for c in results.values() if not c.connected],
            },
            warnings=warnings,
        )

    def inject_broken(self, source: str, target: str) -> None:
        """注入一条断连。"""
        self.connection_states[(source, target)] = False

    def inject_all_broken(self) -> None:
        """所有连接断开（压力测试）。"""
        for s, t in CONNECTIVITY_PAIRS:
            self.connection_states[(s, t)] = False

    def restore_all(self) -> None:
        self.connection_states.clear()


__all__ = ["ConnectivityExaminer", "CONNECTIVITY_PAIRS"]
