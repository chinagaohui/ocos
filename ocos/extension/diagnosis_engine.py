"""Phase 44: DiagnosisEngine — 扩展健康诊断。

监控:
    - 扩展健康状态
    - 接口状态
    - 性能变化
    - 认知冲突
    - 错误率
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import HealthStatus, HealthReport, ExtensionState


@dataclass
class DiagnosisEngine:
    """诊断引擎 — 检查已集成扩展的运行健康。

    产出 HealthReport。
    """

    _reports: dict[str, list[HealthReport]] = field(default_factory=dict)
    error_threshold: int = 3   # 连续错误数阈值（≥ 此值 → UNSTABLE）
    degrade_threshold: int = 1  # 连续错误数阈值（≥ 此值 → DEGRADED）

    def check(self, candidate_id: str, error_count: int = 0,
              performance_score: float = 1.0,
              cognitive_conflicts: list[str] | None = None) -> HealthReport:
        """执行一次健康检查。"""
        conflicts = cognitive_conflicts or []

        # 判定状态
        if error_count >= self.error_threshold:
            status = HealthStatus.UNSTABLE
        elif error_count >= self.degrade_threshold:
            status = HealthStatus.DEGRADED
        elif performance_score < 0.4:
            status = HealthStatus.DEGRADED
        elif conflicts:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        report = HealthReport(
            candidate_id=candidate_id,
            status=status,
            error_count=error_count,
            performance_score=performance_score,
            cognitive_conflicts=conflicts,
        )

        if candidate_id not in self._reports:
            self._reports[candidate_id] = []
        self._reports[candidate_id].append(report)
        return report

    def latest(self, candidate_id: str) -> HealthReport | None:
        history = self._reports.get(candidate_id, [])
        return history[-1] if history else None

    def is_healthy(self, candidate_id: str) -> bool:
        report = self.latest(candidate_id)
        return report is not None and report.status == HealthStatus.HEALTHY


__all__ = ["DiagnosisEngine"]
