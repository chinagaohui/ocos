"""Phase 52: EnvironmentSensor — 环境信号感知。

检测运行环境变化:
    - 时间流逝 (tick, wall-clock)
    - 资源变化 (内存、磁盘)
    - 系统信号
    - 自身健康变化

这是 OCOS 的"内感" — 感知自身运行环境。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import time as _time

# 2026-08-17 健康化：psutil 可选（环境缺省时传感器降级，不崩溃收集）。
try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SensorConfig, SensorHealth,
    SensorModality, SensorStatus,
)


@dataclass
class EnvironmentSnapshot:
    """环境快照 — 单次采集的完整环境状态。"""
    timestamp: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    cpu_percent: float = 0.0
    disk_used_gb: float = 0.0
    uptime_seconds: float = 0.0


@dataclass
class EnvironmentSensor:
    """环境传感器 — OCOS 的"内感"。

    监控:
        - 内存使用 (RSS)
        - CPU 占用
        - 磁盘空间
        - 运行时长
        - 异常跳变检测
    """

    config: SensorConfig = field(default_factory=lambda: SensorConfig(
        sensor_name="environment_sensor",
        poll_interval=10.0,
        max_observations_per_poll=5,
        confidence_threshold=0.5,
        modalities=[SensorModality.ENV],
    ))
    health: SensorHealth = field(default_factory=lambda: SensorHealth(
        sensor_name="environment_sensor",
    ))

    _last_snapshot: EnvironmentSnapshot | None = None
    _start_time: float = field(default_factory=_time.time)
    _memory_high_mb: float = 1024     # 内存告警线 (MB)
    _memory_critical_mb: float = 2048  # 内存危险线 (MB)

    def poll(self) -> list[Observation]:
        """采集环境状态，检测异常变化。"""
        if not self.config.enabled:
            return []

        observations: list[Observation] = []

        # 2026-08-17 健康化：psutil 缺失 → 环境感知降级（返回空，不崩溃）
        if psutil is None:
            return observations

        try:
            proc = psutil.Process()
            mem = proc.memory_info()
            current = EnvironmentSnapshot(
                timestamp=_time.time(),
                memory_used_mb=mem.rss / 1024 / 1024,
                memory_total_mb=psutil.virtual_memory().total / 1024 / 1024,
                cpu_percent=proc.cpu_percent(interval=0.1),
                disk_used_gb=psutil.disk_usage("/").used / 1024**3,
                uptime_seconds=_time.time() - self._start_time,
            )

            # 内存告警
            if current.memory_used_mb > self._memory_critical_mb:
                observations.append(Observation(
                    id=f"env-critical-mem-{current.timestamp}",
                    modality=SensorModality.ENV,
                    type=ObservationType.ANOMALY,
                    content={"type": "memory_critical", "used_mb": current.memory_used_mb},
                    confidence=1.0,
                    source_sensor=self.config.sensor_name,
                ))
            elif current.memory_used_mb > self._memory_high_mb:
                observations.append(Observation(
                    id=f"env-high-mem-{current.timestamp}",
                    modality=SensorModality.ENV,
                    type=ObservationType.ANOMALY,
                    content={"type": "memory_high", "used_mb": current.memory_used_mb},
                    confidence=0.9,
                    source_sensor=self.config.sensor_name,
                ))

            # 跳变检测
            if self._last_snapshot:
                mem_delta = current.memory_used_mb - self._last_snapshot.memory_used_mb
                if abs(mem_delta) > 100:  # 内存突然跳变超 100MB
                    observations.append(Observation(
                        id=f"env-spike-{current.timestamp}",
                        modality=SensorModality.ENV,
                        type=ObservationType.ANOMALY,
                        content={
                            "type": "memory_spike",
                            "delta_mb": mem_delta,
                            "from": self._last_snapshot.memory_used_mb,
                            "to": current.memory_used_mb,
                        },
                        confidence=0.8,
                        source_sensor=self.config.sensor_name,
                    ))

            self._last_snapshot = current
            self.health.last_poll_at = _time.time()
            self.health.observations_collected += len(observations)

        except Exception as e:
            self.health.status = SensorStatus.ERROR
            self.health.last_error_msg = str(e)
            self.health.last_error_at = _time.time()
            self.health.errors += 1
            return []  # PS52-02

        return observations

    def get_health(self) -> SensorHealth:
        return self.health

    @property
    def last_snapshot(self) -> EnvironmentSnapshot | None:
        return self._last_snapshot


__all__ = ["EnvironmentSensor", "EnvironmentSnapshot"]
