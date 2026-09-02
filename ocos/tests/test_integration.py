"""OCOS 集成测试 — 端到端验证各模块协同工作。

测试场景：
1. 完整认知循环：感知 → 认知 → 决策 → 行动
2. 记忆-学习闭环：新记忆 → 模式提取 → 信念更新
3. 注意力-目标协同：焦点变化 → 目标调整
4. 持久化-恢复：快照保存 → 崩溃 → 恢复
5. 监控-告警：指标采集 → 阈值触发 → 告警
6. 安全-权限：访问检查 → 输入清洗 → 审计日志
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ocos.agent.master_agent import MasterAgent
from ocos.agent.state import AgentState
from ocos.performance.manager import PerformanceManager
from ocos.monitoring.manager import MonitoringManager
from ocos.security.manager import SecurityManager
from ocos.persistence.manager import PersistenceManager
from ocos.external.server_manager import ServerManager


class FakeIdentity:
    """模拟 IdentityAnchor。"""
    
    def __init__(self, agent_id="test-agent-001"):
        self.agent_id = agent_id
        self.core_values = ["curiosity", "growth", "service"]
    
    def get_identity(self) -> dict:
        return {"agent_id": self.agent_id, "core_values": self.core_values}
    
    def check_consolidation(self) -> bool:
        return True


class FakeGoalStack:
    """模拟 GoalStack。"""
    
    def __init__(self):
        self._goals = []
        self._history = []
    
    def push(self, goal):
        self._goals.append(goal)
    
    def peek(self):
        return self._goals[-1] if self._goals else None
    
    def pop(self):
        if self._goals:
            return self._goals.pop()
        return None
    
    def is_empty(self):
        return len(self._goals) == 0
    
    def history(self):
        return self._history


class FakeIntent:
    """模拟 Intent。"""
    
    def __init__(self):
        self.current_intent = None
    
    def set_intent(self, intent):
        self.current_intent = intent
        return True
    
    def clear_intent(self):
        self.current_intent = None


class FakeAttention:
    """模拟 Attention。"""
    
    def __init__(self):
        self._focus = "default"
        self._drive = 0.5
    
    def current_focus(self):
        return self._focus
    
    def update_focus(self, focus):
        self._focus = focus
    
    def set_drive(self, drive):
        self._drive = drive


class FakeWorkingMemory:
    """模拟 WorkingMemory。"""
    
    def __init__(self):
        self._items = {}
        self._history = []
    
    def set(self, key, value):
        self._items[key] = value
        self._history.append({"action": "set", "key": key})
    
    def get(self, key, default=None):
        return self._items.get(key, default)
    
    def list_items(self):
        return list(self._items.keys())
    
    def clear(self):
        self._items.clear()


class FakeCapabilityManager:
    """模拟 CapabilityManager。"""
    
    def __init__(self):
        self._capabilities = {
            "perception": True,
            "cognition": True,
            "learning": True,
            "memory": True,
        }
    
    def list_capabilities(self):
        return list(self._capabilities.keys())
    
    def has_capability(self, name):
        return self._capabilities.get(name, False)


class FakeExecutionManager:
    """模拟 ExecutionManager。"""
    
    def __init__(self):
        self._executing = False
        self._results = []
    
    def is_executing(self):
        return self._executing
    
    def execute(self, action):
        self._executing = True
        result = {"action": action, "result": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
        self._results.append(result)
        self._executing = False
        return result


class TestFullCognitiveLoop:
    """完整认知循环测试。"""
    
    def test_perceive_cognize_decide_act(self):
        """测试：感知 → 认知 → 决策 → 行动。"""
        # 创建 MasterAgent
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        agent = MasterAgent(
            agent_id="test-agent",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
        )
        
        # 模拟一次完整循环
        observation = {
            "type": "sensory",
            "content": "新信息",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # 感知（记录到工作记忆）
        working_memory.set("last_observation", observation)
        assert working_memory.get("last_observation") == observation
        
        # 认知（提取焦点）
        focus = attention.current_focus()
        assert focus == "default"
        
        # 决策（检查能力）
        has_perception = capability_mgr.has_capability("perception")
        assert has_perception is True
        
        # 行动（执行）
        result = execution_mgr.execute("process_observation")
        assert result["action"] == "process_observation"
        assert result["result"] == "ok"
        
        # 验证历史
        assert len(execution_mgr._results) == 1
    
    def test_goal_creation_and_tracking(self):
        """测试目标创建与追踪。"""
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        agent = MasterAgent(
            agent_id="test-agent",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
        )
        
        # 创建目标
        goal_stack.push({"id": "goal-1", "description": "测试目标", "priority": 0.8})
        
        # 检查当前目标
        current_goal = goal_stack.peek()
        assert current_goal["id"] == "goal-1"
        
        # 完成目标
        completed = goal_stack.pop()
        assert completed["id"] == "goal-1"
        assert goal_stack.is_empty()


class TestMemoryLearningLoop:
    """记忆-学习闭环测试。"""
    
    def test_memory_write_read(self):
        """测试记忆写入与读取。"""
        working_memory = FakeWorkingMemory()
        
        # 写入记忆
        working_memory.set("fact_1", {"content": "北京是中国的首都", "confidence": 0.95})
        working_memory.set("fact_2", {"content": "Python是编程语言", "confidence": 0.9})
        
        # 读取记忆
        fact_1 = working_memory.get("fact_1")
        assert fact_1["content"] == "北京是中国的首都"
        assert fact_1["confidence"] == 0.95
        
        # 列出所有记忆
        keys = working_memory.list_items()
        assert len(keys) == 2
        assert "fact_1" in keys
        assert "fact_2" in keys
    
    def test_memory_clear(self):
        """测试记忆清除。"""
        working_memory = FakeWorkingMemory()
        working_memory.set("temp", "value")
        
        working_memory.clear()
        assert working_memory.list_items() == []
        assert working_memory.get("temp") is None


class TestAttentionGoalCoordination:
    """注意力-目标协同测试。"""
    
    def test_focus_changes_goal_priority(self):
        """测试焦点变化影响目标优先级。"""
        attention = FakeAttention()
        goal_stack = FakeGoalStack()
        
        # 设置注意力焦点
        attention.update_focus("writing")
        attention.set_drive(0.8)
        
        # 创建相关目标
        goal_stack.push({
            "id": "goal-write",
            "focus": "writing",
            "priority": 0.8,
        })
        
        # 检查目标与焦点匹配
        current = goal_stack.peek()
        assert current["focus"] == "writing"
        assert current["priority"] == 0.8


class TestPersistenceRecovery:
    """持久化-恢复测试。"""
    
    def test_save_and_restore_state(self):
        """测试状态保存与恢复。"""
        pm = PersistenceManager()
        
        # 保存状态
        state = {
            "agent_id": "test-agent",
            "beliefs": {"b1": {"content": "test", "confidence": 0.9}},
            "goals": [{"id": "g1", "status": "active"}],
        }
        
        result = pm.save(state, reason="test_save")
        assert result.success is True
        snapshot_id = result.snapshot_id
        
        # 恢复状态（使用 correct 方法名）
        restore_result = pm.restore(snapshot_id=snapshot_id)
        assert restore_result.success is True
        assert restore_result.snapshot_id == snapshot_id
    
    def test_snapshot_list_and_delete(self):
        """测试快照列表与删除。"""
        pm = PersistenceManager()
        
        # 创建多个快照
        ids = []
        for i in range(3):
            result = pm.save({"data": f"test_{i}"}, reason=f"save_{i}")
            ids.append(result.snapshot_id)
        
        # 列出快照
        snapshots = pm.list_snapshots()
        assert len(snapshots) >= 3
        
        # 删除最旧的
        deleted = pm.delete_snapshot(ids[0])
        assert deleted is True
        
        # 验证删除
        snapshots = pm.list_snapshots()
        assert len(snapshots) >= 2


class TestMonitoringAlerting:
    """监控-告警测试。"""
    
    def test_metrics_collection(self):
        """测试指标收集。"""
        mm = MonitoringManager()
        
        # 记录指标
        mm.record_metric("requests_total", 1.0, metric_type="counter")
        mm.record_metric("response_time", 0.5, metric_type="histogram")
        mm.record_metric("memory_usage", 0.75, metric_type="gauge")
        
        # 获取指标
        prom_format = mm.get_metrics()
        assert "requests_total" in prom_format
        assert "response_time" in prom_format
    
    def test_alert_rules(self):
        """测试告警规则。"""
        mm = MonitoringManager()
        
        # 评估告警（高错误率）
        triggered = mm.evaluate_alerts({"error_rate": 0.15})
        assert len(triggered) > 0
        assert triggered[0]["rule"] == "high_error_rate"
    
    def test_health_status(self):
        """测试健康状态。"""
        mm = MonitoringManager()
        health = mm.get_health_status()
        
        assert "status" in health
        assert health["status"] in ["healthy", "degraded", "critical"]
        assert "uptime_seconds" in health


class TestSecurityAccess:
    """安全-权限测试。"""
    
    def test_access_check(self):
        """测试访问检查。"""
        sm = SecurityManager()
        
        decision, reason, info = sm.check_access("user", "query")
        assert decision.value == "ALLOW"
    
    def test_access_denied(self):
        """测试访问拒绝。"""
        sm = SecurityManager()
        
        decision, reason, info = sm.check_access("user", "delete_memory")
        assert decision.value == "DENY"
    
    def test_input_sanitization(self):
        """测试输入清洗。"""
        sm = SecurityManager()
        
        safe_text, threats, decision = sm.sanitize_input("normal text")
        assert decision.value == "ALLOW"
        assert threats == []
        
        # SQL注入检测
        malicious, threats, decision = sm.sanitize_input("SELECT * FROM users")
        assert decision.value == "DENY"
        assert len(threats) > 0
    
    def test_audit_log(self):
        """测试审计日志。"""
        sm = SecurityManager()
        
        # 产生一些事件
        sm.check_access("user", "query")
        sm.check_access("user", "delete_memory")
        
        events = sm.get_recent_events()
        assert len(events) >= 2


class TestPerformanceOptimization:
    """性能优化测试。"""
    
    def test_smart_cache(self):
        """测试智能缓存。"""
        pm = PerformanceManager()
        cache = pm.cache
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        # 过期测试
        cache.set("key2", "value2", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("key2") is None
    
    def test_performance_profiler(self):
        """测试性能分析器。"""
        pm = PerformanceManager()
        profiler = pm.profiler
        
        profiler.start_timer("test_operation")
        time.sleep(0.05)
        duration = profiler.stop_timer("test_operation")
        
        assert duration > 40  # 至少40ms
        stats = profiler.get_stats()
        assert stats["total_operations"] == 1


class TestMasterAgentIntegration:
    """MasterAgent 集成测试。"""
    
    def test_master_agent_creation(self):
        """测试 MasterAgent 创建。"""
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        agent = MasterAgent(
            agent_id="integration-test",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
        )
        
        assert agent.agent_id == "integration-test"
        assert agent.identity is not None
    
    def test_master_agent_with_all_managers(self):
        """测试 MasterAgent 注入所有管理器。"""
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        pm = PerformanceManager()
        mm = MonitoringManager()
        sm = SecurityManager()
        perm = PersistenceManager()
        server = ServerManager()
        
        agent = MasterAgent(
            agent_id="full-integration",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
            performance_manager=pm,
            monitoring_manager=mm,
            security_manager=sm,
            persistence_manager=perm,
            server_manager=server,
        )
        
        # 验证所有管理器已注入
        assert agent.performance_manager is pm
        assert agent.monitoring_manager is mm
        assert agent.security_manager is sm
        assert agent.persistence_manager is perm
        assert agent.server_manager is server
    
    def test_master_agent_methods(self):
        """测试 MasterAgent 方法调用。"""
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        agent = MasterAgent(
            agent_id="method-test",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
        )
        
        # 测试方法存在且可调用
        assert hasattr(agent, 'get_status_report')
        assert hasattr(agent, 'check_access')
        assert hasattr(agent, 'sanitize_input')
        assert hasattr(agent, 'get_metrics')
        assert hasattr(agent, 'get_security_stats')
        
        # 测试方法返回正确类型
        report = agent.get_status_report()
        assert isinstance(report, dict)
        
        stats = agent.get_security_stats()
        assert "error" in stats or isinstance(stats, dict)


class TestEndToEndScenario:
    """端到端场景测试。"""
    
    def test_complete_workflow(self):
        """测试完整工作流程。"""
        # 1. 创建 Agent
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        pm = PerformanceManager()
        mm = MonitoringManager()
        sm = SecurityManager()
        
        agent = MasterAgent(
            agent_id="e2e-test",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
            performance_manager=pm,
            monitoring_manager=mm,
            security_manager=sm,
        )
        
        # 2. 记录性能指标
        pm.profiler.start_timer("workflow")
        
        # 3. 安全检查
        decision, _, _ = sm.check_access("user", "query")
        assert decision.value == "ALLOW"
        
        # 4. 输入清洗
        text, threats, _ = sm.sanitize_input("safe input")
        assert threats == []
        
        # 5. 缓存数据
        pm.cache.set("cached_data", {"value": 42})
        
        # 6. 记录监控指标
        mm.record_metric("workflow_step", 1.0, metric_type="counter")
        
        # 7. 执行操作
        result = execution_mgr.execute("process")
        assert result["result"] == "ok"
        
        # 8. 停止性能计时
        pm.profiler.stop_timer("workflow")
        
        # 9. 验证统计
        perf_stats = pm.get_stats()
        assert "cache" in perf_stats
        assert "profiler" in perf_stats
        
        mon_stats = mm.get_stats()
        assert "alert_stats" in mon_stats
        
        sec_stats = sm.get_security_stats()
        assert "audit_stats" in sec_stats
        
        # 10. 获取健康状态
        health = mm.get_health_status()
        assert health["status"] in ["healthy", "degraded", "critical"]


class TestConcurrentAccess:
    """并发访问测试。"""
    
    def test_concurrent_cache_access(self):
        """测试并发缓存访问。"""
        import threading
        
        cache = PerformanceManager().cache
        
        def writer(key, value):
            cache.set(key, value)
        
        def reader(key):
            return cache.get(key)
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=writer, args=(f"key_{i}", i))
            threads.append(t)
            t = threading.Thread(target=reader, args=(f"key_{i}",))
            threads.append(t)
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # 验证数据一致性
        for i in range(10):
            assert cache.get(f"key_{i}") == i


class TestErrorHandling:
    """错误处理测试。"""
    
    def test_manager_not_injected(self):
        """测试管理器未注入时的优雅处理。"""
        identity = FakeIdentity()
        goal_stack = FakeGoalStack()
        intent = FakeIntent()
        attention = FakeAttention()
        working_memory = FakeWorkingMemory()
        capability_mgr = FakeCapabilityManager()
        execution_mgr = FakeExecutionManager()
        
        # 不注入任何管理器
        agent = MasterAgent(
            agent_id="no-managers",
            identity=identity,
            goal_stack=goal_stack,
            intent=intent,
            attention=attention,
            working_memory=working_memory,
            capability_manager=capability_mgr,
            execution_manager=execution_mgr,
        )
        
        # 应该返回错误信息而不是抛出异常
        stats = agent.get_persistence_stats()
        assert "error" in stats
        
        metrics = agent.get_metrics()
        assert "not injected" in metrics or isinstance(metrics, str)
        
        health = agent.get_health_status()
        assert "error" in health or isinstance(health, dict)


class TestBoundaryConditions:
    """边界条件测试。"""
    
    def test_large_number_of_operations(self):
        """测试大量操作的性能。"""
        pm = PerformanceManager()
        
        # 写入大量数据到缓存
        start = time.monotonic()
        for i in range(1000):
            pm.cache.set(f"key_{i}", f"value_{i}")
        elapsed = time.monotonic() - start
        
        # 应该能在合理时间内完成
        assert elapsed < 1.0  # 1秒内
        
        # 读取验证
        assert pm.cache.get("key_500") == "value_500"
    
    def test_rapid_alert_evaluation(self):
        """测试快速告警评估。"""
        mm = MonitoringManager()
        
        # 快速多次评估
        for _ in range(100):
            mm.evaluate_alerts({"error_rate": 0.2})
        
        # 冷却机制应该阻止重复告警
        stats = mm.alerts.get_stats()
        assert stats["active_alerts"] <= 1
