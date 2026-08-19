"""Phase 52: PerceptionEngine — 感知引擎主循环。

核心流:
    Sensors[] → poll() → Observations[] → SemanticExtractor → Validation → EventBus

    ┌──────────────┐
    │ TextSensor   │──┐
    ├──────────────┤  │
    │ FileSensor   │──┼──→ PerceptionEngine ──→ EventBus
    ├──────────────┤  │        │
    │ EnvSensor    │──┘        │
    └──────────────┘           ▼
                        SemanticExtractor
                               │
                               ▼
                        PerceptionValidator
                               │
                               ▼
                        EventBus → Attention
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable
import time as _time

from ocos.perception.sensor_types import (
    Observation, SemanticFragment, PerceptionEvent, PerceptionEventType,
    SensorConfig, SensorHealth, SensorStatus,
    ValidationResult, ValidationVerdict,
)


@dataclass
class PerceptionEngine:
    """感知引擎 — 协调所有传感器，驱动 Perceive → Extract → Validate → Publish 链路。

    用法:
        engine = PerceptionEngine()
        engine.register_sensor(text_sensor)
        engine.register_sensor(file_sensor)
        engine.register_sensor(env_sensor)

        events = engine.tick()  # 一次感知周期
        for event in events:
            event_bus.publish(event)
    """

    sensors: dict[str, object] = field(default_factory=dict)
    semantic_extractor: Callable[[Observation], SemanticFragment | None] | None = None
    validator: Callable[[Observation, SemanticFragment | None], ValidationResult] | None = None
    event_callback: Callable[[PerceptionEvent], None] | None = None

    # 统计
    total_observations: int = 0
    total_events: int = 0
    tick_count: int = 0

    # 配置
    observation_capacity: int = 1000  # 最多保留的最近观察
    _recent_observations: list[Observation] = field(default_factory=list)

    def register_sensor(self, sensor: object) -> None:
        """注册传感器。sensor 必须有 poll() 方法。"""
        name = getattr(sensor, "config", None)
        sensor_name = name.sensor_name if hasattr(name, "sensor_name") else str(id(sensor))
        self.sensors[sensor_name] = sensor

    def unregister_sensor(self, sensor_name: str) -> None:
        self.sensors.pop(sensor_name, None)

    def tick(self) -> list[PerceptionEvent]:
        """执行一次完整的感知周期。

        1. Poll all sensors
        2. Extract semantics
        3. Validate
        4. Emit events
        """
        self.tick_count += 1
        events: list[PerceptionEvent] = []

        # 1. Poll
        all_observations: list[Observation] = []
        for name, sensor in self.sensors.items():
            try:
                if hasattr(sensor, "poll"):
                    obs_list = sensor.poll()
                    all_observations.extend(obs_list)
            except Exception:
                # PS52-02: sensor failure is isolated
                continue

        self.total_observations += len(all_observations)
        self._store_recent(all_observations)

        # 2. Process each observation
        for obs in all_observations:
            # Semantic extraction
            semantic = self._extract_semantic(obs)

            # Validation (PS52-04)
            validation = self._validate(obs, semantic)

            # Build event
            event = PerceptionEvent(
                type=PerceptionEventType.OBSERVATION_READY,
                observation=obs,
                semantic=semantic,
                sensor_name=obs.source_sensor,
            )

            if validation and validation.verdict != ValidationVerdict.REJECTED:
                event.metadata["validation"] = {
                    "verdict": validation.verdict.value,
                    "reason": validation.reason,
                    "confidence_adjustment": validation.confidence_adjustment,
                }

            events.append(event)
            self.total_events += 1

            if self.event_callback:
                self.event_callback(event)

        return events

    def _extract_semantic(self, obs: Observation) -> SemanticFragment | None:
        if self.semantic_extractor:
            return self.semantic_extractor(obs)
        return None

    def _validate(self, obs: Observation, semantic: SemanticFragment | None) -> ValidationResult | None:
        if self.validator:
            return self.validator(obs, semantic)
        # 默认: 置信度 > 0.5 就通过
        if obs.confidence >= 0.5:
            return ValidationResult(
                observation_id=obs.id,
                verdict=ValidationVerdict.ACCEPTED,
                reason="confidence threshold met",
            )
        return ValidationResult(
            observation_id=obs.id,
            verdict=ValidationVerdict.REJECTED,
            reason="low confidence",
        )

    def _store_recent(self, observations: list[Observation]) -> None:
        self._recent_observations.extend(observations)
        if len(self._recent_observations) > self.observation_capacity:
            self._recent_observations = self._recent_observations[-self.observation_capacity:]

    def get_recent_observations(self, n: int = 10) -> list[Observation]:
        return self._recent_observations[-n:]

    def sensor_health(self) -> dict[str, dict]:
        """获取所有传感器健康状态。"""
        report = {}
        for name, sensor in self.sensors.items():
            if hasattr(sensor, "get_health"):
                h = sensor.get_health()
                report[name] = {
                    "status": h.status.value,
                    "collected": h.observations_collected,
                    "errors": h.errors,
                }
        return report

    def get_state(self) -> dict:
        """导出状态用于持久化。"""
        return {
            "total_observations": self.total_observations,
            "total_events": self.total_events,
            "tick_count": self.tick_count,
            "sensor_count": len(self.sensors),
        }

    def set_state(self, data: dict) -> None:
        """从持久化恢复。"""
        self.total_observations = data.get("total_observations", 0)
        self.total_events = data.get("total_events", 0)
        self.tick_count = data.get("tick_count", 0)


__all__ = ["PerceptionEngine"]
