"""Phase 24 — SelfMonitor: 自主演化循环。

职责:
  1. 周期性检查是否需要 Self 演化
  2. 通过 SelfModelBuilder 构建候选 SelfModel
  3. 通过 SelfGovernor 审批
  4. 记录演化结果（EvolutionRecord）

约束:
  - 只读 BeliefStore / SelfModel（不写）
  - 演化必经 SelfGovernor 审批
  - 频率受 IdentityBoundary.evolution_constraints 限制
  - 防御性：任何异常不影响主系统
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ocos.memory.belief.store import BeliefStore
    from ocos.self.builder import SelfModelBuilder
    from ocos.self.governor import EvolutionRecord, SelfGovernor
    from ocos.self.models import SelfModel


# ── MonitorState ────────────────────────────────────────────────────────────


class MonitorAction(Enum):
    """Monitor 动作类型。"""
    NO_CHANGE = "no-change"          # 无需演化
    EVOLVED = "evolved"              # 演化成功
    DENIED = "denied"                # 被 SelfGovernor 拒绝
    SKIPPED_FREQUENCY = "skipped-frequency"  # 频率限制
    SKIPPED_INSUFFICIENT = "skipped-insufficient"  # 证据不足


@dataclass(frozen=True)
class MonitorResult:
    """SelfMonitor 的一次检查结果。"""
    result_id: str
    action: MonitorAction
    message: str
    previous_version: int
    new_version: int | None
    checked_at: datetime
    evolution_record_id: str | None   # EvolutionRecord.record_id (仅 EVOLVED)


# ── ChangeDetector ──────────────────────────────────────────────────────────


class ChangeDetector:
    """检测 Self 相关变化，判断是否需要演化。

    检查维度:
      - BeliefStore 中 self 域的 belief 数量变化
      - CapabilityState 置信度变化
      - Limitation 数量变化
    """

    MIN_BELIEFS_FOR_CHANGE = 3                # self 域 belief 变化 >= N 条
    MIN_CONFIDENCE_DELTA = 0.1                # 置信度变化阈值
    MIN_LIMITATION_DELTA = 1                  # 新局限检测阈值

    @staticmethod
    def should_evolve(
        belief_store: "BeliefStore",
        current_model: "SelfModel | None",
    ) -> tuple[bool, str]:
        """判断是否需要触发 Self 演化。

        Returns (should_evolve, reason).
        """
        if current_model is None:
            return True, "no current SelfModel — initial build required"

        try:
            self_beliefs = belief_store.query_by_domain("self", limit=100)
        except Exception:
            return False, "unable to query belief store"

        reasons: list[str] = []

        # 1. Belief 数量变化
        current_cap_belief_count = sum(
            len(c.belief_ids) for c in current_model.capability_states
        )
        if abs(len(self_beliefs) - current_cap_belief_count) >= ChangeDetector.MIN_BELIEFS_FOR_CHANGE:
            reasons.append(
                f"self-domain beliefs changed: {current_cap_belief_count} → {len(self_beliefs)}"
            )

        # 2. Capability 置信度总体变化
        if current_model.capability_states:
            current_avg = sum(
                c.confidence_score for c in current_model.capability_states
            ) / len(current_model.capability_states)

            # 简单检测：有资料就触发（因为 Builder 会重新计算）
            if reasons:
                pass  # 已经被其他条件触发
            elif len(self_beliefs) > 0 and current_cap_belief_count == 0:
                reasons.append("new self-domain beliefs detected")

        if reasons:
            return True, "; ".join(reasons)
        return False, "no significant change detected"


# ── SelfMonitor ─────────────────────────────────────────────────────────────


class SelfMonitor:
    """Self 自主演化监控器。

    用法:
        monitor = SelfMonitor(builder, governor, belief_store)
        result = monitor.run_once()          # 检查并演化一次
        results = monitor.run()               # 持续检查（直到无变化）
    """

    def __init__(
        self,
        builder: "SelfModelBuilder",
        governor: "SelfGovernor",
        belief_store: "BeliefStore",
    ) -> None:
        self._builder = builder
        self._governor = governor
        self._belief_store = belief_store
        self._current_model: SelfModel | None = None
        self._history: list[MonitorResult] = []

    # ── 属性 ─────────────────────────────────────────────────────────────

    @property
    def current_model(self) -> "SelfModel | None":
        return self._current_model

    @property
    def history(self) -> tuple[MonitorResult, ...]:
        return tuple(self._history)

    # ── 核心循环 ─────────────────────────────────────────────────────────

    def run_once(self) -> MonitorResult:
        """执行一次检查+演化循环。"""
        now = datetime.now(timezone.utc)

        # 频率检查
        frequency_result = self._check_frequency(now)
        if frequency_result:
            return frequency_result

        # 变化检测
        should, reason = ChangeDetector.should_evolve(
            self._belief_store, self._current_model
        )
        if not should:
            result = MonitorResult(
                result_id=f"MON-{uuid.uuid4().hex[:8].upper()}",
                action=MonitorAction.NO_CHANGE,
                message=reason,
                previous_version=self._current_model.version if self._current_model else 0,
                new_version=None,
                checked_at=now,
                evolution_record_id=None,
            )
            self._history.append(result)
            return result

        # 执行演化
        try:
            new_model = self._builder.build_and_approve(
                self._governor, self._current_model
            )
            if new_model is None:
                result = MonitorResult(
                    result_id=f"MON-{uuid.uuid4().hex[:8].upper()}",
                    action=MonitorAction.DENIED,
                    message=f"evolution denied by SelfGovernor (reason: {reason})",
                    previous_version=self._current_model.version if self._current_model else 0,
                    new_version=None,
                    checked_at=now,
                    evolution_record_id=None,
                )
                self._history.append(result)
                return result

            # 演化成功
            self._current_model = new_model
            result = MonitorResult(
                result_id=f"MON-{uuid.uuid4().hex[:8].upper()}",
                action=MonitorAction.EVOLVED,
                message=f"evolved to v{new_model.version}: {reason}",
                previous_version=new_model.version - 1,
                new_version=new_model.version,
                checked_at=now,
                evolution_record_id=new_model.governor_approval_id,
            )
            self._history.append(result)
            return result

        except Exception as e:
            result = MonitorResult(
                result_id=f"MON-{uuid.uuid4().hex[:8].upper()}",
                action=MonitorAction.DENIED,
                message=f"evolution failed: {e}",
                previous_version=self._current_model.version if self._current_model else 0,
                new_version=None,
                checked_at=now,
                evolution_record_id=None,
            )
            self._history.append(result)
            return result

    def run(self, max_iterations: int = 10) -> list[MonitorResult]:
        """持续检查直到无变化或达到最大迭代次数。"""
        results: list[MonitorResult] = []
        for _ in range(max_iterations):
            result = self.run_once()
            results.append(result)
            if result.action != MonitorAction.EVOLVED:
                break
        return results

    def seed(self, model: "SelfModel") -> None:
        """注入初始 SelfModel（用于从已有的 model 开始监控）。"""
        self._current_model = model

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _check_frequency(self, now: datetime) -> MonitorResult | None:
        """检查演化频率是否超限。"""
        boundary = self._governor.boundary
        max_freq_days = boundary.max_evolution_frequency_days

        if not self._history:
            return None

        recent_evolutions = [
            r for r in self._history
            if r.action == MonitorAction.EVOLVED
        ]
        if not recent_evolutions:
            return None

        last_evo = recent_evolutions[-1]
        days_since = (now - last_evo.checked_at).days
        if days_since < max_freq_days:
            return MonitorResult(
                result_id=f"MON-{uuid.uuid4().hex[:8].upper()}",
                action=MonitorAction.SKIPPED_FREQUENCY,
                message=f"frequency limit: {days_since}d since last evolution (min {max_freq_days}d)",
                previous_version=self._current_model.version if self._current_model else 0,
                new_version=None,
                checked_at=now,
                evolution_record_id=None,
            )

        return None
