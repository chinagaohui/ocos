"""Phase AE: SelfReflectionManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 反思执行
3. 智慧管理
4. 身份连续性检查
5. 批量反思
6. 统计信息
7. 边界约束
8. 回调测试
9. 端到端流程
10. 错误处理
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.reflection.manager import (
    SelfReflectionManager,
    ReflectionTrace,
    WisdomItem,
    IdentitySnapshot,
    ReflectionType,
    ReflectionDepth,
    InsightType,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = SelfReflectionManager()

        assert mgr.list_reflections() == []
        assert mgr.list_wisdom() == []
        assert mgr.get_latest_snapshot() is None

        stats = mgr.get_stats()
        assert stats["reflection_count"] == 0
        assert stats["wisdom_count"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = SelfReflectionManager(
            max_reflections=50,
            max_wisdom_items=20,
            max_identity_snapshots=30,
            min_wisdom_confidence=0.8,
        )

        assert mgr._max_reflections == 50
        assert mgr._max_wisdom_items == 20
        assert mgr._min_wisdom_confidence == 0.8

    def test_context_manager(self):
        """上下文管理器应正确关闭。"""
        with SelfReflectionManager() as mgr:
            mgr.start_reflection(ReflectionType.BEHAVIOR, "test")
            assert len(mgr.list_reflections()) == 1

        # 关闭后应为空
        assert len(mgr.list_reflections()) == 0


# =========================================================================
# 2. 反思执行
# =========================================================================

class TestReflectionExecution:
    """反思执行测试。"""

    def test_start_reflection(self):
        """开始反思。"""
        mgr = SelfReflectionManager()

        trace = mgr.start_reflection(
            ReflectionType.RESULT,
            "subject-1",
            depth=ReflectionDepth.ANALYTICAL,
        )

        assert trace is not None
        assert trace.reflection_type == ReflectionType.RESULT
        assert trace.subject_id == "subject-1"
        assert trace.depth == ReflectionDepth.ANALYTICAL

    def test_add_insight(self):
        """添加反思洞察。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.BEHAVIOR, "test")

        result = mgr.add_insight(
            trace.trace_id,
            InsightType.SUCCESS_FACTOR,
            "Good decision making",
            confidence=0.85,
        )

        assert result is True
        assert len(trace.insights) == 1
        assert trace.insights[0]["type"] == "success_factor"

    def test_complete_reflection(self):
        """完成反思。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.RESULT, "test")

        result = mgr.complete_reflection(trace.trace_id)
        assert result is True
        assert trace.completed_at > 0
        assert trace.duration > 0

    def test_get_reflection(self):
        """获取反思轨迹。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.IDENTITY, "test")

        retrieved = mgr.get_reflection(trace.trace_id)
        assert retrieved is trace

    def test_list_reflections_by_type(self):
        """按类型列出反思。"""
        mgr = SelfReflectionManager()

        mgr.start_reflection(ReflectionType.BEHAVIOR, "test1")
        mgr.start_reflection(ReflectionType.RESULT, "test2")
        mgr.start_reflection(ReflectionType.BEHAVIOR, "test3")

        behavior_refs = mgr.list_reflections(reflection_type=ReflectionType.BEHAVIOR)
        assert len(behavior_refs) == 2
        assert all(t.reflection_type == ReflectionType.BEHAVIOR for t in behavior_refs)


# =========================================================================
# 3. 智慧管理
# =========================================================================

class TestWisdomManagement:
    """智慧管理测试。"""

    def test_propose_wisdom(self):
        """提出智慧候选。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")

        wisdom = mgr.propose_wisdom(
            trace.trace_id,
            "Success comes from consistency",
            confidence=0.75,
        )

        assert wisdom is not None
        assert wisdom.content == "Success comes from consistency"
        assert wisdom.confidence == 0.75
        assert wisdom.verified is False

    def test_verify_wisdom(self):
        """验证智慧候选。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")
        wisdom = mgr.propose_wisdom(trace.trace_id, "Test wisdom")

        result = mgr.verify_wisdom(wisdom.wisdom_id, True)
        assert result is True
        assert wisdom.verified is True

    def test_get_wisdom(self):
        """获取智慧条目。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")
        wisdom = mgr.propose_wisdom(trace.trace_id, "Test")

        retrieved = mgr.get_wisdom(wisdom.wisdom_id)
        assert retrieved is wisdom

    def test_list_wisdom_verified_only(self):
        """列出已验证智慧。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")

        w1 = mgr.propose_wisdom(trace.trace_id, "A", confidence=0.8)
        w2 = mgr.propose_wisdom(trace.trace_id, "B", confidence=0.6)
        mgr.verify_wisdom(w1.wisdom_id, True)
        mgr.verify_wisdom(w2.wisdom_id, False)

        verified = mgr.list_wisdom(verified_only=True)
        assert len(verified) == 1
        assert verified[0].content == "A"

    def test_increment_wisdom_usage(self):
        """增加智慧使用次数。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")
        wisdom = mgr.propose_wisdom(trace.trace_id, "Test")

        result = mgr.increment_wisdom_usage(wisdom.wisdom_id)
        assert result is True
        assert wisdom.usage_count == 1


# =========================================================================
# 4. 身份连续性检查
# =========================================================================

class TestIdentityContinuity:
    """身份连续性检查测试。"""

    def test_create_identity_snapshot(self):
        """创建身份快照。"""
        mgr = SelfReflectionManager()

        snapshot = mgr.create_identity_snapshot(
            {"identity": "test", "version": 1},
            continuity_score=0.95,
        )

        assert snapshot is not None
        assert snapshot.continuity_score == 0.95

    def test_check_identity_continuity_no_history(self):
        """无历史时检查连续性。"""
        mgr = SelfReflectionManager()
        result = mgr.check_identity_continuity({"test": "state"})

        assert result["continuity_score"] == 1.0
        assert result["drift_detected"] is False
        assert result["recommendation"] == "no_history"

    def test_check_identity_continuity_with_history(self):
        """有历史时检查连续性。"""
        mgr = SelfReflectionManager()

        # 创建几个快照
        for i in range(5):
            mgr.create_identity_snapshot({"state": i}, continuity_score=0.9)

        result = mgr.check_identity_continuity({"state": 6})
        assert result["continuity_score"] == 0.9
        assert result["drift_detected"] is False

    def test_drift_detection(self):
        """检测身份漂移。"""
        mgr = SelfReflectionManager()

        # 创建低连续性的快照
        for i in range(5):
            mgr.create_identity_snapshot({"state": i}, continuity_score=0.5)

        result = mgr.check_identity_continuity({"state": 6})
        assert result["drift_detected"] is True
        assert result["recommendation"] == "investigate"

    def test_get_latest_snapshot(self):
        """获取最新快照。"""
        mgr = SelfReflectionManager()

        s1 = mgr.create_identity_snapshot({"v": 1})
        s2 = mgr.create_identity_snapshot({"v": 2})

        latest = mgr.get_latest_snapshot()
        assert latest is s2


# =========================================================================
# 5. 批量反思
# =========================================================================

class TestBatchReflection:
    """批量反思测试。"""

    def test_batch_reflect_success(self):
        """批量反思成功事件。"""
        mgr = SelfReflectionManager()

        events = [
            {"subject_id": "e1", "success": True, "analysis": "Good", "confidence": 0.9},
            {"subject_id": "e2", "success": True, "analysis": "Great", "confidence": 0.95},
        ]

        traces = mgr.batch_reflect(events, ReflectionType.RESULT)
        assert len(traces) == 2
        assert all(t.completed_at > 0 for t in traces)

    def test_batch_reflect_mixed(self):
        """批量反思混合事件。"""
        mgr = SelfReflectionManager()

        events = [
            {"subject_id": "e1", "success": True, "analysis": "Good"},
            {"subject_id": "e2", "success": False, "analysis": "Failed"},
        ]

        traces = mgr.batch_reflect(events, ReflectionType.RESULT)
        assert len(traces) == 2


# =========================================================================
# 6. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = SelfReflectionManager()
        stats = mgr.get_stats()

        assert "reflections_performed" in stats
        assert "wisdom_candidates" in stats
        assert "identity_checks" in stats

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = SelfReflectionManager()

        # 执行一些操作
        trace = mgr.start_reflection(ReflectionType.RESULT, "test")
        mgr.add_insight(trace.trace_id, InsightType.SUCCESS_FACTOR, "Good")
        mgr.complete_reflection(trace.trace_id)
        mgr.propose_wisdom(trace.trace_id, "Wisdom", confidence=0.8)
        mgr.create_identity_snapshot({"state": "test"})

        stats = mgr.get_stats()
        assert stats["reflections_performed"] >= 1
        assert stats["insights_generated"] >= 1
        assert stats["wisdom_candidates"] >= 1
        assert stats["identity_checks"] >= 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = SelfReflectionManager()
        mgr.start_reflection(ReflectionType.RESULT, "test")
        mgr.reset_stats()

        stats = mgr.get_stats()
        assert stats["reflections_performed"] == 0


# =========================================================================
# 7. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_reflections_limit(self):
        """反思数量上限约束。"""
        mgr = SelfReflectionManager(max_reflections=2)

        mgr.start_reflection(ReflectionType.RESULT, "test1")
        mgr.start_reflection(ReflectionType.RESULT, "test2")

        result = mgr.start_reflection(ReflectionType.RESULT, "test3")
        assert result is None

    def test_max_wisdom_limit(self):
        """智慧条目上限约束。"""
        mgr = SelfReflectionManager(max_wisdom_items=2)
        trace = mgr.start_reflection(ReflectionType.PATTERN, "test")

        mgr.propose_wisdom(trace.trace_id, "W1", confidence=0.8)
        mgr.propose_wisdom(trace.trace_id, "W2", confidence=0.8)

        result = mgr.propose_wisdom(trace.trace_id, "W3", confidence=0.8)
        assert result is None

    def test_max_identity_snapshots_limit(self):
        """身份快照上限约束。"""
        mgr = SelfReflectionManager(max_identity_snapshots=2)

        mgr.create_identity_snapshot({"v": 1})
        mgr.create_identity_snapshot({"v": 2})

        # 第三个应替换最旧的
        snapshot = mgr.create_identity_snapshot({"v": 3})
        assert snapshot is not None
        assert len(mgr._identity_snapshots) == 2


# =========================================================================
# 8. 回调测试
# =========================================================================

class TestCallbacks:
    """回调函数测试。"""

    def test_reflection_duration(self):
        """反思持续时间计算。"""
        mgr = SelfReflectionManager()
        trace = mgr.start_reflection(ReflectionType.RESULT, "test")

        import time
        time.sleep(0.01)
        mgr.complete_reflection(trace.trace_id)

        assert trace.duration >= 0
        assert trace.completed_at > trace.created_at


# =========================================================================
# 9. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_reflection_workflow(self):
        """完整反思工作流。"""
        mgr = SelfReflectionManager()

        # 1. 开始反思
        trace = mgr.start_reflection(
            ReflectionType.RESULT,
            "subject-1",
            depth=ReflectionDepth.DEEP,
        )
        assert trace is not None

        # 2. 添加洞察
        mgr.add_insight(trace.trace_id, InsightType.SUCCESS_FACTOR, "Good execution", 0.85)
        mgr.add_insight(trace.trace_id, InsightType.PATTERN_RECOGNIZED, "Pattern detected", 0.75)

        # 3. 完成反思
        mgr.complete_reflection(trace.trace_id)

        # 4. 提出智慧
        wisdom = mgr.propose_wisdom(trace.trace_id, "Consistency leads to success", 0.8)
        assert wisdom is not None

        # 5. 验证智慧
        mgr.verify_wisdom(wisdom.wisdom_id, True)
        assert wisdom.verified is True

        # 6. 创建身份快照
        snapshot = mgr.create_identity_snapshot(
            {"identity": "test", "version": 1},
            continuity_score=0.9,
        )

        # 7. 检查连续性
        continuity = mgr.check_identity_continuity({"identity": "test"})
        assert continuity["drift_detected"] is False

        # 8. 获取统计
        stats = mgr.get_stats()
        assert stats["reflections_performed"] == 1
        assert stats["insights_generated"] == 2
        assert stats["wisdom_confirmed"] == 1


# =========================================================================
# 10. 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_add_insight_to_nonexistent_trace(self):
        """向不存在的轨迹添加洞察。"""
        mgr = SelfReflectionManager()
        result = mgr.add_insight("nonexistent", InsightType.SUCCESS_FACTOR, "test")
        assert result is False

    def test_complete_nonexistent_reflection(self):
        """完成不存在的反思。"""
        mgr = SelfReflectionManager()
        result = mgr.complete_reflection("nonexistent")
        assert result is False

    def test_verify_nonexistent_wisdom(self):
        """验证不存在的智慧。"""
        mgr = SelfReflectionManager()
        result = mgr.verify_wisdom("nonexistent", True)
        assert result is False

    def test_get_nonexistent_reflection(self):
        """获取不存在的反思。"""
        mgr = SelfReflectionManager()
        result = mgr.get_reflection("nonexistent")
        assert result is None
