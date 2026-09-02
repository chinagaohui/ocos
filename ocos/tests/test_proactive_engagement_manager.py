"""Phase AF: ProactiveEngagementManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 参与请求管理
3. 状态转换
4. 频率管理
5. 权限检查
6. 疲劳检测
7. 执行引擎
8. 统计信息
9. 边界约束
10. 端到端流程
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.engagement.manager import (
    ProactiveEngagementManager,
    EngagementRequest,
    EngagementType,
    EngagementSource,
    EngagementStatus,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = ProactiveEngagementManager()
        
        assert mgr.list_requests() == []
        stats = mgr.get_stats()
        assert stats["total_initiatives"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = ProactiveEngagementManager(
            max_daily_initiatives=5,
            max_hourly_initiatives=2,
            fatigue_threshold=0.5,
        )
        
        assert mgr._max_daily_initiatives == 5
        assert mgr._max_hourly_initiatives == 2
        assert mgr._fatigue_threshold == 0.5

    def test_with_permission_guard(self):
        """带权限守卫的初始化。"""
        guard = MagicMock()
        guard.check.return_value = True
        
        mgr = ProactiveEngagementManager(permission_guard=guard)
        assert mgr._permission_guard is guard


# =========================================================================
# 2. 参与请求管理
# =========================================================================

class TestEngagementRequest:
    """参与请求管理测试。"""

    def test_create_request(self):
        """创建参与请求。"""
        mgr = ProactiveEngagementManager()
        
        request = mgr.create_engagement_request(
            engagement_type=EngagementType.OBSERVATION,
            topic="test_topic",
            content="test_content",
            urgency=0.8,
        )
        
        assert request is not None
        assert request.topic == "test_topic"
        assert request.urgency == 0.8
        assert request.status == EngagementStatus.DRAFT

    def test_get_request(self):
        """获取参与请求。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(
            EngagementType.ALERT, "t", "c"
        )
        
        retrieved = mgr.get_request(request.request_id)
        assert retrieved is request

    def test_list_requests(self):
        """列出参与请求。"""
        mgr = ProactiveEngagementManager()
        
        mgr.create_engagement_request(EngagementType.GREETING, "t1", "c1")
        mgr.create_engagement_request(EngagementType.OBSERVATION, "t2", "c2")
        
        requests = mgr.list_requests()
        assert len(requests) == 2

    def test_list_requests_by_status(self):
        """按状态列出参与请求。"""
        mgr = ProactiveEngagementManager()
        
        r1 = mgr.create_engagement_request(EngagementType.GREETING, "t1", "c1")
        r2 = mgr.create_engagement_request(EngagementType.OBSERVATION, "t2", "c2")
        mgr.submit_for_review(r1.request_id)
        
        pending = mgr.list_requests(status=EngagementStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].request_id == r1.request_id


# =========================================================================
# 3. 状态转换
# =========================================================================

class TestStatusTransitions:
    """状态转换测试。"""

    def test_submit_for_review(self):
        """提交审核。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        
        result = mgr.submit_for_review(request.request_id)
        assert result is True
        assert request.status == EngagementStatus.PENDING

    def test_approve_engagement(self):
        """批准参与。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        mgr.submit_for_review(request.request_id)
        
        result = mgr.approve_engagement(request.request_id)
        assert result is True
        assert request.status == EngagementStatus.SENT
        assert request.sent_at > 0

    def test_reject_engagement(self):
        """拒绝参与。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        mgr.submit_for_review(request.request_id)
        
        result = mgr.reject_engagement(request.request_id, "too_risky")
        assert result is True
        assert request.status == EngagementStatus.WITHDRAWN

    def test_mark_ignored(self):
        """标记忽略。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        mgr.submit_for_review(request.request_id)
        mgr.approve_engagement(request.request_id)
        
        result = mgr.mark_ignored(request.request_id)
        assert result is True
        assert request.status == EngagementStatus.IGNORED

    def test_invalid_transition(self):
        """无效状态转换。"""
        mgr = ProactiveEngagementManager()
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        
        # 不能直接从 DRAFT 批准
        assert mgr.approve_engagement(request.request_id) is False


# =========================================================================
# 4. 频率管理
# =========================================================================

class TestFrequencyManagement:
    """频率管理测试。"""

    def test_check_frequency_limit(self):
        """检查频率限制。"""
        mgr = ProactiveEngagementManager(max_daily_initiatives=5)
        
        ok, reason = mgr.check_frequency_limit()
        assert ok is True

    def test_daily_limit_exceeded(self):
        """超过每日限制。"""
        mgr = ProactiveEngagementManager(max_daily_initiatives=2)
        
        mgr.increment_counts()
        mgr.increment_counts()
        
        ok, reason = mgr.check_frequency_limit()
        assert ok is False
        assert reason == "daily_limit"

    def test_hourly_limit_exceeded(self):
        """超过每小时限制。"""
        mgr = ProactiveEngagementManager(max_hourly_initiatives=1)
        
        mgr.increment_counts()
        
        ok, reason = mgr.check_frequency_limit()
        assert ok is False
        assert reason == "hourly_limit"


# =========================================================================
# 5. 权限检查
# =========================================================================

class TestPermissionCheck:
    """权限检查测试。"""

    def test_permission_check_with_guard(self):
        """带权限守卫的检查。"""
        guard = MagicMock()
        guard.check.return_value = True
        
        mgr = ProactiveEngagementManager(permission_guard=guard)
        request = mgr.create_engagement_request(EngagementType.ALERT, "t", "c")
        
        ok, reason = mgr.check_permission(request)
        assert ok is True

    def test_permission_denied(self):
        """权限被拒绝。"""
        guard = MagicMock()
        guard.check.return_value = False
        
        mgr = ProactiveEngagementManager(permission_guard=guard)
        request = mgr.create_engagement_request(EngagementType.ALERT, "t", "c")
        
        ok, reason = mgr.check_permission(request)
        assert ok is False

    def test_dual_check_pass(self):
        """双检通过。"""
        guard = MagicMock()
        guard.check.return_value = True
        
        mgr = ProactiveEngagementManager(permission_guard=guard)
        request = mgr.create_engagement_request(EngagementType.ALERT, "t", "c")
        
        ok, reason = mgr.dual_check(request)
        assert ok is True

    def test_dual_check_fail(self):
        """双检失败。"""
        guard = MagicMock()
        guard.check.return_value = False
        
        mgr = ProactiveEngagementManager(permission_guard=guard)
        request = mgr.create_engagement_request(EngagementType.ALERT, "t", "c")
        
        ok, reason = mgr.dual_check(request)
        assert ok is False
        assert "permission" in reason


# =========================================================================
# 6. 疲劳检测
# =========================================================================

class TestFatigueCheck:
    """疲劳检测测试。"""

    def test_fatigue_ok(self):
        """疲劳水平正常。"""
        mgr = ProactiveEngagementManager(fatigue_threshold=0.7)
        
        ok, reason = mgr.check_fatigue(0.5)
        assert ok is True

    def test_fatigue_exceeded(self):
        """疲劳水平超限。"""
        mgr = ProactiveEngagementManager(fatigue_threshold=0.7)
        
        ok, reason = mgr.check_fatigue(0.8)
        assert ok is False
        assert reason == "fatigue"


# =========================================================================
# 7. 执行引擎
# =========================================================================

class TestExecutionEngine:
    """执行引擎测试。"""

    def test_execute_success(self):
        """成功执行。"""
        mgr = ProactiveEngagementManager()
        received = []
        mgr.set_output_callback(lambda m: received.append(m))
        
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "hello")
        mgr.submit_for_review(request.request_id)
        mgr.approve_engagement(request.request_id)
        
        result = mgr.execute_engagement(request.request_id, fatigue_level=0.3)
        assert result["success"] is True
        assert len(received) == 1

    def test_execute_frequency_blocked(self):
        """频率限制阻止执行。"""
        mgr = ProactiveEngagementManager(max_daily_initiatives=0)
        
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "hello")
        result = mgr.execute_engagement(request.request_id)
        assert "error" in result
        assert "frequency_limit" in result["error"]

    def test_execute_fatigue_blocked(self):
        """疲劳阻止执行。"""
        mgr = ProactiveEngagementManager()
        
        request = mgr.create_engagement_request(EngagementType.GREETING, "t", "hello")
        result = mgr.execute_engagement(request.request_id, fatigue_level=0.9)
        assert "error" in result
        assert "fatigue" in result["error"]

    def test_execute_nonexistent(self):
        """执行不存在的请求。"""
        mgr = ProactiveEngagementManager()
        
        result = mgr.execute_engagement("eng:nonexistent")
        assert "error" in result


# =========================================================================
# 8. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = ProactiveEngagementManager()
        
        stats = mgr.get_stats()
        assert "total_initiatives" in stats
        assert "initiatives_sent" in stats

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = ProactiveEngagementManager()
        
        mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        stats = mgr.get_stats()
        assert stats["total_initiatives"] >= 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = ProactiveEngagementManager()
        mgr.create_engagement_request(EngagementType.GREETING, "t", "c")
        mgr.reset_stats()
        
        stats = mgr.get_stats()
        assert stats["total_initiatives"] == 0
        assert stats["daily_count"] == 0


# =========================================================================
# 9. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_requests_limit(self):
        """请求数量上限约束。"""
        mgr = ProactiveEngagementManager()
        
        # 创建大量请求（不超过内部限制）
        for i in range(10):
            mgr.create_engagement_request(EngagementType.GREETING, f"t{i}", "c")
        
        assert len(mgr.list_requests()) == 10


# =========================================================================
# 10. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_engagement_workflow(self):
        """完整参与工作流。"""
        mgr = ProactiveEngagementManager(
            max_daily_initiatives=5,
            max_hourly_initiatives=2,
        )
        
        received = []
        mgr.set_output_callback(lambda m: received.append(m))
        
        # 1. 创建请求
        request = mgr.create_engagement_request(
            engagement_type=EngagementType.OBSERVATION,
            topic="pattern_detected",
            content="I noticed you've been working on OCOS for hours",
            urgency=0.6,
            source=EngagementSource.PATTERN_CHANGE,
        )
        assert request is not None
        
        # 2. 提交审核
        assert mgr.submit_for_review(request.request_id) is True
        
        # 3. 批准
        assert mgr.approve_engagement(request.request_id) is True
        
        # 4. 执行
        result = mgr.execute_engagement(request.request_id, fatigue_level=0.3)
        assert result["success"] is True
        
        # 5. 验证
        assert len(received) == 1
        assert "观察" in received[0]
        
        # 6. 统计
        stats = mgr.get_stats()
        assert stats["initiatives_sent"] >= 1


# =========================================================================
# 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_get_nonexistent_request(self):
        """获取不存在的请求。"""
        mgr = ProactiveEngagementManager()
        result = mgr.get_request("eng:nonexistent")
        assert result is None

    def test_submit_nonexistent(self):
        """提交不存在的请求。"""
        mgr = ProactiveEngagementManager()
        result = mgr.submit_for_review("eng:nonexistent")
        assert result is False

    def test_approve_nonexistent(self):
        """批准不存在的请求。"""
        mgr = ProactiveEngagementManager()
        result = mgr.approve_engagement("eng:nonexistent")
        assert result is False
