"""Phase 56: Self Diagnosis & Repair — DiagnosTypes.

SD56-01: Diagnosis ≠ Decision — 发现异常 ≠ 自动改变目标
SD56-02: Repair ≠ Evolution — 修复恢复原状 ≠ 演化改变能力
SD56-03: Repair ≠ Self Rewrite — 禁止修改 Identity/Constitution/权限
SD56-04: Repair requires Snapshot — 任何修复前必须 checkpoint
SD56-05: Failure Isolation — 单模块故障不拖垮整体
SD56-06: Learning From Repair — 修复结果进入 EventMemory → Wisdom

诊断类型：FaultSignal, DiagnosisReport, SystemSnapshot, Severity, FaultCategory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time
import uuid


# ══════════════════════════════════════════════════
# Fault Category & Severity
# ══════════════════════════════════════════════════

class FaultCategory(str, Enum):
    """故障分类 — 不是所有异常都是故障。"""
    PERFORMANCE_DEGRADATION = "performance_degradation"
    RESOURCE_PRESSURE = "resource_pressure"
    CAPABILITY_FAILURE = "capability_failure"
    STATE_CORRUPTION = "state_corruption"
    CONNECTION_FAILURE = "connection_failure"
    CONSISTENCY_WARNING = "consistency_warning"
    STORAGE_FAILURE = "storage_failure"
    SCHEDULER_STALL = "scheduler_stall"
    MEMORY_LEAK = "memory_leak"
    IDENTITY_DRIFT = "identity_drift"


class Severity(float, Enum):
    """严重程度 0.0 ~ 1.0。"""
    NEGLIGIBLE = 0.1
    LOW = 0.3
    MODERATE = 0.5
    HIGH = 0.7
    CRITICAL = 0.9
    CATASTROPHIC = 1.0


# ══════════════════════════════════════════════════
# System Snapshot — 身体检查快照
# ══════════════════════════════════════════════════

@dataclass
class ComponentHealth:
    """单组件健康状态。"""
    component: str
    healthy: bool = True
    metrics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    last_error: str = ""


@dataclass
class SystemSnapshot:
    """系统级健康快照。

    Probe 只读，不决策 (SD56-01)。
    """
    snapshot_id: str
    timestamp: float
    tick: int

    # 各子系统指标
    components: dict[str, ComponentHealth] = field(default_factory=dict)

    # 汇总
    overall_health: float = 1.0         # 0.0=failed, 1.0=perfect
    degraded_components: list[str] = field(default_factory=list)
    failing_components: list[str] = field(default_factory=list)

    # 趋势数据 (由 HealthAnalyzer 填充)
    trend: str = ""                      # improving / stable / degrading / failing
    trend_data: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════
# Fault Signal — 异常检测输出
# ══════════════════════════════════════════════════

@dataclass
class FaultSignal:
    """检测到的异常信号。

    注意: FaultSignal ≠ DiagnosisReport — 信号只是"有问题"，
    诊断才是"什么问题、为什么"。
    """
    signal_id: str
    timestamp: float
    category: FaultCategory
    severity: Severity

    source: str = ""              # 哪个组件检测到的
    indicator: str = ""           # 具体指标名
    observed_value: float = 0.0
    threshold: float = 0.0
    description: str = ""

    # 上下文
    snapshot_ref: str = ""        # SystemSnapshot.snapshot_id
    tick: int = 0

    @property
    def is_critical(self) -> bool:
        return self.severity.value >= Severity.HIGH.value


# ══════════════════════════════════════════════════
# Diagnosis Report — 诊断报告
# ══════════════════════════════════════════════════

@dataclass
class EvidencePoint:
    """证据点。"""
    source: str
    observation: str
    value: float
    timestamp: float
    relevance: float = 0.5


@dataclass
class DiagnosisReport:
    """诊断报告 — 从 FaultSignal 推导出的完整诊断。

    包含:
        - 问题是什么
        - 证据链
        - 影响哪些组件
        - 可能原因及置信度
        - 建议的操作 (REPAIR / MONITOR / ESCALATE / IGNORE)
    """
    report_id: str
    timestamp: float

    problem: str = ""
    category: FaultCategory = FaultCategory.CONSISTENCY_WARNING
    severity: Severity = Severity.LOW

    # 证据
    evidence: list[EvidencePoint] = field(default_factory=list)

    # 影响范围
    affected_components: list[str] = field(default_factory=list)

    # 原因分析
    possible_causes: list[str] = field(default_factory=list)
    confidence: float = 0.0         # 综合置信度

    # 推荐行动
    recommendation: str = "monitor"  # repair / monitor / escalate / ignore

    # 关联
    trigger_signal_id: str = ""
    snapshot_ref: str = ""

    @property
    def needs_repair(self) -> bool:
        return (self.recommendation == "repair"
                and self.confidence > 0.5
                and self.severity.value >= Severity.MODERATE.value)


__all__ = [
    "FaultCategory", "Severity",
    "ComponentHealth", "SystemSnapshot",
    "FaultSignal", "EvidencePoint", "DiagnosisReport",
]
