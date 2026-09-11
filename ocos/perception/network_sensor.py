"""Phase 52: NetworkSensor — 网络连通性感知 (P5.3).

最小实现:
    - socket.gethostbyname() DNS 解析可达性
    - 对比前后两次状态 → reachable / unreachable
    - 不做 HTTP ping / 延迟采样 (避免跨环境不稳定性)
    - 复用 SensorModality.ENV → EventSource.SYSTEM 细粒度分类
"""

from __future__ import annotations

from dataclasses import dataclass, field
import socket
import time as _time

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SensorConfig, SensorHealth,
    SensorModality, SensorStatus,
)


@dataclass
class NetworkSensor:
    """网络连通性传感器 — DNS 解析 + 基本 TCP 可达性。"""

    config: SensorConfig = field(default_factory=lambda: SensorConfig(
        sensor_name="network_sensor",
        poll_interval=30.0,
        max_observations_per_poll=5,
        confidence_threshold=0.7,
        modalities=[SensorModality.ENV],
    ))
    health: SensorHealth = field(default_factory=lambda: SensorHealth(
        sensor_name="network_sensor",
    ))

    _check_targets: list[str] = field(default_factory=lambda: [
        "www.baidu.com",   # 国内
        "8.8.8.8",         # Google DNS IP (纯 IP 不解析)
    ])
    _previous: dict[str, bool] = field(default_factory=dict)  # target → reachable

    def poll(self) -> list[Observation]:
        """检测网络连通性变化。"""
        if not self.config.enabled:
            return []

        observations: list[Observation] = []
        now = _time.time()

        for target in self._check_targets:
            reachable = self._check_dns(target)

            prev = self._previous.get(target)
            self._previous[target] = reachable

            # 第一次 poll: 建立基线, 不产出事件
            if prev is None:
                continue

            if reachable != prev:
                if reachable:
                    observations.append(Observation(
                        id=f"net-reach-{target}-{int(now)}",
                        modality=SensorModality.ENV,
                        type=ObservationType.CHANGE,
                        content={
                            "type": "network_reachable",
                            "operation": "reachable",
                            "target": target,
                        },
                        confidence=0.9,
                        source_sensor=self.config.sensor_name,
                    ))
                else:
                    observations.append(Observation(
                        id=f"net-unreach-{target}-{int(now)}",
                        modality=SensorModality.ENV,
                        type=ObservationType.ANOMALY,
                        content={
                            "type": "network_unreachable",
                            "operation": "unreachable",
                            "target": target,
                        },
                        confidence=0.9,
                        source_sensor=self.config.sensor_name,
                    ))

        self.health.last_poll_at = _time.time()
        self.health.observations_collected += len(observations)
        return observations

    def _check_dns(self, target: str) -> bool:
        """DNS 解析检测 (纯 socket, 不依赖 psutil/httpx)."""
        try:
            socket.gethostbyname(target)
            return True
        except (socket.gaierror, socket.herror, OSError):
            return False

    def get_health(self) -> SensorHealth:
        return self.health


__all__ = ["NetworkSensor"]
