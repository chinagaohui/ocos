"""Phase AF: SelfOptimizationManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 性能基线管理
3. 优化提案
4. 优化应用与验证
5. 回滚机制
6. 自动优化
7. 统计信息
8. 边界约束
9. 端到端流程
10. 错误处理
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.optimization.manager import (
    SelfOptimizationManager,
    OptimizationProposal,
    OptimizationResult,
    OptimizationType,
    OptimizationStatus,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = SelfOptimizationManager()

        assert mgr.list_proposals() == []
        assert mgr.get_all_baselines() == {}

        stats = mgr.get_stats()
        assert stats["proposals_generated"] == 0
        assert stats["optimizations_applied"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = SelfOptimizationManager(
            max_proposals=20,
            max_results=100,
            min_improvement_threshold=0.1,
            validation_window=120.0,
        )

        assert mgr._max_proposals == 20
        assert mgr._min_improvement_threshold == 0.1

    def test_context_manager(self):
        """上下文管理器应正确关闭。"""
        with SelfOptimizationManager() as mgr:
            mgr.set_baseline("latency", 100.0)
            assert mgr.get_baseline("latency") == 100.0


# =========================================================================
# 2. 性能基线管理
# =========================================================================

class TestBaselineManagement:
    """性能基线管理测试。"""

    def test_set_baseline(self):
        """设置性能基线。"""
        mgr = SelfOptimizationManager()
        mgr.set_baseline("latency", 100.0)
        assert mgr.get_baseline("latency") == 100.0

    def test_update_baseline_with_improvement(self):
        """更新基线并计算改进。"""
        mgr = SelfOptimizationManager()
        mgr.set_baseline("latency", 100.0)

        improvement = mgr.update_baseline("latency", 80.0)
        assert improvement == 0.2  # (100-80)/100

    def test_update_baseline_with_no_baseline(self):
        """无基线时更新。"""
        mgr = SelfOptimizationManager()
        improvement = mgr.update_baseline("latency", 80.0)
        assert improvement == 0.0

    def test_get_all_baselines(self):
        """获取所有基线。"""
        mgr = SelfOptimizationManager()
        mgr.set_baseline("latency", 100.0)
        mgr.set_baseline("memory", 50.0)

        baselines = mgr.get_all_baselines()
        assert baselines["latency"] == 100.0
        assert baselines["memory"] == 50.0


# =========================================================================
# 3. 优化提案
# =========================================================================

class TestOptimizationProposal:
    """优化提案测试。"""

    def test_propose_optimization(self):
        """生成优化提案。"""
        mgr = SelfOptimizationManager()

        proposal = mgr.propose_optimization(
            opt_type=OptimizationType.CACHE,
            description="Increase cache size",
            expected_improvement=0.15,
            risk_level="low",
            parameters={"cache_size": 2000},
        )

        assert proposal is not None
        assert proposal.opt_type == OptimizationType.CACHE
        assert proposal.expected_improvement == 0.15
        assert proposal.parameters["cache_size"] == 2000

    def test_get_proposal(self):
        """获取优化提案。"""
        mgr = SelfOptimizationManager()
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)

        retrieved = mgr.get_proposal(proposal.proposal_id)
        assert retrieved is proposal

    def test_list_proposals_by_type(self):
        """按类型列出提案。"""
        mgr = SelfOptimizationManager()

        mgr.propose_optimization(OptimizationType.CACHE, "cache1", 0.1)
        mgr.propose_optimization(OptimizationType.BATCH, "batch1", 0.2)
        mgr.propose_optimization(OptimizationType.CACHE, "cache2", 0.15)

        cache_proposals = mgr.list_proposals(opt_type=OptimizationType.CACHE)
        assert len(cache_proposals) == 2
        assert all(p.opt_type == OptimizationType.CACHE for p in cache_proposals)


# =========================================================================
# 4. 优化应用与验证
# =========================================================================

class TestOptimizationApplication:
    """优化应用与验证测试。"""

    def test_apply_optimization(self):
        """应用优化方案。"""
        mgr = SelfOptimizationManager()
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)

        result = mgr.apply_optimization(
            proposal.proposal_id,
            before_metrics={"latency": 100.0, "memory": 50.0},
        )

        assert result is not None
        assert result.status == OptimizationStatus.APPLIED
        assert result.before_metrics["latency"] == 100.0

    def test_validate_successful_optimization(self):
        """验证成功的优化。"""
        mgr = SelfOptimizationManager()
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)
        result = mgr.apply_optimization(proposal.proposal_id, {"latency": 100.0})

        # 优化后延迟降低到 80
        validated = mgr.validate_optimization(result.result_id, {"latency": 80.0})

        assert validated is True
        assert result.status == OptimizationStatus.VALIDATED
        assert result.actual_improvement == 0.2

    def test_validate_failed_optimization(self):
        """验证失败的优化。"""
        mgr = SelfOptimizationManager(min_improvement_threshold=0.3)
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)
        result = mgr.apply_optimization(proposal.proposal_id, {"latency": 100.0})

        # 只改进了 10%，低于阈值 30%
        validated = mgr.validate_optimization(result.result_id, {"latency": 90.0})

        assert validated is False
        assert result.status == OptimizationStatus.FAILED

    def test_rollback_optimization(self):
        """回滚优化。"""
        mgr = SelfOptimizationManager()
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)
        result = mgr.apply_optimization(proposal.proposal_id, {"latency": 100.0})

        rolled_back = mgr.rollback_optimization(result.result_id)
        assert rolled_back is True
        assert result.status == OptimizationStatus.ROLLED_BACK


# =========================================================================
# 5. 自动优化
# =========================================================================

class TestAutoOptimization:
    """自动优化测试。"""

    def test_auto_optimize_success(self):
        """自动优化成功。"""
        mgr = SelfOptimizationManager()

        def optimization_fn(params):
            return {"latency": 80.0}

        result = mgr.auto_optimize({"latency": 100.0}, optimization_fn)

        assert result is not None
        assert result.status == OptimizationStatus.VALIDATED

    def test_auto_optimize_failure(self):
        """自动优化失败。"""
        mgr = SelfOptimizationManager(min_improvement_threshold=0.5)

        def optimization_fn(params):
            return {"latency": 90.0}  # 只改进 10%，低于 50% 阈值

        result = mgr.auto_optimize({"latency": 100.0}, optimization_fn)

        assert result is not None
        assert result.status == OptimizationStatus.FAILED


# =========================================================================
# 6. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = SelfOptimizationManager()
        stats = mgr.get_stats()

        assert "proposals_generated" in stats
        assert "optimizations_applied" in stats
        assert "proposal_count" in stats

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = SelfOptimizationManager()

        # 执行一些操作
        proposal = mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)
        result = mgr.apply_optimization(proposal.proposal_id, {"latency": 100.0})
        mgr.validate_optimization(result.result_id, {"latency": 80.0})

        stats = mgr.get_stats()
        assert stats["proposals_generated"] == 1
        assert stats["optimizations_applied"] == 1
        assert stats["optimizations_validated"] == 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = SelfOptimizationManager()
        mgr.propose_optimization(OptimizationType.CACHE, "test", 0.1)
        mgr.reset_stats()

        stats = mgr.get_stats()
        assert stats["proposals_generated"] == 0


# =========================================================================
# 7. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_proposals_limit(self):
        """提案数量上限约束。"""
        mgr = SelfOptimizationManager(max_proposals=2)

        mgr.propose_optimization(OptimizationType.CACHE, "test1", 0.1)
        mgr.propose_optimization(OptimizationType.CACHE, "test2", 0.1)

        result = mgr.propose_optimization(OptimizationType.CACHE, "test3", 0.1)
        assert result is None
        assert len(mgr.list_proposals()) == 2


# =========================================================================
# 8. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_optimization_workflow(self):
        """完整优化工作流。"""
        mgr = SelfOptimizationManager()

        # 1. 设置基线
        mgr.set_baseline("latency", 100.0)
        mgr.set_baseline("memory", 50.0)

        # 2. 生成优化提案
        proposal = mgr.propose_optimization(
            opt_type=OptimizationType.CACHE,
            description="Increase cache size by 50%",
            expected_improvement=0.2,
            parameters={"cache_size": 1500},
        )

        # 3. 应用优化
        result = mgr.apply_optimization(
            proposal.proposal_id,
            before_metrics={"latency": 100.0, "memory": 50.0},
        )

        # 4. 验证效果
        validated = mgr.validate_optimization(
            result.result_id,
            after_metrics={"latency": 80.0, "memory": 40.0},
        )

        assert validated is True
        assert result.status == OptimizationStatus.VALIDATED
        assert result.actual_improvement > 0

        # 5. 更新基线
        mgr.update_baseline("latency", 80.0)
        mgr.update_baseline("memory", 40.0)

        # 6. 获取统计
        stats = mgr.get_stats()
        assert stats["optimizations_validated"] == 1
        assert stats["total_improvement"] > 0


# =========================================================================
# 9. 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_apply_nonexistent_proposal(self):
        """应用不存在的提案。"""
        mgr = SelfOptimizationManager()
        result = mgr.apply_optimization("nonexistent", {"latency": 100.0})
        assert result is None

    def test_validate_nonexistent_result(self):
        """验证不存在的结果。"""
        mgr = SelfOptimizationManager()
        validated = mgr.validate_optimization("nonexistent", {"latency": 80.0})
        assert validated is False

    def test_rollback_nonexistent_result(self):
        """回滚不存在的结果。"""
        mgr = SelfOptimizationManager()
        rolled_back = mgr.rollback_optimization("nonexistent")
        assert rolled_back is False

    def test_get_nonexistent_proposal(self):
        """获取不存在的提案。"""
        mgr = SelfOptimizationManager()
        result = mgr.get_proposal("nonexistent")
        assert result is None
