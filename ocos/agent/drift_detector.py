"""Phase 37 §6: Drift Detector — 认知漂移检测器。

§6.4: 输出只能是 DriftAlert，禁止 AdaptiveAction / ParameterUpdate。

四种漂移:
  Goal Drift       — 执行结果偏离 Goal intent
  Capability Drift — 单一 Agent 使用频率 > 70%
  Preference Drift — User Alignment 持续下降
  Confidence Drift — calibration_delta 持续偏离 0

Usage:
    detector = DriftDetector()
    alert = detector.check_goal_drift(alignment_score=0.25, goal_id="g1")
    if alert and alert.severity >= DriftSeverity.HIGH:
        await notify_user(alert)
"""

from __future__ import annotations

import time
from collections import deque

from ocos.contracts.feedback_abi import (
    DriftAlert,
    DriftSeverity,
    DriftType,
)
from ocos.logging import get_logger

logger = get_logger(__name__)

# 漂移检测窗口
DRIFT_WINDOW_SIZE = 10          # 最近 N 条记录
DRIFT_ALERT_CONTINUOUS = 5      # 连续 N 次触发才报警
CAPABILITY_DRIFT_THRESHOLD = 0.7  # 单一 Agent 使用率 > 70%
PREFERENCE_DRIFT_THRESHOLD = 0.3  # User Alignment < 0.3 连续触发
CONFIDENCE_DRIFT_ABS = 0.3       # calibration_delta 绝对值 > 0.3


class DriftDetector:
    """认知漂移检测器。

    所有方法返回 Optional[DriftAlert]。
    没有任何 .adjust() / .correct() / .repair() 方法（§6.4 约束）。
    """

    def __init__(self, window_size: int = DRIFT_WINDOW_SIZE):
        self._window_size = window_size
        # 滑动窗口
        self._alignment_history: deque[float] = deque(maxlen=window_size)
        self._calibration_history: deque[float] = deque(maxlen=window_size)
        self._capability_usage: dict[str, int] = {}
        self._total_executions: int = 0
        # 连续触发计数（防误报）
        self._alignment_drift_count: int = 0
        self._confidence_drift_count: int = 0

    # ── Goal Drift ──────────────────────────────────────────────────────────

    def check_goal_drift(
        self,
        alignment_score: float,
        goal_id: str = "",
    ) -> DriftAlert | None:
        """检查 Goal Drift — 执行结果偏离目标意图。

        当 User Alignment 持续低于阈值时触发。
        """
        self._alignment_history.append(alignment_score)

        if alignment_score < PREFERENCE_DRIFT_THRESHOLD:
            self._alignment_drift_count += 1
        else:
            self._alignment_drift_count = max(0, self._alignment_drift_count - 1)

        if self._alignment_drift_count >= DRIFT_ALERT_CONTINUOUS:
            severity = (
                DriftSeverity.CRITICAL if self._alignment_drift_count >= 10
                else DriftSeverity.HIGH if self._alignment_drift_count >= 7
                else DriftSeverity.MEDIUM
            )
            return DriftAlert(
                drift_type=DriftType.PREFERENCE,
                severity=severity,
                metric="user_alignment",
                current_value=alignment_score,
                threshold=PREFERENCE_DRIFT_THRESHOLD,
                description=(
                    f"User alignment {alignment_score:.2f} < {PREFERENCE_DRIFT_THRESHOLD} "
                    f"for {self._alignment_drift_count} consecutive ticks"
                    + (f" (goal={goal_id})" if goal_id else "")
                ),
            )
        return None

    # ── Capability Drift ────────────────────────────────────────────────────

    def record_capability_usage(self, capability_id: str) -> None:
        """记录一次能力使用。"""
        self._capability_usage[capability_id] = self._capability_usage.get(capability_id, 0) + 1
        self._total_executions += 1

    def check_capability_drift(self) -> DriftAlert | None:
        """检查 Capability Drift — 单一 Agent 使用频率过高。"""
        if self._total_executions < 10:
            return None  # 样本不足

        for cap_id, count in self._capability_usage.items():
            ratio = count / self._total_executions
            if ratio > CAPABILITY_DRIFT_THRESHOLD:
                severity = DriftSeverity.HIGH if ratio > 0.9 else DriftSeverity.MEDIUM
                return DriftAlert(
                    drift_type=DriftType.CAPABILITY,
                    severity=severity,
                    metric="capability_usage_ratio",
                    current_value=ratio,
                    threshold=CAPABILITY_DRIFT_THRESHOLD,
                    description=(
                        f"Capability '{cap_id}' used {ratio:.0%} of time "
                        f"({count}/{self._total_executions}) — possible over-reliance"
                    ),
                )
        return None

    # ── Confidence Drift ────────────────────────────────────────────────────

    def check_confidence_drift(self, calibration_delta: float) -> DriftAlert | None:
        """检查 Confidence Drift — 预测持续偏离实际（过度自信或过度悲观）。"""
        self._calibration_history.append(calibration_delta)

        if abs(calibration_delta) > CONFIDENCE_DRIFT_ABS:
            self._confidence_drift_count += 1
        else:
            self._confidence_drift_count = max(0, self._confidence_drift_count - 1)

        if self._confidence_drift_count >= DRIFT_ALERT_CONTINUOUS:
            direction = "overconfident" if calibration_delta > 0 else "underconfident"
            return DriftAlert(
                drift_type=DriftType.CONFIDENCE,
                severity=DriftSeverity.MEDIUM,
                metric="calibration_delta",
                current_value=calibration_delta,
                threshold=CONFIDENCE_DRIFT_ABS,
                description=(
                    f"Prediction calibration consistently {direction}: "
                    f"|delta|={abs(calibration_delta):.3f} > {CONFIDENCE_DRIFT_ABS} "
                    f"for {self._confidence_drift_count} ticks"
                ),
            )
        return None

    # ── Consolidated check ──────────────────────────────────────────────────

    def check_all(
        self,
        *,
        alignment_score: float = 0.5,
        calibration_delta: float = 0.0,
        goal_id: str = "",
    ) -> list[DriftAlert]:
        """一次性检查所有漂移类型，返回所有活跃的 alert。

        注意：返回 list[DriftAlert]，绝不执行任何修正操作。
        """
        alerts: list[DriftAlert] = []

        gd = self.check_goal_drift(alignment_score, goal_id)
        if gd:
            alerts.append(gd)

        cd = self.check_capability_drift()
        if cd:
            alerts.append(cd)

        fd = self.check_confidence_drift(calibration_delta)
        if fd:
            alerts.append(fd)

        return alerts

    # ── Status ──────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """获取检测器状态（用于 CLI/API 查询）。"""
        avg_alignment = (
            sum(self._alignment_history) / len(self._alignment_history)
            if self._alignment_history else 0.0
        )
        avg_calibration = (
            sum(self._calibration_history) / len(self._calibration_history)
            if self._calibration_history else 0.0
        )
        return {
            "total_executions": self._total_executions,
            "avg_alignment": round(avg_alignment, 3),
            "avg_calibration_delta": round(avg_calibration, 3),
            "alignment_drift_count": self._alignment_drift_count,
            "confidence_drift_count": self._confidence_drift_count,
            "capability_usage": dict(self._capability_usage),
        }
