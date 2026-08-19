"""Phase 50: CognitiveDriftDetector — 认知漂移检测。

长期运行中检测 OCOS 的状态漂移。

检测维度:
    - 风险偏好漂移 (Phase 48 CognitiveSignature)
    - 决策风格变化 (Phase 43 Decision)
    - 用户模型漂移 (Phase 48 Personalization)
    - 交互模式异常 (Phase 48 InteractionStyle)

OS50-03: Drift Detection ≠ Correction
    检测漂移→报告→建议人工审查。
    不自动回滚 (自动回滚是 Phase 47 Evolution 的职责)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.os_v1.os_types import (
    DriftSignal, DriftReport, DriftSeverity,
)


@dataclass
class DriftBaseline:
    """漂移基线——某一时刻的状态快照，用于后续比较。"""
    risk_tolerance: str = ""
    decision_style: str = ""
    interaction_style: str = ""
    tick_id: int = 0


@dataclass
class CognitiveDriftDetector:
    """认知漂移检测器。

    长时间运行的 OCOS 可能逐渐偏离初始状态。
    检测器建立基线→定期对比→生成报告。

    OS50-03: 只检测和报告。不自动干预。
    """

    baselines: list[DriftBaseline] = field(default_factory=list)
    reports: list[DriftReport] = field(default_factory=list)
    report_counter: int = 0

    def set_baseline(
        self, tick_id: int, risk_tolerance: str,
        decision_style: str, interaction_style: str = "",
    ) -> DriftBaseline:
        """设定漂移基线。"""
        baseline = DriftBaseline(
            risk_tolerance=risk_tolerance,
            decision_style=decision_style,
            interaction_style=interaction_style,
            tick_id=tick_id,
        )
        self.baselines.append(baseline)
        if len(self.baselines) > 10:
            self.baselines = self.baselines[-10:]
        return baseline

    def check_drift(
        self, tick_id: int, risk_tolerance: str,
        decision_style: str, interaction_style: str = "",
    ) -> DriftReport:
        """检测当前状态与基线的漂移。"""
        if not self.baselines:
            return DriftReport(report_id=f"drift:{tick_id}", tick_id=tick_id)

        baseline = self.baselines[-1]
        signals: list[DriftSignal] = []
        severity_max = DriftSeverity.NONE

        # 1. 风险偏好漂移
        if baseline.risk_tolerance != risk_tolerance:
            sev = self._severity_for_dimension(
                baseline.risk_tolerance, risk_tolerance, "risk"
            )
            signals.append(DriftSignal(
                dimension="risk_tolerance",
                previous_value=baseline.risk_tolerance,
                current_value=risk_tolerance,
                severity=sev,
                description=f"Risk tolerance shifted: {baseline.risk_tolerance} → {risk_tolerance}",
            ))
            severity_max = self._max_severity(severity_max, sev)

        # 2. 决策风格漂移
        if baseline.decision_style != decision_style:
            sev = self._severity_for_dimension(
                baseline.decision_style, decision_style, "decision"
            )
            signals.append(DriftSignal(
                dimension="decision_style",
                previous_value=baseline.decision_style,
                current_value=decision_style,
                severity=sev,
                description=f"Decision style changed: {baseline.decision_style} → {decision_style}",
            ))
            severity_max = self._max_severity(severity_max, sev)

        # 3. 交互风格漂移
        if baseline.interaction_style and interaction_style:
            if baseline.interaction_style != interaction_style:
                sev = DriftSeverity.MODERATE
                signals.append(DriftSignal(
                    dimension="interaction_style",
                    previous_value=baseline.interaction_style,
                    current_value=interaction_style,
                    severity=sev,
                    description=f"Interaction style changed: {baseline.interaction_style} → {interaction_style}",
                ))
                severity_max = self._max_severity(severity_max, sev)

        self.report_counter += 1
        report = DriftReport(
            report_id=f"drift:{tick_id}:{self.report_counter}",
            tick_id=tick_id,
            signals=signals,
            overall_severity=severity_max,
            is_significant=severity_max in (DriftSeverity.SIGNIFICANT, DriftSeverity.CRITICAL),
            recommendation=self._make_recommendation(signals),
        )
        self.reports.append(report)
        return report

    def _severity_for_dimension(
        self, old: str, new: str, dimension: str,
    ) -> DriftSeverity:
        """评估单个维度的漂移严重度。"""
        if dimension == "risk":
            # conservative → bold = 显著
            extremes = {"conservative", "bold"}
            if old in extremes and new in extremes and old != new:
                return DriftSeverity.SIGNIFICANT
            return DriftSeverity.MODERATE
        if dimension == "decision":
            return DriftSeverity.MODERATE
        return DriftSeverity.MILD

    @staticmethod
    def _max_severity(a: DriftSeverity, b: DriftSeverity) -> DriftSeverity:
        order = [
            DriftSeverity.NONE,
            DriftSeverity.MILD,
            DriftSeverity.MODERATE,
            DriftSeverity.SIGNIFICANT,
            DriftSeverity.CRITICAL,
        ]
        return order[max(order.index(a), order.index(b))]

    def _make_recommendation(self, signals: list[DriftSignal]) -> str:
        if not signals:
            return "No drift detected"
        if len(signals) == 1:
            return f"Review {signals[0].dimension} change — may be intentional evolution"
        dims = [s.dimension for s in signals]
        return f"Multiple dimensions shifted ({', '.join(dims)}) — recommend full audit"

    @property
    def latest_report(self) -> DriftReport | None:
        return self.reports[-1] if self.reports else None

    @property
    def significant_drifts(self) -> list[DriftReport]:
        return [r for r in self.reports if r.is_significant]


__all__ = ["DriftBaseline", "CognitiveDriftDetector"]
