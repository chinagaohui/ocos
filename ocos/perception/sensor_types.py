"""Phase 52: Perception System — Types.

OCOS 的第一感官系统。

核心原则:
    PS52-01: Perception ≠ Truth — 感知产生 Observation，不是事实
    PS52-02: Sensor Isolation — 传感器失败不影响其他模块
    PS52-03: Confidence Required — 每条观察携带置信度
    PS52-04: Validation Before Belief — WorldValidator 决定是否进入世界模型

类似人脑:
    眼睛看到东西 ≠ 大脑相信 — 中间经过层层过滤和校验
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time as _time


# ═══════════════════════════════════════════════════════════════════════════════
# Sensor Types
# ═══════════════════════════════════════════════════════════════════════════════


class SensorModality(Enum):
    """感知模态 — OCOS 的"感官类型"。

    对应不同的输入渠道:
        TEXT    = 文本输入 (用户消息、文档)
        FILE    = 文件系统变化
        API     = 外部 API 响应
        ENV     = 环境信号 (系统指标、时间变化)
        EVENT   = 内部事件流
        UNKNOWN = 未识别输入
    """
    TEXT = "text"
    FILE = "file"
    API = "api"
    ENV = "env"
    EVENT = "event"
    UNKNOWN = "unknown"


class SensorStatus(Enum):
    ACTIVE = "active"       # 正常采集
    DEGRADED = "degraded"   # 部分功能异常
    DISCONNECTED = "disconnected"  # 连接中断
    ERROR = "error"         # 致命错误
    STOPPED = "stopped"     # 手动停止


# ═══════════════════════════════════════════════════════════════════════════════
# Sensor Base
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SensorConfig:
    """传感器配置。

    每个 Sensor 有独立的:
        - poll_interval: 采集间隔 (秒)
        - max_observations_per_poll: 单次最大观察数
        - confidence_threshold: 低于此置信度的观察丢弃
        - modalities: 支持的模态
    """
    sensor_name: str = ""
    poll_interval: float = 1.0
    max_observations_per_poll: int = 100
    confidence_threshold: float = 0.3
    modalities: list[SensorModality] = field(default_factory=list)
    enabled: bool = True

    def supports(self, modality: SensorModality) -> bool:
        return modality in self.modalities


@dataclass
class SensorHealth:
    """传感器健康状态 (PS52-02: 隔离监控)。"""
    sensor_name: str = ""
    status: SensorStatus = SensorStatus.ACTIVE
    observations_collected: int = 0
    errors: int = 0
    last_poll_at: float = 0.0
    last_error_at: float = 0.0
    last_error_msg: str = ""
    avg_latency: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Observation
# ═══════════════════════════════════════════════════════════════════════════════


class ObservationType(Enum):
    RAW = "raw"               # 原始数据，未处理
    STRUCTURED = "structured"  # 结构化后
    SEMANTIC = "semantic"      # 语义提取后
    ANOMALY = "anomaly"        # 异常感知
    PATTERN = "pattern"        # 模式识别
    CHANGE = "change"          # 变化检测


@dataclass
class Observation:
    """感知观察 — PS52-01: 这是假设，不是真理。

    每条观察:
        - 携带来源传感器
        - 携带置信度 (PS52-03)
        - 携带时间戳
        - 携带原始数据副本
        - 可以被 WorldValidator 拒绝

    Example:
        Observation(
            modality=SensorModality.TEXT,
            content="用户说要做股票分析",
            confidence=0.9,
            source_sensor="text_sensor",
        )
    """
    id: str = field(default_factory=lambda: f"obs-{_time.time()}")
    modality: SensorModality = SensorModality.UNKNOWN
    type: ObservationType = ObservationType.RAW
    content: Any = None
    confidence: float = 0.5
    source_sensor: str = ""
    timestamp: float = field(default_factory=_time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_payload: Any = None

    @property
    def is_reliable(self) -> bool:
        """置信度是否达到可靠阈值。"""
        return self.confidence >= 0.7

    @property
    def age_seconds(self) -> float:
        return _time.time() - self.timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# Semantic Fragment
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SemanticFragment:
    """语义片段 — 从 Observation 中提取的有意义信息。

    例如从 "用户想开发股票分析系统" 中提取:
        intent: develop
        domain: stock_analysis
        entities: ["stock", "analysis"]
        priority: high
    """
    text: str = ""
    intent: str = ""
    domain: str = ""
    entities: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    priority_hint: str = "normal"  # low/normal/high/urgent
    confidence: float = 0.5
    source_observation_id: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Perception Event
# ═══════════════════════════════════════════════════════════════════════════════


class PerceptionEventType(Enum):
    OBSERVATION_READY = "observation_ready"   # 新观察就绪
    SEMANTIC_EXTRACTED = "semantic_extracted"  # 语义提取完成
    ANOMALY_DETECTED = "anomaly_detected"      # 异常发现
    SENSOR_STATUS_CHANGE = "sensor_status_change"  # 传感器状态变化
    VALIDATION_RESULT = "validation_result"    # 验证结果


@dataclass
class PerceptionEvent:
    """感知事件 — 从 Perception 流向 EventBus。

    这是 OCOS 的内部事件，触发 Attention → Working Memory → Decision 链。
    """
    type: PerceptionEventType = PerceptionEventType.OBSERVATION_READY
    observation: Observation | None = None
    semantic: SemanticFragment | None = None
    sensor_name: str = ""
    timestamp: float = field(default_factory=_time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Result (PS52-04)
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationVerdict(Enum):
    ACCEPTED = "accepted"              # 进入世界模型
    REJECTED = "rejected"              # 丢弃
    NEEDS_CONFIRMATION = "needs_confirmation"  # 需要人工确认
    DEFERRED = "deferred"              # 暂存，待更多证据
    CONFLICT = "conflict"              # 与现有知识冲突


@dataclass
class ValidationResult:
    """PS52-04: WorldValidator 的验证结果。

    决定 Observation 是否进入 World Model:
        - ACCEPTED → 更新世界模型
        - REJECTED → 丢弃
        - CONFLICT → 与现有知识冲突，标记待解决
    """
    observation_id: str = ""
    verdict: ValidationVerdict = ValidationVerdict.ACCEPTED
    reason: str = ""
    conflicts_with: list[str] = field(default_factory=list)  # 冲突的知识 ID
    supporting_evidence: list[str] = field(default_factory=list)
    confidence_adjustment: float = 0.0  # 对置信度的调整


__all__ = [
    "SensorModality", "SensorStatus", "SensorConfig", "SensorHealth",
    "ObservationType", "Observation",
    "SemanticFragment",
    "PerceptionEventType", "PerceptionEvent",
    "ValidationVerdict", "ValidationResult",
]
