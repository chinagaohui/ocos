"""Phase 52: TextSensor — 文本输入感知。

处理: 用户消息、文档、聊天记录等文本输入。

PS52-01: 文本传感器只负责捕获输入，不做语义理解。
    语义提取交给 SemanticExtractor，验证交给 PerceptionValidator。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
import time as _time

from ocos.perception.sensor_types import (
    Observation, ObservationType,
    SensorConfig, SensorHealth,
    SensorModality, SensorStatus,
)


@dataclass
class TextSensor:
    """文本传感器 — OCOS 的"耳朵"。

    职责:
        - 接收文本输入
        - 检测输入模式 (单条/对话/文档)
        - 产生 Raw Observation
        - 不负责语义理解 (交给 SemanticExtractor)

    输入缓冲区 — 支持批量读取，兼容事件驱动的输入流。
    """

    config: SensorConfig = field(default_factory=lambda: SensorConfig(
        sensor_name="text_sensor",
        poll_interval=0.1,
        max_observations_per_poll=50,
        confidence_threshold=0.5,
        modalities=[SensorModality.TEXT],
    ))
    health: SensorHealth = field(default_factory=lambda: SensorHealth(
        sensor_name="text_sensor",
    ))
    _buffer: deque[str] = field(default_factory=deque)
    _cursor: int = 0  # 上次读取位置

    def feed(self, text: str) -> None:
        """向传感器输入文本。"""
        self._buffer.append(text)

    def feed_batch(self, texts: list[str]) -> None:
        """批量输入。"""
        self._buffer.extend(texts)

    def poll(self) -> list[Observation]:
        """采集当前缓冲区中的文本。

        返回 Observation 列表 — 不调用 SemanticExtractor。
        """
        if self.config.enabled is False:
            return []

        observations: list[Observation] = []
        limit = self.config.max_observations_per_poll
        count = 0

        while self._buffer and count < limit:
            text = self._buffer.popleft()
            if not text.strip():
                continue

            obs = Observation(
                id=f"txt-{self._cursor}",
                modality=SensorModality.TEXT,
                type=ObservationType.RAW,
                content=text,
                confidence=self._estimate_confidence(text),
                source_sensor=self.config.sensor_name,
                raw_payload={"length": len(text)},
            )
            observations.append(obs)
            self._cursor += 1
            count += 1

        self.health.last_poll_at = _time.time()
        self.health.observations_collected += len(observations)
        return observations

    def _estimate_confidence(self, text: str) -> float:
        """根据文本质量估算置信度。

        简单启发式:
            - 太短 (< 5 char) → 低置信
            - 正常长度 → 标准置信
            - 过长 → 高置信 (可能是结构化输入)
        """
        length = len(text.strip())
        if length < 5:
            return 0.3
        elif length < 100:
            return 0.8
        else:
            return 0.95

    def has_pending(self) -> bool:
        return len(self._buffer) > 0

    @property
    def pending_count(self) -> int:
        return len(self._buffer)

    def clear_buffer(self) -> None:
        self._buffer.clear()

    def get_health(self) -> SensorHealth:
        return self.health


__all__ = ["TextSensor"]
