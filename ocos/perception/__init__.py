"""Phase 52: Perception System.

OCOS 的第一感官系统 — 从外部世界采集信号，提取语义，验证后进入认知环。

核心管线:
    Sensors[] → poll() → Observations[] → SemanticExtractor → PerceptionValidator → EventBus → Attention

核心原则:
    PS52-01: Perception ≠ Truth — 感知只是产生 Observation
    PS52-02: Sensor Isolation — 传感器失败不影响其他模块
    PS52-03: Confidence Required — 每条观察携带置信度
    PS52-04: Validation Before Belief — 验证后才进入世界模型

组件:
    - TextSensor: 文本输入感知
    - FileSensor: 文件系统变化感知
    - EnvironmentSensor: 环境/资源感知 (内感)
    - PerceptionEngine: 感知引擎主循环
    - SemanticExtractor: 语义提取
    - ObservationBuilder: Observation 工厂
    - PerceptionValidator: 验证门控
"""

from ocos.perception.sensor_types import (
    SensorModality, SensorStatus, SensorConfig, SensorHealth,
    ObservationType, Observation,
    SemanticFragment,
    PerceptionEventType, PerceptionEvent,
    ValidationVerdict, ValidationResult,
)
from ocos.perception.text_sensor import TextSensor
from ocos.perception.file_sensor import FileSensor
from ocos.perception.environment_sensor import EnvironmentSensor, EnvironmentSnapshot
from ocos.perception.perception_engine import PerceptionEngine
from ocos.perception.semantic_extractor import SemanticExtractor, ObservationBuilder
from ocos.perception.perception_validator import PerceptionValidator


__all__ = [
    # Types
    "SensorModality", "SensorStatus", "SensorConfig", "SensorHealth",
    "ObservationType", "Observation",
    "SemanticFragment",
    "PerceptionEventType", "PerceptionEvent",
    "ValidationVerdict", "ValidationResult",
    # Sensors
    "TextSensor", "FileSensor", "EnvironmentSensor", "EnvironmentSnapshot",
    # Engine
    "PerceptionEngine",
    # Processing
    "SemanticExtractor", "ObservationBuilder",
    # Validation
    "PerceptionValidator",
]
