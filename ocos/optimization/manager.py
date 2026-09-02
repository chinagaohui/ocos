"""Phase AF: SelfOptimizationManager — 自我优化管理器。

整合 PerformanceManager + ImprovementDetector + 反思洞察，
提供统一的自我优化接口：
- 性能瓶颈检测
- 优化策略应用
- 优化效果验证
- 自动调参

架构原则：
- AF-OPT-01: 优化必须可回滚
- AF-OPT-02: 优化效果必须可测量
- AF-OPT-03: 优化决策基于证据而非猜测
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

from ocos.logging import get_logger

logger = get_logger(__name__)


class OptimizationType(Enum):
    """优化类型。"""
    CACHE = auto()           # 缓存优化
    BATCH = auto()           # 批处理优化
    THREAD = auto()          # 线程池优化
    MEMORY = auto()          # 内存优化
    ALGORITHM = auto()       # 算法优化


class OptimizationStatus(Enum):
    """优化状态。"""
    PENDING = "pending"
    APPLIED = "applied"
    VALIDATED = "validated"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class OptimizationProposal:
    """优化提案。"""
    proposal_id: str
    opt_type: OptimizationType
    description: str
    expected_improvement: float
    risk_level: str  # "low" | "medium" | "high"
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class OptimizationResult:
    """优化结果。"""
    result_id: str
    proposal_id: str
    status: OptimizationStatus
    actual_improvement: float = 0.0
    before_metrics: dict[str, float] = field(default_factory=dict)
    after_metrics: dict[str, float] = field(default_factory=dict)
    applied_at: float = 0.0
    validated_at: float = 0.0

    def __post_init__(self):
        if self.applied_at == 0.0:
            self.applied_at = time.time()


class SelfOptimizationManager:
    """自我优化管理器。

    统一管理层：
    1. 性能监控与瓶颈检测
    2. 优化提案生成
    3. 优化策略应用
    4. 优化效果验证
    5. 自动调参
    """

    def __init__(
        self,
        max_proposals: int = 100,
        max_results: int = 500,
        min_improvement_threshold: float = 0.05,
        validation_window: float = 60.0,
    ):
        self._max_proposals = max_proposals
        self._max_results = max_results
        self._min_improvement_threshold = min_improvement_threshold
        self._validation_window = validation_window

        # 优化提案
        self._proposals: dict[str, OptimizationProposal] = {}
        self._proposal_lock = threading.RLock()

        # 优化结果
        self._results: dict[str, OptimizationResult] = {}
        self._result_lock = threading.RLock()

        # 性能基线
        self._baseline: dict[str, float] = {}
        self._baseline_lock = threading.RLock()

        # 统计
        self._stats = {
            "proposals_generated": 0,
            "optimizations_applied": 0,
            "optimizations_validated": 0,
            "optimizations_failed": 0,
            "total_improvement": 0.0,
        }

    # ── 性能基线 ────────────────────────────────────────────────

    def set_baseline(self, metric_name: str, value: float) -> None:
        """设置性能基线。"""
        with self._baseline_lock:
            self._baseline[metric_name] = value
            logger.debug("Baseline set: %s = %.4f", metric_name, value)

    def get_baseline(self, metric_name: str) -> float | None:
        """获取性能基线。"""
        with self._baseline_lock:
            return self._baseline.get(metric_name)

    def get_all_baselines(self) -> dict[str, float]:
        """获取所有基线。"""
        with self._baseline_lock:
            return dict(self._baseline)

    def update_baseline(self, metric_name: str, current_value: float) -> float:
        """更新基线并返回改进率。"""
        with self._baseline_lock:
            old_value = self._baseline.get(metric_name)
            if old_value is not None and old_value > 0:
                improvement = (old_value - current_value) / old_value
                self._baseline[metric_name] = current_value
                return improvement
            self._baseline[metric_name] = current_value
            return 0.0

    # ── 优化提案 ────────────────────────────────────────────────

    def propose_optimization(
        self,
        opt_type: OptimizationType,
        description: str,
        expected_improvement: float,
        risk_level: str = "low",
        parameters: dict[str, Any] | None = None,
    ) -> OptimizationProposal | None:
        """生成优化提案。"""
        with self._proposal_lock:
            if len(self._proposals) >= self._max_proposals:
                logger.warning("Max proposals reached (%d)", self._max_proposals)
                return None

            proposal_id = f"opt:{uuid.uuid4().hex[:8]}"
            proposal = OptimizationProposal(
                proposal_id=proposal_id,
                opt_type=opt_type,
                description=description,
                expected_improvement=expected_improvement,
                risk_level=risk_level,
                parameters=parameters or {},
            )
            self._proposals[proposal_id] = proposal
            self._stats["proposals_generated"] += 1
            logger.info("Optimization proposal generated: %s (%s)", proposal_id, opt_type.name)
            return proposal

    def get_proposal(self, proposal_id: str) -> OptimizationProposal | None:
        """获取优化提案。"""
        with self._proposal_lock:
            return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        opt_type: OptimizationType | None = None,
        limit: int = 50,
    ) -> list[OptimizationProposal]:
        """列出优化提案。"""
        with self._proposal_lock:
            proposals = list(self._proposals.values())
            if opt_type:
                proposals = [p for p in proposals if p.opt_type == opt_type]
            return proposals[-limit:]

    # ── 优化应用 ────────────────────────────────────────────────

    def apply_optimization(
        self,
        proposal_id: str,
        before_metrics: dict[str, float],
    ) -> OptimizationResult | None:
        """应用优化方案。"""
        with self._proposal_lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return None

        result_id = f"res:{uuid.uuid4().hex[:8]}"
        result = OptimizationResult(
            result_id=result_id,
            proposal_id=proposal_id,
            status=OptimizationStatus.APPLIED,
            before_metrics=before_metrics,
        )

        with self._result_lock:
            self._results[result_id] = result
            self._stats["optimizations_applied"] += 1

        logger.info("Optimization applied: %s", result_id)
        return result

    def validate_optimization(
        self,
        result_id: str,
        after_metrics: dict[str, float],
    ) -> bool:
        """验证优化效果。"""
        with self._result_lock:
            result = self._results.get(result_id)
            if not result or result.status != OptimizationStatus.APPLIED:
                return False

            # 计算实际改进
            improvements = []
            for metric, new_value in after_metrics.items():
                old_value = result.before_metrics.get(metric)
                if old_value and old_value > 0:
                    improvement = (old_value - new_value) / old_value
                    improvements.append(improvement)

            if improvements:
                avg_improvement = sum(improvements) / len(improvements)
                result.actual_improvement = avg_improvement

                # 检查是否达到最小阈值
                if avg_improvement >= self._min_improvement_threshold:
                    result.status = OptimizationStatus.VALIDATED
                    self._stats["optimizations_validated"] += 1
                    self._stats["total_improvement"] += avg_improvement
                    logger.info("Optimization validated: %s (improvement=%.2f%%)",
                               result_id, avg_improvement * 100)
                else:
                    result.status = OptimizationStatus.FAILED
                    self._stats["optimizations_failed"] += 1
                    logger.warning("Optimization failed validation: %s (improvement=%.2f%%)",
                                  result_id, avg_improvement * 100)
            else:
                result.status = OptimizationStatus.FAILED
                self._stats["optimizations_failed"] += 1

            result.validated_at = time.time()
            return result.status == OptimizationStatus.VALIDATED

    def rollback_optimization(self, result_id: str) -> bool:
        """回滚优化。"""
        with self._result_lock:
            result = self._results.get(result_id)
            if not result:
                return False

            result.status = OptimizationStatus.ROLLED_BACK
            logger.info("Optimization rolled back: %s", result_id)
            return True

    # ── 自动优化 ────────────────────────────────────────────────

    def auto_optimize(
        self,
        current_metrics: dict[str, float],
        optimization_fn: Callable[[dict[str, Any]], dict[str, float]],
    ) -> OptimizationResult | None:
        """自动优化循环。"""
        # 生成提案
        proposal = self.propose_optimization(
            opt_type=OptimizationType.ALGORITHM,
            description="Auto-optimization based on current metrics",
            expected_improvement=0.1,
            risk_level="medium",
            parameters={"current_metrics": current_metrics},
        )
        if not proposal:
            return None

        # 应用优化
        result = self.apply_optimization(proposal.proposal_id, current_metrics)
        if not result:
            return None

        # 执行优化函数
        try:
            new_metrics = optimization_fn(proposal.parameters)
        except Exception as e:
            logger.error("Auto-optimization failed: %s", e)
            result.status = OptimizationStatus.FAILED
            self._stats["optimizations_failed"] += 1
            return result

        # 验证效果
        self.validate_optimization(result.result_id, new_metrics)
        return result

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._proposal_lock:
            proposal_count = len(self._proposals)
        with self._result_lock:
            result_count = len(self._results)
            validated_count = sum(
                1 for r in self._results.values()
                if r.status == OptimizationStatus.VALIDATED
            )

        return {
            **self._stats,
            "proposal_count": proposal_count,
            "result_count": result_count,
            "validated_count": validated_count,
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "proposals_generated": 0,
            "optimizations_applied": 0,
            "optimizations_validated": 0,
            "optimizations_failed": 0,
            "total_improvement": 0.0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._proposal_lock:
            self._proposals.clear()
        with self._result_lock:
            self._results.clear()
        with self._baseline_lock:
            self._baseline.clear()
        logger.info("SelfOptimizationManager closed")


__all__ = [
    "SelfOptimizationManager",
    "OptimizationProposal",
    "OptimizationResult",
    "OptimizationType",
    "OptimizationStatus",
]
