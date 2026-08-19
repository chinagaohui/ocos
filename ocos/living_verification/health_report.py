"""Phase 57: HealthReport — 系统健康报告。

整合所有验证层输出:
    - SimulationEngine stats
    - TraceAudit results
    - FailureInjector results
    - LongevityTest results
    - Benchmark results

输出统一的 LivingSystemHealth 报告。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class SystemGrade(str, Enum):
    """系统等级。"""
    ALIVE = "alive"            # 活体 — 所有指标通过
    DEGRADED = "degraded"      # 降级 — 部分失败但可恢复
    UNSTABLE = "unstable"      # 不稳定 — 多项失败
    DEAD = "dead"              # 死亡 — 关键指标失败


@dataclass
class HealthDimension:
    """单个健康维度。"""
    name: str
    score: float          # 0.0 - 1.0
    passed: bool
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class LivingSystemHealth:
    """LV57 活体系统健康报告。"""
    report_id: str = field(default_factory=lambda: f"health-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)

    # 六大维度
    dimensions: list[HealthDimension] = field(default_factory=list)

    # 聚合
    overall_score: float = 0.0
    grade: SystemGrade = SystemGrade.DEAD

    # LV57-01~06 验证状态
    lv57_01_pass: bool = False   # 全链路闭环
    lv57_02_pass: bool = False   # 长期运行
    lv57_03_pass: bool = False   # 故障恢复
    lv57_04_pass: bool = False   # 能力真实性
    lv57_05_pass: bool = False   # 演化安全
    lv57_06_pass: bool = False   # 人格连续性

    @property
    def is_alive(self) -> bool:
        return self.grade == SystemGrade.ALIVE

    @property
    def all_pass(self) -> bool:
        return all(d.passed for d in self.dimensions)


@dataclass
class HealthReportGenerator:
    """LV57: 健康报告生成器。"""

    def generate(self,
                 simulation_stats: dict | None = None,
                 trace_audit_result: dict | None = None,
                 injection_report: dict | None = None,
                 longevity_metrics: dict | None = None,
                 benchmark_report: dict | None = None,
                 ) -> LivingSystemHealth:
        """整合所有验证层输出，生成统一健康报告。"""
        report = LivingSystemHealth()
        dimensions = []

        # LV57-01: 全链路闭环
        d01 = self._eval_trace_audit(trace_audit_result)
        dimensions.append(d01)
        report.lv57_01_pass = d01.passed

        # LV57-02: 长期运行
        d02 = self._eval_longevity(longevity_metrics)
        dimensions.append(d02)
        report.lv57_02_pass = d02.passed

        # LV57-03: 故障恢复
        d03 = self._eval_failure_injection(injection_report)
        dimensions.append(d03)
        report.lv57_03_pass = d03.passed

        # LV57-04: 能力真实性
        d04 = self._eval_capability_realness(benchmark_report, simulation_stats)
        dimensions.append(d04)
        report.lv57_04_pass = d04.passed

        # LV57-05: 演化安全
        d05 = self._eval_evolution_safety(injection_report, longevity_metrics)
        dimensions.append(d05)
        report.lv57_05_pass = d05.passed

        # LV57-06: 人格连续性
        d06 = self._eval_identity_continuity(longevity_metrics)
        dimensions.append(d06)
        report.lv57_06_pass = d06.passed

        report.dimensions = dimensions

        # 聚合
        scores = [d.score for d in dimensions]
        report.overall_score = sum(scores) / len(scores) if scores else 0.0

        if report.overall_score >= 0.90 and all(d.passed for d in dimensions):
            report.grade = SystemGrade.ALIVE
        elif report.overall_score >= 0.70:
            report.grade = SystemGrade.DEGRADED
        elif report.overall_score >= 0.40:
            report.grade = SystemGrade.UNSTABLE
        else:
            report.grade = SystemGrade.DEAD

        return report

    def _eval_trace_audit(self, audit: dict | None) -> HealthDimension:
        if not audit:
            return HealthDimension("LV57-01 全链路闭环", 0.0, False,
                                   warnings=["no trace audit data"])
        completeness = audit.get("causal_chain_complete", 0.0)
        passed = completeness >= 0.90
        return HealthDimension(
            "LV57-01 全链路闭环", completeness, passed,
            details={"causal_completeness": completeness,
                     "traced_steps": audit.get("traced_steps", 0),
                     "untraced_steps": audit.get("untraced_steps", 0)},
        )

    def _eval_longevity(self, metrics: dict | None) -> HealthDimension:
        if not metrics:
            return HealthDimension("LV57-02 长期运行", 0.0, False,
                                   warnings=["no longevity data"])
        passed = metrics.get("passed", False)
        score = metrics.get("continuity_score", 0.0)
        warnings = list(metrics.get("failures", []))
        return HealthDimension(
            "LV57-02 长期运行", score, passed,
            details={"total_ticks": metrics.get("total_ticks", 0)},
            warnings=warnings,
        )

    def _eval_failure_injection(self, injection: dict | None) -> HealthDimension:
        if not injection:
            return HealthDimension("LV57-03 故障恢复", 0.0, False,
                                   warnings=["no injection data"])
        pass_rate = injection.get("pass_rate", 0.0)
        survived = injection.get("system_survived", False)
        breaches = injection.get("no_security_breach", True)
        passed = pass_rate >= 0.90 and survived and breaches
        warnings = []
        if injection.get("passed_through", 0) > 0:
            warnings.append(f"{injection['passed_through']} injections passed through")
        return HealthDimension(
            "LV57-03 故障恢复", pass_rate, passed,
            details={"pass_rate": pass_rate, "survived": survived},
            warnings=warnings,
        )

    def _eval_capability_realness(self, benchmark: dict | None,
                                  sim_stats: dict | None) -> HealthDimension:
        if not benchmark and not sim_stats:
            return HealthDimension("LV57-04 能力真实性", 0.0, False,
                                   warnings=["no benchmark data"])
        score = benchmark.get("overall_pass_rate", 0.0) if benchmark else 0.50
        passed = score >= 0.80
        return HealthDimension(
            "LV57-04 能力真实性", score, passed,
            details={"benchmark_pass_rate": score},
        )

    def _eval_evolution_safety(self, injection: dict | None,
                               longevity: dict | None) -> HealthDimension:
        safe = True
        warnings = []

        if injection and injection.get("passed_through", 0) > 0:
            safe = False
            warnings.append("security breach detected")

        if longevity and longevity.get("permission_escalation_detected"):
            safe = False
            warnings.append("permission escalation detected")

        if longevity and longevity.get("identity_drift_detected"):
            safe = False
            warnings.append("identity drift detected")

        score = 1.0 if safe else 0.5 if not warnings else 0.0
        return HealthDimension(
            "LV57-05 演化安全", score, safe,
            warnings=warnings,
        )

    def _eval_identity_continuity(self, longevity: dict | None) -> HealthDimension:
        if not longevity:
            return HealthDimension("LV57-06 人格连续性", 0.0, False,
                                   warnings=["no longevity data"])
        continuity = longevity.get("continuity_score", 0.0)
        passed = continuity >= 0.90
        return HealthDimension(
            "LV57-06 人格连续性", continuity, passed,
            details={"continuity_score": continuity},
        )


__all__ = ["HealthReportGenerator", "LivingSystemHealth", "HealthDimension",
           "SystemGrade"]
