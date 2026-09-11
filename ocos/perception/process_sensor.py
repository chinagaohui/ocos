"""Phase 52: ProcessSensor — 进程存在性感知。

检测进程开始/消失 (start/stop):
    - 采样进程列表快照 (psutil.process_iter)
    - 对比两次快照的差异 → started / stopped / new
    - 不读进程详细信息 (命令行/路径) — 避免权限问题
    - 不做进程监控平台 — 只做变化检测

P5.2 最小实现: 变化检测 + 细粒度 system_process_started/stopped 事件.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time

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
class ProcessSensor:
    """进程传感器 — 检测系统进程变化。

    最小实现:
        - 快照 (pid, name) 对
        - 前后 diff → started / stopped
        - 不采样命令行/路径 (跨平台/权限敏感)
    """

    config: SensorConfig = field(default_factory=lambda: SensorConfig(
        sensor_name="process_sensor",
        poll_interval=15.0,          # 进程变化比文件变化慢, 15s 采样
        max_observations_per_poll=10,
        confidence_threshold=0.6,
        modalities=[SensorModality.ENV],
    ))
    health: SensorHealth = field(default_factory=lambda: SensorHealth(
        sensor_name="process_sensor",
    ))

    _seen_pids: set[int] = field(default_factory=set)

    def poll(self) -> list[Observation]:
        """采集进程列表变化。"""
        if not self.config.enabled:
            return []

        if psutil is None:
            return []  # 降级

        observations: list[Observation] = []

        try:
            # 轻量采样: 只抓 pid + name (不抓 cmdline/cwd — 权限敏感)
            current: set[int] = set()
            pid_name: dict[int, str] = {}
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pid = proc.info['pid']
                    name = proc.info['name'] or ""
                    current.add(pid)
                    pid_name[pid] = name
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 第一次 poll: 建立基线, 不产出事件 (太多噪音)
            if not self._seen_pids:
                self._seen_pids = current
                self.health.last_poll_at = _time.time()
                self.health.observations_collected = 0
                return []

            started = current - self._seen_pids
            stopped = self._seen_pids - current

            now = _time.time()

            for pid in started:
                observations.append(Observation(
                    id=f"proc-start-{pid}-{int(now)}",
                    modality=SensorModality.ENV,
                    type=ObservationType.CHANGE,
                    content={
                        "type": "process_started",
                        "operation": "started",
                        "pid": pid,
                        "name": pid_name.get(pid, ""),
                    },
                    confidence=0.8,
                    source_sensor=self.config.sensor_name,
                ))

            for pid in stopped:
                observations.append(Observation(
                    id=f"proc-stop-{pid}-{int(now)}",
                    modality=SensorModality.ENV,
                    type=ObservationType.CHANGE,
                    content={
                        "type": "process_stopped",
                        "operation": "stopped",
                        "pid": pid,
                    },
                    confidence=0.8,
                    source_sensor=self.config.sensor_name,
                ))

            self._seen_pids = current
            self.health.last_poll_at = _time.time()
            self.health.observations_collected += len(observations)

        except Exception as e:
            self.health.status = SensorStatus.ERROR
            self.health.last_error_msg = str(e)
            self.health.last_error_at = _time.time()
            self.health.errors += 1
            return []

        return observations

    def get_health(self) -> SensorHealth:
        return self.health


__all__ = ["ProcessSensor"]
