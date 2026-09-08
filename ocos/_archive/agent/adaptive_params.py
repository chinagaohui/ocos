# ARCHIVED（收敛裁决 P1，2026-09-08）— 本模块已冻结归档，非生产代码。
# 依据: docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md（FROZEN DECISION）
# 禁止从生产路径 import 本模块（违冻条款见来源文档第七节）。

"""Phase 37 §4: Adaptive Param Guard — 自适应参数防护层。

§4.3: 5 个允许的自适应参数
§4.4: 单步上限 0.1 + 日累计上限 0.2 (Mutation Budget)
§7.3: 唯一参数修改写入点

Usage:
    guard = AdaptiveParamGuard()
    guard.adjust("capability_reliability", +0.03)  # OK
    guard.adjust("constitution", +0.01)             # PermissionDeniedError
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ocos.contracts.feedback_abi import (
    ADAPTIVE_PARAM_KEYS,
    IMMUTABLE_PARAM_KEYS,
    MAX_SINGLE_STEP_DELTA,
    MAX_DAILY_MUTATION_BUDGET,
)
from ocos.logging import get_logger

logger = get_logger(__name__)


class PermissionDeniedError(PermissionError):
    """自适应参数权限拒绝。"""


@dataclass
class AdaptiveParams:
    """可变自适应参数容器。"""

    capability_reliability: dict[tuple[str, str], float] = field(default_factory=dict)
    execution_cost_estimate: dict[tuple[str, str], float] = field(default_factory=dict)
    attention_relevance_weight: float = 1.0
    retrieval_ranking: dict[str, float] = field(default_factory=dict)
    planning_confidence_threshold: float = 0.5

    # 日累计记录 (§4.4)
    _daily_deltas: dict[str, float] = field(default_factory=dict, repr=False)
    _last_reset_day: float = field(default_factory=time.time, repr=False)


class AdaptiveParamGuard:
    """自适应参数防护层 — 唯一写入点 (§7.3)。

    权限:
      ✅ ADAPTIVE_PARAM_KEYS: 可调整（幅度+日预算双限制）
      ❌ IMMUTABLE_PARAM_KEYS: 拒绝，抛出 PermissionDeniedError
    """

    def __init__(self):
        self._params = AdaptiveParams()

    @property
    def params(self) -> AdaptiveParams:
        return self._params

    def adjust(self, key: str, delta: float) -> bool:
        """调整自适应参数。

        Args:
            key: 参数键名
            delta: 变化量

        Returns:
            True: 已应用
            False: 被限制（幅度超限或日预算耗尽）

        Raises:
            PermissionDeniedError: 尝试修改不可变参数
        """
        # ── §4.2 禁止参数检查 ──
        if key in IMMUTABLE_PARAM_KEYS:
            raise PermissionDeniedError(f"Cannot adapt immutable param: {key}")

        if key not in ADAPTIVE_PARAM_KEYS:
            logger.warning("Unknown adaptive param: %s", key)
            return False

        # ── §4.4 单步上限 ──
        if abs(delta) > MAX_SINGLE_STEP_DELTA:
            logger.warning(
                "Single-step delta capped for %s: %.3f > %.3f",
                key, abs(delta), MAX_SINGLE_STEP_DELTA,
            )
            return False

        # ── §4.4 日累计预算 ──
        self._reset_daily_budget_if_new_day()
        daily = self._params._daily_deltas.get(key, 0.0)
        if abs(daily + delta) > MAX_DAILY_MUTATION_BUDGET:
            logger.warning(
                "Daily mutation budget exhausted for %s: %.3f + %.3f > %.3f",
                key, daily, delta, MAX_DAILY_MUTATION_BUDGET,
            )
            return False

        # ── 应用调整 ──
        self._apply(key, delta)
        self._params._daily_deltas[key] = daily + delta
        logger.debug("Adaptive param adjusted: %s by %.3f → %.3f",
                      key, delta, getattr(self._params, key, "N/A"))
        return True

    def _apply(self, key: str, delta: float) -> None:
        if key == "attention_relevance_weight":
            self._params.attention_relevance_weight = max(0.1, min(2.0,
                self._params.attention_relevance_weight + delta))
        elif key == "planning_confidence_threshold":
            self._params.planning_confidence_threshold = max(0.1, min(0.9,
                self._params.planning_confidence_threshold + delta))
        elif key == "capability_reliability":
            pass  # 由 CalibrationStore.apply 处理
        elif key == "execution_cost_estimate":
            pass  # 由 CalibrationStore.apply 处理
        elif key == "retrieval_ranking":
            pass  # 由 MemoryHub 处理

    def _reset_daily_budget_if_new_day(self) -> None:
        now = time.time()
        if now - self._params._last_reset_day > 86400:  # 24h
            self._params._daily_deltas.clear()
            self._params._last_reset_day = now
            logger.debug("Daily mutation budget reset")

    def get_adaptation_state(self) -> dict:
        """获取当前自适应状态快照（用于审计）。"""
        return {
            "attention_relevance_weight": self._params.attention_relevance_weight,
            "planning_confidence_threshold": self._params.planning_confidence_threshold,
            "daily_deltas": dict(self._params._daily_deltas),
            "capability_rel_count": len(self._params.capability_reliability),
        }
