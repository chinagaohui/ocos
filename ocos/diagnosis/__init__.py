"""Phase 56: Self Diagnosis & Repair.

OCOS 的免疫系统 — 发现异常、诊断原因、提出修复、审核、沙箱验证、执行、记住经验。

核心原则:
    SD56-01: Diagnosis ≠ Decision — 发现异常 ≠ 自动改变目标
    SD56-02: Repair ≠ Evolution — 修复恢复原状 ≠ 演化改变能力
    SD56-03: Repair ≠ Self Rewrite — 禁止修改 Identity/Constitution/权限
    SD56-04: Repair requires Snapshot — 任何修复前必须 checkpoint
    SD56-05: Failure Isolation — 单模块故障不拖垮整体
    SD56-06: Learning From Repair — 修复结果进入 EventMemory → Wisdom

架构:
    Runtime Loop
        ↓
    SystemProbe.capture() → SystemSnapshot
        ↓
    FaultDetector.feed() → [FaultSignal]
        ↓
    Diagnosis → DiagnosisReport
        ↓
    RepairProposer.propose() → [RepairProposal]
        ↓
    RepairValidator.validate() → approve/reject/needs_review
        ↓
    RepairSandbox.validate() → SandboxReport
        ↓
    RepairExecutor.execute()
        ├── create_checkpoint()          (SD56-04)
        ├── execute_step() × N
        ├── verify()
        └── commit / rollback()
        ↓
    RepairMemory.record() → RepairRecord   (SD56-06)
        ↓
    EventMemory / Wisdom

修复类型:
    ALLOWED:  RECONNECT / RELOAD / REINDEX / CLEAR_CACHE / RESYNC /
              PAUSE_RESUME / REBUILD_INDEX / ROLLBACK / RESTART_SUBSYS / REINIT

    FORBIDDEN: modify_identity / rewrite_constitution / remove_permission /
               change_core_values / self_rewrite / expand_capability / alter_goal_system
"""

from ocos.diagnosis.diagnosis_types import (
    FaultCategory, Severity,
    ComponentHealth, SystemSnapshot,
    FaultSignal, EvidencePoint, DiagnosisReport,
)
from ocos.diagnosis.system_probe import SystemProbe
from ocos.diagnosis.health_analyzer import HealthAnalyzer, HealthTrend
from ocos.diagnosis.fault_detector import FaultDetector, ThresholdRule
from ocos.diagnosis.repair_types import (
    RepairType, RepairStatus, RepairRisk,
    RepairProposal, RepairRecord,
)
from ocos.diagnosis.repair_proposer import RepairProposer
from ocos.diagnosis.repair_validator import (
    RepairValidator, ValidationOutcome, ValidationCode,
)
from ocos.diagnosis.repair_sandbox import (
    RepairSandbox, SandboxReport, SandboxResult,
)
from ocos.diagnosis.repair_executor import (
    RepairExecutor, ExecutionReport, ExecutorResult,
)
from ocos.diagnosis.repair_memory import RepairMemory


__all__ = [
    # Diagnosis
    "FaultCategory", "Severity",
    "ComponentHealth", "SystemSnapshot",
    "FaultSignal", "EvidencePoint", "DiagnosisReport",
    "SystemProbe",
    "HealthAnalyzer", "HealthTrend",
    "FaultDetector", "ThresholdRule",
    # Repair
    "RepairType", "RepairStatus", "RepairRisk",
    "RepairProposal", "RepairRecord",
    "RepairProposer",
    "RepairValidator", "ValidationOutcome", "ValidationCode",
    "RepairSandbox", "SandboxReport", "SandboxResult",
    "RepairExecutor", "ExecutionReport", "ExecutorResult",
    "RepairMemory",
]
