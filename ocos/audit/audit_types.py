"""Phase 51: System Integration Audit — Types.

不建新器官。验证现有器官是否组成生命系统。

核心边界:
    AU51-01: Audit ≠ Modification — 只观察和报告，不修改
    AU51-02: Trace ≠ Execution — 追踪连接路径，不运行生产数据
    AU51-03: Report ≠ Prescription — 报告发现，不自动生成修复
    AU51-04: Gap ≠ Blocker — 缺口不阻止运行，只记录
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Layer Status
# ═══════════════════════════════════════════════════════════════════════════════


class LayerStatus(Enum):
    """层状态。"""
    EXISTS = "exists"               # 模块文件存在
    TESTED = "tested"               # 有测试覆盖
    CONNECTED = "connected"         # 已接入认知循环
    VERIFIED = "verified"           # 连接已验证
    MISSING = "missing"             # 设计中有但目前缺失


class ConnectionStatus(Enum):
    """连接状态。"""
    NONE = "none"                   # 无连接
    IMPORTABLE = "importable"       # 可导入
    WIRED = "wired"                 # 已连线
    TRACED = "traced"               # 已追踪验证
    BROKEN = "broken"               # 预期连接但断了


# ═══════════════════════════════════════════════════════════════════════════════
# Architecture Layer
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LayerSpec:
    """单层规格。"""
    phase: int = 0
    name: str = ""                  # 层名 (Runtime / Self / Memory / ...)
    design_goal: str = ""           # 设计目标
    module_path: str = ""           # 模块路径
    status: LayerStatus = LayerStatus.EXISTS
    test_file: str = ""             # 测试文件
    test_count: int = 0             # 测试数量
    connections_in: list[str] = field(default_factory=list)   # 入边 (谁调用它)
    connections_out: list[str] = field(default_factory=list)  # 出边 (它调用谁)
    frozen_boundaries: list[str] = field(default_factory=list)  # 冻结边界
    notes: str = ""
    audit_result: str = ""          # 审计发现


# ═══════════════════════════════════════════════════════════════════════════════
# Capability Matrix
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CapabilityMatrix:
    """完整能力矩阵 — 12 层 × 设计目标 vs 实际状态。"""
    layers: list[LayerSpec] = field(default_factory=list)
    total_layers: int = 0
    existing_count: int = 0
    connected_count: int = 0
    verified_count: int = 0
    missing_count: int = 0
    overall_score: float = 0.0      # [0,1]


# ═══════════════════════════════════════════════════════════════════════════════
# Integration Trace
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TraceHop:
    """追踪中的一跳。"""
    from_layer: str = ""
    to_layer: str = ""
    via: str = ""                   # 接口名 / 方法名
    status: ConnectionStatus = ConnectionStatus.NONE
    detail: str = ""


@dataclass
class IntegrationTrace:
    """一次完整跨层追踪。"""
    trace_id: str = ""
    name: str = ""                  # 追踪场景名
    path: list[TraceHop] = field(default_factory=list)
    complete: bool = False          # 是否完成全链路
    broken_at: int = -1             # -1 = 无断裂
    hop_count: int = 0
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary Violation
# ═══════════════════════════════════════════════════════════════════════════════


class ViolationSeverity(Enum):
    """违规严重度。"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class BoundaryViolation:
    """边界违规记录。"""
    boundary: str = ""              # 被违反的边界
    layer: str = ""                 # 发生违规的层
    description: str = ""
    severity: ViolationSeverity = ViolationSeverity.INFO
    evidence: str = ""              # 违规证据


# ═══════════════════════════════════════════════════════════════════════════════
# Gap Report
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class GapReport:
    """能力缺口报告。"""
    gap_id: str = ""
    category: str = ""              # perception / action / memory / decision / ...
    description: str = ""
    impact: str = ""                # 影响评估
    suggested_phase: str = ""       # 建议哪一阶段填补
    priority: str = "low"           # low / medium / high / critical


# ═══════════════════════════════════════════════════════════════════════════════
# Task Simulation
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TaskStep:
    """任务模拟中的一步。"""
    step_id: int = 0
    layer: str = ""                 # 应参与的层
    action: str = ""                # 动作描述
    expected: str = ""              # 期望输出
    actual: str = ""                # 实际输出
    passed: bool = False
    evidence: str = ""              # 验证依据


@dataclass
class TaskSimulation:
    """一次完整的任务模拟。"""
    task_id: str = ""
    task_name: str = ""
    description: str = ""
    steps: list[TaskStep] = field(default_factory=list)
    passed: bool = False
    layers_involved: list[str] = field(default_factory=list)
    layers_missing: list[str] = field(default_factory=list)
    duration_ticks: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Report
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AuditReport:
    """完整审计报告。"""
    version: str = "1.0.0"
    audit_date: str = ""
    capability_matrix: CapabilityMatrix = field(default_factory=CapabilityMatrix)
    integration_traces: list[IntegrationTrace] = field(default_factory=list)
    boundary_violations: list[BoundaryViolation] = field(default_factory=list)
    gap_reports: list[GapReport] = field(default_factory=list)
    task_simulations: list[TaskSimulation] = field(default_factory=list)
    overall_grade: str = ""         # PASS / PASS_WITH_GAPS / FAIL
    risk_assessment: str = ""
    v1_1_roadmap: list[str] = field(default_factory=list)
    summary: str = ""


__all__ = [
    "LayerStatus", "ConnectionStatus",
    "LayerSpec", "CapabilityMatrix",
    "TraceHop", "IntegrationTrace",
    "ViolationSeverity", "BoundaryViolation",
    "GapReport",
    "TaskStep", "TaskSimulation",
    "AuditReport",
]
