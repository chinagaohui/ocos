"""Phase 49: IdentityContinuity — 身份连续性验证。

定期检查当前 OCOS 状态是否与长期认知轨迹一致。

检测 (不阻止):
    - 风险偏好突变
    - 决策模式剧烈变化
    - 交互风格异常转换
    - 核心特征漂移

CC49-02: Identity Continuity ≠ Freeze
    检测漂移，报告异常，但 NOT 阻止 Phase 47 演化。
    快速变化可能合法——只是提醒"这在你的历史轨迹上不常见"。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_continuity.continuity_types import (
    IdentitySnapshot,
)


@dataclass
class ContinuityCheck:
    """连续性检查结果。"""
    is_consistent: bool = True
    drift_detected: bool = False
    anomalies: list[str] = field(default_factory=list)
    severity: float = 0.0          # 0 = 完全一致, 1 = 严重偏离
    recommendation: str = ""


@dataclass
class IdentityContinuityEngine:
    """身份连续性引擎。

    定期冻结快照 + 对比当前状态。
    不阻止演化——只是检测和报告 (CC49-02)。
    """

    snapshots: list[IdentitySnapshot] = field(default_factory=list)
    checks: list[ContinuityCheck] = field(default_factory=list)

    # 检测阈值
    RISK_SHIFT_THRESHOLD = 0.5   # 风险偏好变化 >0.5 触发
    PATTERN_SHIFT_THRESHOLD = 0.4

    def create_snapshot(
        self, tick_id: int, label: str,
        risk_tolerance: str,
        decision_style: str,
        key_memories: list[str] | None = None,
        wisdom_count: int = 0,
        evolution_count: int = 0,
    ) -> IdentitySnapshot:
        """创建当前身份快照。"""
        snapshot = IdentitySnapshot(
            snapshot_id=f"snap:{tick_id}",
            tick_id=tick_id,
            label=label,
            risk_tolerance=risk_tolerance,
            decision_style=decision_style,
            key_memories=key_memories or [],
            wisdom_count=wisdom_count,
            evolution_count=evolution_count,
        )
        self.snapshots.append(snapshot)
        if len(self.snapshots) > 100:
            self.snapshots = self.snapshots[-100:]
        return snapshot

    def check_continuity(
        self, current: IdentitySnapshot,
    ) -> ContinuityCheck:
        """检查当前快照与历史轨迹的一致性。"""
        anomalies: list[str] = []
        severity = 0.0

        if not self.snapshots:
            self.checks.append(ContinuityCheck())
            return ContinuityCheck()

        # 对比最近一次快照
        last = self.snapshots[-2] if len(self.snapshots) > 1 else self.snapshots[-1]

        # 检查1: 风险偏好突变
        if (
            last.risk_tolerance != current.risk_tolerance
            and last.risk_tolerance
            and current.risk_tolerance
        ):
            anomalies.append(
                f"Risk tolerance shifted: {last.risk_tolerance} → {current.risk_tolerance}"
            )
            severity += 0.3

        # 检查2: 决策风格改变
        if (
            last.decision_style != current.decision_style
            and last.decision_style
            and current.decision_style
        ):
            anomalies.append(
                f"Decision style changed: {last.decision_style} → {current.decision_style}"
            )
            severity += 0.2

        # 检查3: 智慧/演化倒退
        if current.wisdom_count < last.wisdom_count:
            anomalies.append("Wisdom count decreased — possible memory issue")
            severity += 0.3

        # 检查4: 核心记忆大量替换
        old_keys = set(last.key_memories)
        new_keys = set(current.key_memories)
        overlap = len(old_keys & new_keys) if old_keys else 1
        total = max(len(old_keys), 1)
        if old_keys and overlap / total < 0.5:
            anomalies.append("Core memories largely replaced")
            severity += 0.4

        is_consistent = len(anomalies) == 0
        result = ContinuityCheck(
            is_consistent=is_consistent,
            drift_detected=len(anomalies) > 0,
            anomalies=anomalies,
            severity=min(1.0, severity),
            recommendation=(
                "Review evolution history and confirm changes are intentional"
                if anomalies else "Consistent with trajectory"
            ),
        )
        self.checks.append(result)
        return result

    @property
    def latest_check(self) -> ContinuityCheck | None:
        return self.checks[-1] if self.checks else None

    @property
    def consistent_rate(self) -> float:
        """一致性比例——过去的检查中有多少是一致的。"""
        if not self.checks:
            return 1.0
        consistent = sum(1 for c in self.checks if c.is_consistent)
        return consistent / len(self.checks)


__all__ = ["ContinuityCheck", "IdentityContinuityEngine"]
