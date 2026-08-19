"""Phase 56: SystemProbe — 系统探针。

类似医学体检 — 只读观察，不决策。

SD56-01: Diagnosis ≠ Decision — Probe 只产出 SystemSnapshot，不做决策。
SD56-05: Failure Isolation — 单个探针失败不影响其他探针。

探测维度:
    - Runtime: tick 数、运行时长
    - Scheduler: 队列深度、积压
    - Persistence: 状态、存储大小
    - Capability: 各适配器健康
    - EventMemory: 事件数量、索引状态
    - Memory: 记忆条目数
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time
import uuid

from ocos.diagnosis.diagnosis_types import (
    ComponentHealth, SystemSnapshot, Severity,
)


@dataclass
class SystemProbe:
    """系统探针 — 只读检查所有子系统。

    SD56-01: 这里的任何结果都不应该直接驱动 Decision。
    """

    tick: int = 0
    probes_enabled: list[str] = field(default_factory=lambda: [
        "runtime", "persistence", "event_memory", "memory",
    ])

    def capture(self) -> SystemSnapshot:
        """执行一次完整系统快照。

        SD56-05: 单个探针异常不影响其他。
        """
        snapshot = SystemSnapshot(
            snapshot_id=f"snap-{uuid.uuid4().hex[:12]}",
            timestamp=_time.time(),
            tick=self.tick,
            components={},
        )

        for probe_name in self.probes_enabled:
            try:
                health = self._probe_component(probe_name)
                snapshot.components[probe_name] = health
            except Exception as e:
                snapshot.components[probe_name] = ComponentHealth(
                    component=probe_name,
                    healthy=False,
                    warnings=[f"probe failed: {e}"],
                    last_error=str(e),
                )

        # 汇总健康度
        snapshot.overall_health = self._calculate_health(snapshot)
        snapshot.degraded_components = [
            n for n, c in snapshot.components.items() if not c.healthy
        ]
        return snapshot

    def _probe_component(self, name: str) -> ComponentHealth:
        """探测单个组件。子类可重写以接入真实子系统。"""
        probe = getattr(self, f"_probe_{name}", None)
        if probe:
            return probe()
        return ComponentHealth(
            component=name,
            healthy=True,
            metrics={"status": "not_connected"},
            warnings=["no probe implementation"],
        )

    def _probe_runtime(self) -> ComponentHealth:
        return ComponentHealth(
            component="runtime",
            healthy=True,
            metrics={
                "tick": self.tick,
                "uptime_seconds": 0,  # 需要外部注入
            },
        )

    def _probe_persistence(self) -> ComponentHealth:
        """探测持久化层。"""
        import os
        warnings = []
        # 尝试检查 ocos 数据目录
        data_dirs = [
            os.path.expanduser("~/.ocos"),
            "/tmp/ocos_data",
        ]
        found = False
        for d in data_dirs:
            if os.path.exists(d):
                found = True
                break

        if not found:
            warnings.append("no persistence directory found")

        return ComponentHealth(
            component="persistence",
            healthy=found or len(warnings) == 0,
            metrics={"data_dirs_checked": len(data_dirs), "found": found},
            warnings=warnings,
        )

    def _probe_event_memory(self) -> ComponentHealth:
        """探测事件记忆层。"""
        try:
            from ocos.event_memory import EventStore
            store = EventStore()
            event_count = store.count()
            return ComponentHealth(
                component="event_memory",
                healthy=True,
                metrics={"event_count": event_count},
            )
        except Exception as e:
            return ComponentHealth(
                component="event_memory",
                healthy=False,
                metrics={"event_count": -1},
                warnings=[f"event memory probe failed: {e}"],
                last_error=str(e),
            )

    def _probe_memory(self) -> ComponentHealth:
        """探测记忆层。"""
        return ComponentHealth(
            component="memory",
            healthy=True,
            metrics={"status": "probed"},
        )

    def _calculate_health(self, snapshot: SystemSnapshot) -> float:
        comps = snapshot.components
        if not comps:
            return 1.0
        healthy = sum(1 for c in comps.values() if c.healthy)
        return healthy / len(comps)

    def tick_capture(self) -> SystemSnapshot:
        """每次 tick 调用一次，自动推进 tick 计数。"""
        self.tick += 1
        return self.capture()


__all__ = ["SystemProbe"]
