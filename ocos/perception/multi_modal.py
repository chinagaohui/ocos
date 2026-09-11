"""Phase T: MultiModalPerception — 多模态感知管理器。

扩展现有感知系统，新增模态：
- AudioSensor: 音频输入
- VisionSensor: 视觉输入
- SensorFusion: 跨模态融合
- ModalityManager: 模态管理

接口兼容现有 PerceptionEngine + SensorConfig。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SensorConfig, SensorHealth,
    SensorModality, SensorStatus,
    SemanticFragment,
    PerceptionEvent, PerceptionEventType,
)
from ocos.perception.text_sensor import TextSensor
from ocos.perception.file_sensor import FileSensor
from ocos.perception.environment_sensor import EnvironmentSensor
from ocos.perception.perception_engine import PerceptionEngine
from .cross_modal_fusion import CrossModalFusion, ModalObservation, FusionStrategy

logger = logging.getLogger(__name__)


class AudioSensor:
    """音频传感器 — OCOS 的\"耳朵\"。"""

    def __init__(self, sample_rate: int = 16000, chunk_duration: float = 1.0) -> None:
        self.config = SensorConfig(
            sensor_name="audio_sensor",
            poll_interval=0.5,
            max_observations_per_poll=10,
            confidence_threshold=0.6,
            modalities=[SensorModality.TEXT],  # 音频转文本
        )
        self.health = SensorHealth(sensor_name="audio_sensor")
        self._buffer: list[str] = []
        self._sample_rate = sample_rate
        self._chunk_duration = chunk_duration

    def feed(self, audio_data: Any, transcription: str = "") -> None:
        """输入音频数据和可选转录文本。"""
        if transcription:
            self._buffer.append(transcription)
        self.health.last_poll_at = time.time()

    def poll(self) -> list[Observation]:
        observations = []
        while self._buffer:
            text = self._buffer.pop(0)
            obs = Observation(
                modality=SensorModality.TEXT,
                type=ObservationType.RAW,
                content=f"[audio] {text}",
                confidence=0.7,
                source_sensor="audio_sensor",
            )
            observations.append(obs)
        return observations


class VisionSensor:
    """视觉传感器 — OCOS 的\"眼睛\"。"""

    def __init__(self, resolution: tuple[int, int] = (640, 480)) -> None:
        self.config = SensorConfig(
            sensor_name="vision_sensor",
            poll_interval=0.1,
            max_observations_per_poll=5,
            confidence_threshold=0.7,
            modalities=[SensorModality.TEXT],  # 图像描述转文本
        )
        self.health = SensorHealth(sensor_name="vision_sensor")
        self._buffer: list[str] = []
        self._resolution = resolution

    def feed(self, image_data: Any, description: str = "") -> None:
        """输入图像数据和可选描述。"""
        if description:
            self._buffer.append(description)
        self.health.last_poll_at = time.time()

    def poll(self) -> list[Observation]:
        observations = []
        while self._buffer:
            desc = self._buffer.pop(0)
            obs = Observation(
                modality=SensorModality.TEXT,
                type=ObservationType.RAW,
                content=f"[vision] {desc}",
                confidence=0.75,
                source_sensor="vision_sensor",
            )
            observations.append(obs)
        return observations


class ApiSensor:
    """API 传感器 — 接收外部 API 响应。"""

    def __init__(self) -> None:
        self.config = SensorConfig(
            sensor_name="api_sensor",
            poll_interval=1.0,
            max_observations_per_poll=20,
            confidence_threshold=0.5,
            modalities=[SensorModality.API],
        )
        self.health = SensorHealth(sensor_name="api_sensor")
        self._buffer: list[dict[str, Any]] = []

    def feed(self, response: dict[str, Any]) -> None:
        self._buffer.append(response)
        self.health.last_poll_at = time.time()

    def poll(self) -> list[Observation]:
        observations = []
        for resp in self._buffer[:self.config.max_observations_per_poll]:
            # P5.4: content 必须是 dict —— 和 TextSensor 统一
            obs = Observation(
                modality=SensorModality.API,
                type=ObservationType.RAW,
                content=resp if isinstance(resp, dict) else {"content": str(resp), "type": "api"},
                confidence=0.8,
                source_sensor="api_sensor",
                raw_payload=resp,
            )
            observations.append(obs)
        self._buffer = self._buffer[self.config.max_observations_per_poll:]
        return observations


class EventSensor:
    """事件传感器 — 内部事件流。"""

    def __init__(self) -> None:
        self.config = SensorConfig(
            sensor_name="event_sensor",
            poll_interval=0.01,
            max_observations_per_poll=100,
            confidence_threshold=0.9,
            modalities=[SensorModality.EVENT],
        )
        self.health = SensorHealth(sensor_name="event_sensor")
        self._events: list[dict[str, Any]] = []

    def emit(self, event_type: str, payload: Any = None) -> None:
        self._events.append({
            "type": event_type,
            "payload": payload,
            "timestamp": time.time(),
        })

    def poll(self) -> list[Observation]:
        observations = []
        for evt in self._events[:self.config.max_observations_per_poll]:
            obs = Observation(
                modality=SensorModality.EVENT,
                type=ObservationType.RAW,
                content=f"[event:{evt['type']}] {str(evt.get('payload', ''))[:100]}",
                confidence=0.9,
                source_sensor="event_sensor",
                raw_payload=evt,
            )
            observations.append(obs)
        self._events = self._events[self.config.max_observations_per_poll:]
        return observations


class MultiModalPerception:
    """Phase T: 多模态感知管理器。

    整合所有模态传感器，提供统一的感知接口。
    支持跨模态融合和冲突检测。
    """

    def __init__(
        self,
        fusion_strategy: FusionStrategy = FusionStrategy.WEIGHTED_VOTE,
    ) -> None:
        # 基础传感器
        self.text_sensor = TextSensor()
        self.file_sensor = FileSensor()
        self.env_sensor = EnvironmentSensor()

        # 新增模态
        self.audio_sensor = AudioSensor()
        self.vision_sensor = VisionSensor()
        self.api_sensor = ApiSensor()
        self.event_sensor = EventSensor()

        # 感知引擎
        self.engine = PerceptionEngine()
        self._register_sensors()

        # 跨模态融合
        self.fusion = CrossModalFusion(strategy=fusion_strategy)

        # 统计
        self._start_time = time.time()
        self._modality_counts: dict[str, int] = {}

    def _register_sensors(self) -> None:
        """注册所有传感器到引擎。"""
        self.engine.register_sensor(self.text_sensor)
        self.engine.register_sensor(self.file_sensor)
        self.engine.register_sensor(self.env_sensor)
        self.engine.register_sensor(self.audio_sensor)
        self.engine.register_sensor(self.vision_sensor)
        self.engine.register_sensor(self.api_sensor)
        self.engine.register_sensor(self.event_sensor)

    # ── 公共 API ────────────────────────────────────────────────────────

    def tick(self) -> list[PerceptionEvent]:
        """执行一次感知周期。"""
        events = self.engine.tick()

        # 统计
        for event in events:
            if event.observation:
                modality = event.observation.modality.name
                self._modality_counts[modality] = self._modality_counts.get(modality, 0) + 1

        return events

    def feed_text(self, text: str) -> None:
        """输入文本。"""
        self.text_sensor.feed(text)

    def feed_audio(self, audio_data: Any, transcription: str = "") -> None:
        """输入音频。"""
        self.audio_sensor.feed(audio_data, transcription)

    def feed_vision(self, image_data: Any, description: str = "") -> None:
        """输入视觉。"""
        self.vision_sensor.feed(image_data, description)

    def feed_api(self, response: dict[str, Any]) -> None:
        """输入 API 响应。"""
        self.api_sensor.feed(response)

    def emit_event(self, event_type: str, payload: Any = None) -> None:
        """发出内部事件。"""
        self.event_sensor.emit(event_type, payload)

    def watch_file(self, path: str) -> None:
        """监控文件。"""
        self.file_sensor.watch(path)

    def watch_directory(self, path: str) -> None:
        """监控目录。"""
        self.file_sensor.watch_directory(path)

    def fuse_modalities(self, observations: list[ModalObservation]) -> ModalObservation:
        """融合多个模态的观察。"""
        fused = self.fusion.fuse(observations)
        return ModalObservation(
            modality="fused",
            content=fused.fused_content,
            confidence=fused.fused_confidence,
        )

    def get_sensor_health(self) -> dict[str, dict]:
        """获取所有传感器健康状态。"""
        report = {}
        for name, sensor in self.engine.sensors.items():
            if hasattr(sensor, "get_health"):
                h = sensor.get_health()
                report[name] = {
                    "status": h.status.value,
                    "collected": h.observations_collected,
                    "errors": h.errors,
                }
        return report

    def get_stats(self) -> dict[str, Any]:
        """获取感知统计。"""
        engine_state = self.engine.get_state()
        fusion_stats = self.fusion.get_stats()
        return {
            **engine_state,
            **fusion_stats,
            "modality_distribution": dict(self._modality_counts),
            "uptime_seconds": time.time() - self._start_time,
            "sensor_count": len(self.engine.sensors),
        }

    def get_status_report(self) -> str:
        """生成状态报告。"""
        stats = self.get_stats()
        health = self.get_sensor_health()
        lines = [
            "=" * 50,
            "多模态感知状态报告",
            "=" * 50,
            f"总观察数: {stats.get('total_observations', 0)}",
            f"总事件数: {stats.get('total_events', 0)}",
            f"感知轮次: {stats.get('tick_count', 0)}",
            f"传感器数: {stats.get('sensor_count', 0)}",
            f"融合次数: {stats.get('total_fusions', 0)}",
            f"冲突检测: {stats.get('conflicts_detected', 0)}",
            "",
            "传感器健康:",
        ]
        for name, h in health.items():
            lines.append(f"  {name}: {h['status']} (采集={h['collected']}, 错误={h['errors']})")
        lines.append("")
        lines.append(f"运行时长: {stats.get('uptime_seconds', 0):.1f}秒")
        lines.append("=" * 50)
        return "\n".join(lines)
