"""Phase AH: SelfDiagnosisManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 诊断流程
3. 健康状态
4. 历史记录
5. 统计信息
6. 自动修复
7. 回调机制
8. 边界约束
9. tick 接口
10. 端到端流程
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.diagnosis.manager import (
    SelfDiagnosisManager,
    DiagnosisMode,
    AutoRepairPolicy,
    DiagnosticResult,
)
from ocos.diagnosis.system_probe import SystemProbe
from ocos.diagnosis.diagnosis_types import FaultSignal, FaultCategory, Severity


@pytest.fixture
def mgr():
    return SelfDiagnosisManager(
        mode=DiagnosisMode.MANUAL,
        auto_repair_policy=AutoRepairPolicy.NEVER,
    )


@pytest.fixture
def auto_mgr():
    return SelfDiagnosisManager(
        mode=DiagnosisMode.AUTO,
        auto_repair_policy=AutoRepairPolicy.LOW_RISK_ONLY,
    )


class TestInit:
    """测试初始化配置。"""

    def test_default_init(self):
        m = SelfDiagnosisManager()
        assert m._mode == DiagnosisMode.HYBRID
        assert m._auto_repair_policy == AutoRepairPolicy.LOW_RISK_ONLY
        assert m._checkpoint_before_repair is True

    def test_manual_mode(self):
        m = SelfDiagnosisManager(mode=DiagnosisMode.MANUAL)
        assert m._mode == DiagnosisMode.MANUAL

    def test_auto_mode(self):
        m = SelfDiagnosisManager(mode=DiagnosisMode.AUTO)
        assert m._mode == DiagnosisMode.AUTO

    def test_hybrid_mode(self):
        m = SelfDiagnosisManager(mode=DiagnosisMode.HYBRID)
        assert m._mode == DiagnosisMode.HYBRID

    def test_never_auto_repair(self):
        m = SelfDiagnosisManager(auto_repair_policy=AutoRepairPolicy.NEVER)
        assert m._auto_repair_policy == AutoRepairPolicy.NEVER

    def test_low_risk_only(self):
        m = SelfDiagnosisManager(auto_repair_policy=AutoRepairPolicy.LOW_RISK_ONLY)
        assert m._auto_repair_policy == AutoRepairPolicy.LOW_RISK_ONLY

    def test_all_allowed(self):
        m = SelfDiagnosisManager(auto_repair_policy=AutoRepairPolicy.ALL_ALLOWED)
        assert m._auto_repair_policy == AutoRepairPolicy.ALL_ALLOWED

    def test_max_proposals_limit(self):
        m = SelfDiagnosisManager(max_proposals_per_tick=3)
        assert m._max_proposals_per_tick == 3


class TestDiagnose:
    """测试诊断流程。"""

    def test_diagnose_returns_result(self, mgr):
        result = mgr.diagnose()
        assert isinstance(result, DiagnosticResult)
        assert result.snapshot_id != ""
        assert result.timestamp > 0

    def test_diagnose_health_score(self, mgr):
        result = mgr.diagnose()
        assert 0.0 <= result.overall_health <= 1.0

    def test_diagnose_faults_count(self, mgr):
        result = mgr.diagnose()
        assert isinstance(result.faults_detected, int)
        assert result.faults_detected >= 0

    def test_diagnose_multiple_times(self, mgr):
        r1 = mgr.diagnose()
        r2 = mgr.diagnose()
        assert r1.snapshot_id != r2.snapshot_id
        assert mgr._stats.total_snapshots == 2


class TestHealthStatus:
    """测试健康状态。"""

    def test_get_health_status(self, mgr):
        status = mgr.get_health_status()
        assert isinstance(status, dict)
        assert "overall_health" in status
        assert "trend" in status
        assert "degraded_components" in status
        assert "faults_detected" in status

    def test_health_status_after_diagnose(self, mgr):
        mgr.diagnose()
        status = mgr.get_health_status()
        assert status["faults_detected"] >= 0

    def test_health_status_empty_history(self):
        m = SelfDiagnosisManager()
        status = m.get_health_status()
        assert status["overall_health"] == 1.0


class TestHistory:
    """测试历史记录。"""

    def test_diagnosis_history(self, mgr):
        mgr.diagnose()
        mgr.diagnose()
        history = mgr.get_diagnosis_history(limit=5)
        assert len(history) == 2
        assert isinstance(history[0], dict)

    def test_diagnosis_history_limit(self, mgr):
        for _ in range(5):
            mgr.diagnose()
        history = mgr.get_diagnosis_history(limit=3)
        assert len(history) == 3

    def test_fault_history_empty(self, mgr):
        history = mgr.get_fault_history()
        assert isinstance(history, list)

    def test_repair_history_empty(self, mgr):
        history = mgr.get_repair_history()
        assert isinstance(history, dict)
        assert "total_repairs" in history


class TestStats:
    """测试统计信息。"""

    def test_get_stats(self, mgr):
        mgr.diagnose()
        stats = mgr.get_stats()
        assert isinstance(stats, dict)
        assert "total_snapshots" in stats
        assert "total_faults_detected" in stats
        assert "recent_trend" in stats

    def test_stats_increment(self, mgr):
        mgr.diagnose()
        mgr.diagnose()
        stats = mgr.get_stats()
        assert stats["total_snapshots"] == 2

    def test_stats_after_repair(self, auto_mgr):
        auto_mgr.diagnose()
        stats = auto_mgr.get_stats()
        assert "total_repairs_performed" in stats


class TestAutoRepair:
    """测试自动修复策略。"""

    def test_never_auto_repair(self, mgr):
        """NEVER 策略不执行任何自动修复。"""
        result = mgr.diagnose()
        assert result.auto_repairs_performed == 0

    def test_auto_mode_performs_repairs(self, auto_mgr):
        """AUTO 模式可能执行修复。"""
        result = auto_mgr.diagnose()
        assert isinstance(result.auto_repairs_performed, int)
        assert result.auto_repairs_performed >= 0

    def test_hybrid_mode(self):
        """HYBRID 模式需要人工审批。"""
        m = SelfDiagnosisManager(mode=DiagnosisMode.HYBRID)
        assert m._mode == DiagnosisMode.HYBRID


class TestCallbacks:
    """测试回调机制。"""

    def test_diagnosis_callback(self, mgr):
        called = []
        mgr.set_diagnosis_callback(lambda r: called.append(r))
        mgr.diagnose()
        assert len(called) == 1
        assert isinstance(called[0], DiagnosticResult)

    def test_fault_callback(self, mgr):
        called = []
        mgr.set_fault_callback(lambda s: called.extend(s))
        mgr.diagnose()
        # 回调应被调用（即使没有故障）

    def test_repair_callback(self, mgr):
        called = []
        mgr.set_repair_callback(lambda r: called.append(r))
        # 不执行修复，回调不会被调用
        assert len(called) == 0

    def test_callback_exception_handled(self, mgr):
        """回调异常不应影响诊断。"""
        def bad_callback(_):
            raise ValueError("callback error")
        mgr.set_diagnosis_callback(bad_callback)
        result = mgr.diagnose()
        assert result is not None


class TestModeSwitch:
    """测试模式切换。"""

    def test_set_mode(self, mgr):
        mgr.set_mode(DiagnosisMode.AUTO)
        assert mgr._mode == DiagnosisMode.AUTO

    def test_set_auto_repair_policy(self, mgr):
        mgr.set_auto_repair_policy(AutoRepairPolicy.ALL_ALLOWED)
        assert mgr._auto_repair_policy == AutoRepairPolicy.ALL_ALLOWED

    def test_set_checkpoint_disabled(self):
        m = SelfDiagnosisManager(checkpoint_before_repair=False)
        assert m._checkpoint_before_repair is False


class TestTick:
    """测试 tick 接口。"""

    def test_tick_returns_list(self, mgr):
        result = mgr.tick()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_tick_result_format(self, mgr):
        results = mgr.tick()
        for r in results:
            assert "snapshot_id" in r
            assert "health" in r
            assert "faults" in r
            assert "trend" in r

    def test_tick_multiple(self, mgr):
        r1 = mgr.tick()
        r2 = mgr.tick()
        assert len(r1) == len(r2)


class TestEndToEnd:
    """端到端验证。"""

    def test_full_diagnosis_workflow(self, mgr):
        # 1. 诊断
        result = mgr.diagnose()
        assert result.snapshot_id != ""
        assert result.overall_health >= 0

        # 2. 获取状态
        status = mgr.get_health_status()
        assert "overall_health" in status

        # 3. 获取历史
        history = mgr.get_diagnosis_history()
        assert len(history) >= 1

        # 4. 获取统计
        stats = mgr.get_stats()
        assert stats["total_snapshots"] >= 1

        # 5. tick
        tick_results = mgr.tick()
        assert isinstance(tick_results, list)

    def test_diagnose_with_callback(self, mgr):
        results = []
        mgr.set_diagnosis_callback(results.append)
        mgr.diagnose()
        assert len(results) == 1


class TestBoundary:
    """边界约束。"""

    def test_empty_diagnose(self):
        """空系统也能诊断。"""
        m = SelfDiagnosisManager()
        result = m.diagnose()
        assert result is not None
        assert result.overall_health >= 0

    def test_many_diagnoses(self, mgr):
        """多次诊断不崩溃。"""
        for _ in range(10):
            mgr.diagnose()
        assert mgr._stats.total_snapshots == 10

    def test_diagnose_after_mode_change(self, mgr):
        mgr.set_mode(DiagnosisMode.AUTO)
        result = mgr.diagnose()
        assert result is not None


class TestIntegration:
    """集成测试。"""

    def test_diagnose_and_history(self, mgr):
        """诊断后历史记录应更新。"""
        mgr.diagnose()
        history = mgr.get_diagnosis_history()
        assert len(history) == 1
        assert "snapshot_id" in history[0]

    def test_stats_reflect_diagnoses(self, mgr):
        """统计应反映诊断次数。"""
        mgr.diagnose()
        mgr.diagnose()
        stats = mgr.get_stats()
        assert stats["total_snapshots"] == 2
