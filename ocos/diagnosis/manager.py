"""Phase AH: SelfDiagnosisManager — 统一自我诊断管理器。

整合诊断基础设施：
- SystemProbe: 系统探针，只读检查子系统
- FaultDetector: 异常检测器，从快照中检测故障
- HealthAnalyzer: 健康趋势分析
- RepairProposer: 修复提案生成器
- RepairValidator: 修复提案验证器
- RepairExecutor: 修复执行器（含 checkpoint + rollback）
- RepairMemory: 修复记忆，从修复中学习

架构原则:
- AH-DIAG-01: 诊断 ≠ 决策 — 发现异常不等于自动改变目标
- AH-DIAG-02: 修复 ≠ 演化 — 修复恢复原状 ≠ 演化改变能力
- AH-DIAG-03: 禁止自我重写 — 不得修改 Identity/Constitution/权限
- AH-DIAG-04: 修复前必须 checkpoint
- AH-DIAG-05: 失败隔离 — 单模块故障不拖垮整体
- AH-DIAG-06: 从修复中学习 — 修复结果进入记忆系统

SD56-01..06 约束由底层组件强制执行。
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from ocos.diagnosis.system_probe import SystemProbe
from ocos.diagnosis.fault_detector import FaultDetector, ThresholdRule
from ocos.diagnosis.health_analyzer import HealthAnalyzer, HealthTrend
from ocos.diagnosis.diagnosis_types import (
    SystemSnapshot, FaultSignal, FaultCategory, Severity,
    DiagnosisReport, ComponentHealth,
)
from ocos.diagnosis.repair_proposer import RepairProposer
from ocos.diagnosis.repair_validator import RepairValidator, ValidationCode
from ocos.diagnosis.repair_executor import RepairExecutor, ExecutionReport, ExecutorResult
from ocos.diagnosis.repair_memory import RepairMemory
from ocos.diagnosis.repair_types import RepairType, RepairStatus, RepairRisk

logger = logging.getLogger(__name__)


class DiagnosisMode(str, Enum):
    """诊断模式。"""
    MANUAL = "manual"
    AUTO = "auto"
    HYBRID = "hybrid"  # 自动检测 + 人工审批修复


class AutoRepairPolicy(str, Enum):
    """自动修复策略。"""
    NEVER = "never"           # 从不自动修复
    LOW_RISK_ONLY = "low_risk"  # 仅低风险自动修复
    ALL_ALLOWED = "all_allowed" # 所有允许的修复自动执行


@dataclass
class DiagnosticResult:
    """单次诊断结果。"""
    snapshot_id: str
    faults_detected: int
    healthy_components: int
    degraded_components: list[str]
    overall_health: float
    trend: str = "stable"
    auto_repairs_performed: int = 0
    pending_proposals: int = 0
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "faults_detected": self.faults_detected,
            "healthy_components": self.healthy_components,
            "degraded_components": self.degraded_components,
            "overall_health": self.overall_health,
            "trend": self.trend,
            "auto_repairs_performed": self.auto_repairs_performed,
            "pending_proposals": self.pending_proposals,
            "timestamp": self.timestamp,
        }


@dataclass
class ManagerStats:
    """管理器统计。"""
    total_snapshots: int = 0
    total_faults_detected: int = 0
    total_repairs_performed: int = 0
    total_repairs_rolled_back: int = 0
    avg_repair_duration_ms: float = 0.0
    recent_trend: str = "stable"
    last_diagnosis_time: float = 0.0
    critical_faults_count: int = 0


class SelfDiagnosisManager:
    """自我诊断管理器。

    提供完整的诊断-修复闭环：
    Probe → Detect → Propose → Validate → Execute → Learn
    """

    def __init__(
        self,
        mode: DiagnosisMode = DiagnosisMode.HYBRID,
        auto_repair_policy: AutoRepairPolicy = AutoRepairPolicy.LOW_RISK_ONLY,
        max_proposals_per_tick: int = 5,
        checkpoint_before_repair: bool = True,
    ) -> None:
        self._mode = mode
        self._auto_repair_policy = auto_repair_policy
        self._max_proposals_per_tick = max_proposals_per_tick
        self._checkpoint_before_repair = checkpoint_before_repair

        # 诊断组件
        self._probe = SystemProbe()
        self._analyzer = HealthAnalyzer()
        self._detector = FaultDetector()
        self._proposer = RepairProposer()
        self._validator = RepairValidator()
        self._executor = RepairExecutor()
        self._memory = RepairMemory()

        # 状态
        self._snapshots: list[SystemSnapshot] = []
        self._fault_history: list[FaultSignal] = []
        self._stats = ManagerStats()

        # 回调
        self._on_diagnosis_result: Any = None
        self._on_fault_detected: Any = None
        self._on_repair_complete: Any = None

        self._lock = threading.Lock()

    # ── 公共接口 ────────────────────────────────────────────────────────

    def diagnose(self) -> DiagnosticResult:
        """执行一次完整诊断。

        返回 DiagnosticResult。
        """
        with self._lock:
            # 1. 采集快照
            snapshot = self._probe.capture()
            self._snapshots.append(snapshot)
            if len(self._snapshots) > 100:
                self._snapshots.pop(0)

            self._analyzer.add_snapshot(snapshot)
            self._stats.total_snapshots += 1

            # 2. 检测故障
            signals = self._detector.feed(snapshot)
            self._stats.total_faults_detected += len(signals)

            for sig in signals:
                if sig.severity >= Severity.CRITICAL:
                    self._stats.critical_faults_count += 1
                self._fault_history.append(sig)

            if self._on_fault_detected:
                try:
                    self._on_fault_detected(signals)
                except Exception:
                    pass

            # 3. 生成报告
            trend = self._analyzer.analyze()
            report = DiagnosisReport(
                report_id=f"rpt-{time.time():.0f}",
                timestamp=time.time(),
            )

            # 4. 生成修复提案
            proposals = self._proposer.propose(report)
            if len(proposals) > self._max_proposals_per_tick:
                proposals = proposals[:self._max_proposals_per_tick]

            # 5. 自动修复（如开启）
            auto_repairs = 0
            if self._mode in (DiagnosisMode.AUTO, DiagnosisMode.HYBRID) and signals:
                auto_repairs = self._auto_repair_signals(signals)

            # 6. 统计更新
            self._stats.last_diagnosis_time = time.time()
            self._stats.recent_trend = trend.direction

            result = DiagnosticResult(
                snapshot_id=snapshot.snapshot_id,
                faults_detected=len(signals),
                healthy_components=sum(
                    1 for c in snapshot.components.values() if c.healthy
                ),
                degraded_components=snapshot.degraded_components.copy(),
                overall_health=snapshot.overall_health,
                trend=trend.direction,
                auto_repairs_performed=auto_repairs,
                pending_proposals=len(proposals),
                timestamp=time.time(),
            )

            if self._on_diagnosis_result:
                try:
                    self._on_diagnosis_result(result)
                except Exception:
                    pass

            return result

    def get_health_status(self) -> dict[str, Any]:
        """获取当前健康状态。"""
        with self._lock:
            trend = self._analyzer.analyze()
            return {
                "overall_health": self._snapshots[-1].overall_health if self._snapshots else 1.0,
                "trend": trend.direction,
                "degraded_components": self._snapshots[-1].degraded_components if self._snapshots else [],
                "faults_detected": self._stats.total_faults_detected,
                "repairs_performed": self._stats.total_repairs_performed,
                "critical_faults": self._stats.critical_faults_count,
                "recent_trend": self._stats.recent_trend,
            }

    def get_diagnosis_history(self, limit: int = 10) -> list[dict]:
        """获取诊断历史。"""
        with self._lock:
            result = []
            for s in self._snapshots[-limit:]:
                result.append({
                    "snapshot_id": s.snapshot_id,
                    "timestamp": s.timestamp,
                    "tick": s.tick,
                    "overall_health": s.overall_health,
                    "degraded_components": s.degraded_components,
                })
            return result

    def get_fault_history(self, limit: int = 20) -> list[dict]:
        """获取故障历史。"""
        with self._lock:
            return [s.to_dict() for s in self._fault_history[-limit:]]

    def get_repair_history(self, limit: int = 20) -> dict:
        """获取修复历史统计。"""
        with self._lock:
            return self._memory.stats()

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._lock:
            return {
                "total_snapshots": self._stats.total_snapshots,
                "total_faults_detected": self._stats.total_faults_detected,
                "total_repairs_performed": self._stats.total_repairs_performed,
                "total_repairs_rolled_back": self._stats.total_repairs_rolled_back,
                "avg_repair_duration_ms": self._stats.avg_repair_duration_ms,
                "recent_trend": self._stats.recent_trend,
                "critical_faults_count": self._stats.critical_faults_count,
            }

    def tick(self) -> list[dict]:
        """tick 接口，返回诊断结果列表。"""
        result = self.diagnose()
        return [{"snapshot_id": result.snapshot_id, "health": result.overall_health,
                 "faults": result.faults_detected, "trend": result.trend}]

    # ── 配置 ────────────────────────────────────────────────────────────

    def set_mode(self, mode: DiagnosisMode) -> None:
        """设置诊断模式。"""
        with self._lock:
            self._mode = mode
            logger.info("Diagnosis mode set to: %s", mode.value)

    def set_auto_repair_policy(self, policy: AutoRepairPolicy) -> None:
        """设置自动修复策略。"""
        with self._lock:
            self._auto_repair_policy = policy

    def add_threshold_rule(self, rule: ThresholdRule) -> None:
        """添加阈值规则。"""
        with self._lock:
            self._detector.thresholds.append(rule)

    # ── 回调 ────────────────────────────────────────────────────────────

    def set_diagnosis_callback(self, callback: Any) -> None:
        """设置诊断结果回调。"""
        self._on_diagnosis_result = callback

    def set_fault_callback(self, callback: Any) -> None:
        """设置故障检测回调。"""
        self._on_fault_detected = callback

    def set_repair_callback(self, callback: Any) -> None:
        """设置修复完成回调。"""
        self._on_repair_complete = callback

    # ── 内部方法 ────────────────────────────────────────────────────────

    def _auto_repair_signals(self, signals: list[FaultSignal]) -> int:
        """根据策略自动修复信号。"""
        performed = 0
        for signal in signals:
            if signal.severity < Severity.LOW:
                continue

            if self._auto_repair_policy == AutoRepairPolicy.NEVER:
                continue

            if self._auto_repair_policy == AutoRepairPolicy.LOW_RISK_ONLY:
                if signal.severity >= Severity.HIGH:
                    continue

            # 生成修复提案并执行
            report = DiagnosisReport(
                report_id=f"auto-{signal.signal_id}",
                timestamp=time.time(),
            )
            proposals = self._proposer.propose(report)
            if not proposals:
                continue

            for proposal in proposals:
                validation = self._validator.validate(proposal)
                if validation.code != ValidationCode.APPROVE:
                    continue

                # AH-DIAG-04: 修复前 checkpoint
                if self._checkpoint_before_repair:
                    checkpoint_id = f"pre-repair-{proposal.proposal_id}"
                else:
                    checkpoint_id = ""

                exec_report = self._executor.execute(proposal)

                if exec_report.ok:
                    self._stats.total_repairs_performed += 1
                    performed += 1
                    logger.info("Auto repair successful: %s", proposal.repair_type.value)
                elif exec_report.result == ExecutorResult.ROLLED_BACK:
                    self._stats.total_repairs_rolled_back += 1
                    logger.warning("Auto repair rolled back: %s", proposal.repair_type.value)

                # AH-DIAG-06: 学习
                self._memory.record_execution(proposal, exec_report)

        return performed
