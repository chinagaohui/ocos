"""Phase 52: PerceptionValidator — 验证 Observation 是否可进入世界模型。

PS52-04: Validation Before Belief。

核心逻辑:
    - 置信度检查: 低于阈值拒绝
    - 一致性检查: 与现有知识冲突则标记 CONFLICT
    - 来源检查: 不可靠传感器降低置信度
    - 频率检查: 重复观察降低价值

类似人脑: 眼睛看到的不等于大脑相信。
    视觉信号 → 初级视觉皮层 → 高级处理 → 意识 — 层层过滤。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
import time as _time

from ocos.perception.sensor_types import (
    Observation, SemanticFragment,
    ValidationResult, ValidationVerdict,
)


@dataclass
class PerceptionValidator:
    """感知验证器 — 决定 Observation 是否值得注意。

    验证维度:
        1. 置信度门控: confidence < min_confidence → REJECTED
        2. 去重: 最近 N 秒相同 observation 已出现 → REJECTED
        3. 来源信誉: 已知不可靠传感器降低置信度
        4. 知识冲突: (由 WorldValidator 处理，这里只标记)
    """

    min_confidence: float = 0.3
    dedup_window_seconds: float = 10.0

    # 来源信誉 (0.0-1.0)
    source_reputation: dict[str, float] = field(default_factory=dict)

    # 去重追踪: (source, content_hash) → timestamp
    _seen: dict[tuple[str, str], float] = field(default_factory=dict)

    # 统计: 来源 → (accepted, rejected)
    _stats: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))

    def validate(self, obs: Observation,
                 semantic: SemanticFragment | None = None) -> ValidationResult:
        """验证 Observation。

        PS52-04: 感知只是假设，需要验证才能进入世界模型。
        """
        content_hash = self._hash_content(obs.content)

        # 1. 去重检查
        key = (obs.source_sensor, content_hash)
        last_seen = self._seen.get(key)
        if last_seen and (_time.time() - last_seen) < self.dedup_window_seconds:
            self._record(obs.source_sensor, accepted=False)
            return ValidationResult(
                observation_id=obs.id,
                verdict=ValidationVerdict.REJECTED,
                reason="duplicate within dedup window",
            )
        self._seen[key] = _time.time()

        # 2. 来源信誉调整
        effective_confidence = obs.confidence
        if obs.source_sensor in self.source_reputation:
            rep = self.source_reputation[obs.source_sensor]
            effective_confidence *= rep

        # 3. 置信度门控
        if effective_confidence < self.min_confidence:
            self._record(obs.source_sensor, accepted=False)
            return ValidationResult(
                observation_id=obs.id,
                verdict=ValidationVerdict.REJECTED,
                reason=f"confidence {effective_confidence:.2f} < {self.min_confidence}",
                confidence_adjustment=effective_confidence - obs.confidence,
            )

        # 4. 低置信但可通过 → NEEDS_CONFIRMATION
        if effective_confidence < 0.6:
            self._record(obs.source_sensor, accepted=False)
            return ValidationResult(
                observation_id=obs.id,
                verdict=ValidationVerdict.NEEDS_CONFIRMATION,
                reason="low confidence, needs more evidence",
                confidence_adjustment=effective_confidence - obs.confidence,
            )

        self._record(obs.source_sensor, accepted=True)
        return ValidationResult(
            observation_id=obs.id,
            verdict=ValidationVerdict.ACCEPTED,
            reason="validation passed",
            confidence_adjustment=effective_confidence - obs.confidence,
        )

    def _hash_content(self, content: object) -> str:
        """生成内容哈希用于去重。"""
        if content is None:
            return "none"
        if isinstance(content, str):
            return content[:50]  # 前 50 字符作为指纹
        return str(hash(str(content))) if content is not None else "empty"

    def _record(self, source: str, accepted: bool) -> None:
        s = self._stats[source]
        if accepted:
            s[0] += 1
        else:
            s[1] += 1

    def set_source_reputation(self, source: str, reputation: float) -> None:
        """设置来源信誉。0.0=完全不可信, 1.0=完全可信。"""
        self.source_reputation[source] = max(0.0, min(1.0, reputation))

    def get_stats(self) -> dict:
        """获取验证统计。"""
        result = {}
        for source, (accepted, rejected) in self._stats.items():
            total = accepted + rejected
            result[source] = {
                "accepted": accepted,
                "rejected": rejected,
                "accept_rate": accepted / total if total > 0 else 0,
            }
        return result

    def get_state(self) -> dict:
        """导出状态。"""
        return {
            "source_reputation": dict(self.source_reputation),
            "stats": {k: {"accepted": v[0], "rejected": v[1]} for k, v in self._stats.items()},
        }


__all__ = ["PerceptionValidator"]
