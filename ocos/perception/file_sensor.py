"""Phase 52: FileSensor — 文件系统感知。

检测文件系统的变化:
    - 文件创建/修改/删除
    - 内容变化
    - 敏感的目录监控

PS52-02: 文件传感器独立运行，崩溃不影响其他模块。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import time as _time

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SensorConfig, SensorHealth,
    SensorModality, SensorStatus,
)


@dataclass
class FileSensor:
    """文件系统传感器 — OCOS 的"眼睛"看文件系统。

    监控指定路径:
        - 文件存在性变化
        - 文件大小变化
        - 修改时间变化

    不读取完整文件内容 (交给 Capability Layer)。
    """

    config: SensorConfig = field(default_factory=lambda: SensorConfig(
        sensor_name="file_sensor",
        poll_interval=5.0,
        max_observations_per_poll=20,
        confidence_threshold=0.7,
        modalities=[SensorModality.FILE],
    ))
    health: SensorHealth = field(default_factory=lambda: SensorHealth(
        sensor_name="file_sensor",
    ))

    _watch_paths: list[Path] = field(default_factory=list)
    _snapshots: dict[str, dict] = field(default_factory=dict)  # path → {mtime, size}

    def watch(self, path: str | Path) -> None:
        """添加监控路径。"""
        p = Path(path).expanduser().resolve()
        if p.exists() and p not in self._watch_paths:
            self._watch_paths.append(p)
            self._snapshot(p)

    def watch_directory(self, path: str | Path) -> None:
        """监控目录下所有文件。"""
        p = Path(path).expanduser().resolve()
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    self.watch(f)

    def poll(self) -> list[Observation]:
        """采集文件变化。比对新旧快照。"""
        if not self.config.enabled:
            return []

        observations: list[Observation] = []

        try:
            for path in self._watch_paths:
                obs = self._check_file(path)
                if obs:
                    observations.append(obs)
        except Exception as e:
            self.health.status = SensorStatus.ERROR
            self.health.last_error_msg = str(e)
            self.health.last_error_at = _time.time()
            self.health.errors += 1
            return []  # PS52-02: isolate failure

        self.health.last_poll_at = _time.time()
        self.health.observations_collected += len(observations)
        return observations

    def _check_file(self, path: Path) -> Observation | None:
        """检查单个文件的变化。"""
        key = str(path)
        old = self._snapshots.get(key, {})

        exists = path.exists()
        now = _time.time()

        if exists:
            stat = path.stat()
            current = {"mtime": stat.st_mtime, "size": stat.st_size, "exists": True}
        else:
            current = {"mtime": 0, "size": 0, "exists": False}

        # 检测变化
        changed = False
        change_type = ""

        if old.get("exists") != current["exists"]:
            changed = True
            change_type = "created" if current["exists"] else "deleted"
        elif current["exists"] and old.get("mtime") != current["mtime"]:
            changed = True
            change_type = "modified"
        elif current["exists"] and old.get("size") != current["size"]:
            changed = True
            change_type = "size_change"

        if changed:
            self._snapshots[key] = current
            return Observation(
                id=f"file-{hash(key)}-{now}",
                modality=SensorModality.FILE,
                type=ObservationType.CHANGE,
                content={
                    "path": key,
                    "change": change_type,
                    "old": old,
                    "current": current,
                },
                confidence=0.95,
                source_sensor=self.config.sensor_name,
                raw_payload={"file": key, "change": change_type},
            )

        # 更新快照
        self._snapshots[key] = current
        return None

    def _snapshot(self, path: Path) -> None:
        """创建文件初始快照。"""
        key = str(path)
        if path.exists() and key not in self._snapshots:
            stat = path.stat()
            self._snapshots[key] = {
                "mtime": stat.st_mtime, "size": stat.st_size, "exists": True,
            }
        elif not path.exists():
            self._snapshots[key] = {"mtime": 0, "size": 0, "exists": False}

    def clear_watches(self) -> None:
        self._watch_paths.clear()
        self._snapshots.clear()

    @property
    def watched_paths(self) -> list[Path]:
        return self._watch_paths

    def get_health(self) -> SensorHealth:
        return self.health


__all__ = ["FileSensor"]
