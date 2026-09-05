"""Phase 37 §3: Calibration Store — 预测校准存储层。

扩展 CapabilityExperienceMemory 表结构，增加校准追踪字段。

§3.4: samples < CALIBRATION_MIN_SAMPLES 只记录不调整。
"""

from __future__ import annotations

from typing import Any

from ocos.contracts.feedback_abi import CALIBRATION_MIN_SAMPLES
from ocos.logging import get_logger

logger = get_logger(__name__)


class CalibrationStore:
    """预测校准追踪器 — 包装 CapabilityExperienceMemory。

    追踪每个 (capability, provider) 对的校准状态。

    Usage:
        store = CalibrationStore(experience_memory=cem)
        result = store.record_calibration(capability_id, provider_id, delta)
        if result.applied:
            # 更新 reliability
    """

    def __init__(self, *, experience_memory: Any = None):
        self._experience = experience_memory
        self._sample_counts: dict[tuple[str, str], int] = {}
        self._delta_accumulators: dict[tuple[str, str], float] = {}

    def record_calibration(
        self,
        capability_id: str,
        provider_id: str,
        calibration_delta: float,
    ) -> CalibrationResult:
        """记录一次校准事件。

        Args:
            capability_id: 能力 ID
            provider_id: Provider ID
            calibration_delta: 预测偏差（正值=乐观、负值=悲观）

        Returns:
            CalibrationResult (applied=True 表示已达到样本门槛并已应用)
        """
        key = (capability_id, provider_id)
        count = self._sample_counts.get(key, 0) + 1
        self._sample_counts[key] = count

        # 累计 delta
        if key not in self._delta_accumulators:
            self._delta_accumulators[key] = 0.0
        self._delta_accumulators[key] += calibration_delta

        if count < CALIBRATION_MIN_SAMPLES:
            return CalibrationResult(
                delta=calibration_delta,
                applied=False,
                reason="INSUFFICIENT_SAMPLES",
                samples=count,
                required_samples=CALIBRATION_MIN_SAMPLES,
            )

        # 计算应用后的 reliability_adjustment
        avg_delta = self._delta_accumulators[key] / count

        # S2.14 (白皮书 P2): CapabilityExperienceMemory 无 update_reliability
        # 方法（原调用 AttributeError 被吞 + 假报 applied=True）。现诚实
        # 降级：delta 只累计在本地校准表，applied=False 如实上报。
        applied = False
        reason = "CALIBRATED_LOCAL_ONLY（reliability 后端未接线）"

        return CalibrationResult(
            delta=calibration_delta,
            cumulative_delta=avg_delta,
            applied=applied,
            reason=reason,
            samples=count,
            required_samples=CALIBRATION_MIN_SAMPLES,
        )

    def get_status(self, capability_id: str, provider_id: str) -> dict[str, Any]:
        key = (capability_id, provider_id)
        return {
            "samples": self._sample_counts.get(key, 0),
            "required": CALIBRATION_MIN_SAMPLES,
            "ready": self._sample_counts.get(key, 0) >= CALIBRATION_MIN_SAMPLES,
            "cumulative_delta": self._delta_accumulators.get(key, 0.0),
        }


class CalibrationResult:
    """一次校准操作的结果。"""

    def __init__(
        self,
        delta: float,
        applied: bool,
        reason: str,
        samples: int = 0,
        required_samples: int = CALIBRATION_MIN_SAMPLES,
        cumulative_delta: float = 0.0,
    ):
        self.delta = delta
        self.applied = applied
        self.reason = reason
        self.samples = samples
        self.required_samples = required_samples
        self.cumulative_delta = cumulative_delta

    def __repr__(self) -> str:
        return (
            f"CalibrationResult(delta={self.delta:.3f}, applied={self.applied}, "
            f"reason={self.reason}, samples={self.samples}/{self.required_samples})"
        )
