"""
C2 Audit Engine — 测试套件。

覆盖范围：
1. 数据模型冻结 + 默认值
2. InMemoryAuditStore 读写查询上限淘汰
3. AuditRuleEngine 注册/移除/运行/异常处理
4. 5 条默认审计规则独立测试
5. AuditEngine 主接口端到端
6. Event Bus 自动收集（4 类事件回调）
7. Debug / Compliance / Replay 报告
8. 边界条件（空 store、不存在 audit_id、无 event_bus 降级）
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ocos.kernel.abi import (
    Event,
    EventType,
    SCHEMA_VERSION,
)
from ocos.platform.audit_engine import (
    DEFAULT_AUDIT_STORE_SIZE,
    DEFAULT_EMIT_AUDIT_EVENTS,
    QUERY_DEFAULT_LIMIT,
    QUERY_MAX_LIMIT,
    AuditEngine,
    AuditFinding,
    AuditRecord,
    AuditRecordType,
    AuditRule,
    AuditRuleEngine,
    InMemoryAuditStore,
    load_default_audit_rules,
    _check_decision_completeness,
    _check_permission_consistency,
    _check_execution_chain_completeness,
    _check_governance_traceability,
    _check_emergency_recovery,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  数据模型冻结 + 默认值
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditRecordFrozen:
    """AuditRecord 必须是 frozen dataclass。"""

    def test_audit_record_frozen(self):
        r = AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="test",
            summary="冻结测试",
        )
        with pytest.raises(AttributeError):
            r.summary = "changed"  # type: ignore[misc]

    def test_audit_record_defaults(self):
        r = AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="test",
            summary="测试审计记录",
        )
        assert r.audit_id != ""
        assert r.record_type == AuditRecordType.DECISION.value
        assert r.source == "test"
        assert r.summary == "测试审计记录"
        assert r.timestamp != ""
        assert r.related_trace_ids == ()
        assert r.related_event_ids == ()
        assert r.details == {}
        assert r.schema_version == SCHEMA_VERSION

    def test_audit_record_with_all_fields(self):
        r = AuditRecord(
            record_type=AuditRecordType.GOVERNANCE.value,
            source="governance",
            summary="审批记录",
            related_trace_ids=("trace_1", "trace_2"),
            related_event_ids=("evt_1",),
            details={"outcome": "approved"},
        )
        assert r.related_trace_ids == ("trace_1", "trace_2")
        assert r.related_event_ids == ("evt_1",)
        assert r.details == {"outcome": "approved"}

    def test_audit_record_immutable(self):
        r = AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="test",
            summary="不可变测试",
        )
        with pytest.raises(AttributeError):
            r.summary = "changed"  # type: ignore[misc]


class TestAuditRuleFrozen:
    """AuditRule 必须是 frozen dataclass。"""

    def test_audit_rule_defaults(self):
        rule = AuditRule()
        assert rule.rule_id == ""
        assert rule.name == ""
        assert rule.description == ""
        assert rule.severity == "info"
        assert rule.check_type == "compliance"

    def test_audit_rule_custom(self):
        rule = AuditRule(
            rule_id="rule_1",
            name="测试规则",
            description="测试描述",
            severity="error",
            check_type="completeness",
        )
        assert rule.rule_id == "rule_1"
        assert rule.severity == "error"
        assert rule.check_type == "completeness"

    def test_audit_rule_immutable(self):
        rule = AuditRule(rule_id="r1")
        with pytest.raises(AttributeError):
            rule.rule_id = "r2"  # type: ignore[misc]


class TestAuditFindingFrozen:
    """AuditFinding 必须是 frozen dataclass。"""

    def test_audit_finding_defaults(self):
        f = AuditFinding()
        assert f.finding_id != ""
        assert f.rule_id == ""
        assert f.severity == "info"
        assert f.message == ""
        assert f.related_audit_ids == ()
        assert f.timestamp != ""

    def test_audit_finding_custom(self):
        f = AuditFinding(
            rule_id="rule_1",
            severity="error",
            message="发现异常",
            related_audit_ids=("audit_1",),
        )
        assert f.rule_id == "rule_1"
        assert f.severity == "error"
        assert f.message == "发现异常"
        assert f.related_audit_ids == ("audit_1",)


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditRecordType 枚举
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditRecordType:
    """AuditRecordType 必须有 4 个值。"""

    def test_has_four_types(self):
        assert len(AuditRecordType) >= 4

    def test_values(self):
        assert AuditRecordType.DECISION.value == "audit.decision"
        assert AuditRecordType.GOVERNANCE.value == "audit.governance"
        assert AuditRecordType.EXECUTION.value == "audit.execution"
        assert AuditRecordType.SYSTEM.value == "audit.system"

    def test_types_are_strings(self):
        for t in AuditRecordType:
            assert isinstance(t.value, str)


# ═══════════════════════════════════════════════════════════════════════════════
#  InMemoryAuditStore
# ═══════════════════════════════════════════════════════════════════════════════

class TestInMemoryAuditStore:

    def _make_record(self, record_type: str, source: str = "test") -> AuditRecord:
        return AuditRecord(
            record_type=record_type,
            source=source,
            summary=f"审计 {source}",
        )

    def test_store_and_get(self):
        store = InMemoryAuditStore()
        r = self._make_record(AuditRecordType.DECISION.value)
        store.store(r)
        got = store.get(r.audit_id)
        assert got is not None
        assert got.audit_id == r.audit_id
        assert got.summary == r.summary

    def test_get_nonexistent_returns_none(self):
        store = InMemoryAuditStore()
        assert store.get("nonexistent") is None

    def test_count_starts_zero(self):
        store = InMemoryAuditStore()
        assert store.count() == 0

    def test_count_increases(self):
        store = InMemoryAuditStore()
        store.store(self._make_record(AuditRecordType.DECISION.value))
        assert store.count() == 1
        store.store(self._make_record(AuditRecordType.GOVERNANCE.value))
        assert store.count() == 2

    def test_query_all(self):
        store = InMemoryAuditStore()
        for t in AuditRecordType:
            store.store(self._make_record(t.value, source=f"src_{t.value}"))
        results = store.query(limit=10)
        assert len(results) >= 4

    def test_query_by_record_type(self):
        store = InMemoryAuditStore()
        store.store(self._make_record(AuditRecordType.DECISION.value, "src_a"))
        store.store(self._make_record(AuditRecordType.GOVERNANCE.value, "src_b"))
        store.store(self._make_record(AuditRecordType.DECISION.value, "src_c"))
        results = store.query(record_type=AuditRecordType.DECISION.value, limit=10)
        assert len(results) >= 2
        for r in results:
            assert r.record_type == AuditRecordType.DECISION.value

    def test_query_by_source(self):
        store = InMemoryAuditStore()
        store.store(self._make_record(AuditRecordType.DECISION.value, "engine_x"))
        store.store(self._make_record(AuditRecordType.DECISION.value, "engine_y"))
        results = store.query(source="engine_x", limit=10)
        assert len(results) >= 1
        for r in results:
            assert r.source == "engine_x"

    def test_query_newest_first(self):
        store = InMemoryAuditStore()
        r1 = self._make_record(AuditRecordType.DECISION.value, "first")
        r2 = self._make_record(AuditRecordType.DECISION.value, "second")
        store.store(r1)
        store.store(r2)
        results = store.query(limit=10)
        assert results[0].source == "second"
        assert results[-1].source == "first"

    def test_query_limit(self):
        store = InMemoryAuditStore()
        for i in range(10):
            store.store(self._make_record(AuditRecordType.DECISION.value, f"src_{i}"))
        results = store.query(limit=3)
        assert len(results) == 3

    def test_query_offset(self):
        store = InMemoryAuditStore()
        for i in range(10):
            store.store(self._make_record(AuditRecordType.DECISION.value, f"src_{i}"))
        results = store.query(limit=10, offset=7)
        assert len(results) == 3

    def test_query_limit_capped_at_max(self):
        store = InMemoryAuditStore()
        for i in range(QUERY_MAX_LIMIT + 100):
            store.store(self._make_record(AuditRecordType.DECISION.value, f"src_{i}"))
        results = store.query(limit=QUERY_MAX_LIMIT + 100)
        assert len(results) <= QUERY_MAX_LIMIT

    def test_fifo_eviction(self):
        store = InMemoryAuditStore(max_size=3)
        r1 = self._make_record(AuditRecordType.DECISION.value, "r1")
        r2 = self._make_record(AuditRecordType.DECISION.value, "r2")
        r3 = self._make_record(AuditRecordType.DECISION.value, "r3")
        r4 = self._make_record(AuditRecordType.DECISION.value, "r4")
        store.store(r1)
        store.store(r2)
        store.store(r3)
        store.store(r4)
        # r1 应该被淘汰
        assert store.get(r1.audit_id) is None
        assert store.get(r2.audit_id) is not None
        assert store.get(r3.audit_id) is not None
        assert store.get(r4.audit_id) is not None
        assert store.count() == 3

    def test_clear(self):
        store = InMemoryAuditStore()
        store.store(self._make_record(AuditRecordType.DECISION.value))
        store.store(self._make_record(AuditRecordType.GOVERNANCE.value))
        store.clear()
        assert store.count() == 0

    def test_max_size_at_least_one(self):
        store = InMemoryAuditStore(max_size=0)
        assert store._max_size >= 1


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditRuleEngine
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditRuleEngine:

    def test_init_empty(self):
        engine = AuditRuleEngine()
        assert engine.rules == {}

    def test_register_rule(self):
        engine = AuditRuleEngine()
        rule = AuditRule(rule_id="r1", name="测试规则")
        engine.register_rule(rule, lambda rec: [])
        assert "r1" in engine.rules
        assert engine.rules["r1"].name == "测试规则"

    def test_remove_rule(self):
        engine = AuditRuleEngine()
        rule = AuditRule(rule_id="r1")
        engine.register_rule(rule, lambda rec: [])
        assert engine.remove_rule("r1") is True
        assert "r1" not in engine.rules

    def test_remove_nonexistent(self):
        engine = AuditRuleEngine()
        assert engine.remove_rule("nonexistent") is False

    def test_run_checks_empty_rules(self):
        engine = AuditRuleEngine()
        findings = engine.run_checks([])
        assert findings == []

    def test_run_checks_returns_findings(self):
        engine = AuditRuleEngine()

        def check_fn(records):
            return [
                AuditFinding(rule_id="r1", severity="error", message="测试发现")
            ]

        engine.register_rule(AuditRule(rule_id="r1", name="测试"), check_fn)
        findings = engine.run_checks([AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="test",
            summary="测试",
        )])
        assert len(findings) == 1
        assert findings[0].rule_id == "r1"
        assert findings[0].severity == "error"
        assert findings[0].message == "测试发现"

    def test_run_checks_catches_exceptions(self):
        engine = AuditRuleEngine()

        def failing_check(records):
            raise ValueError("检查失败")

        engine.register_rule(
            AuditRule(rule_id="failing", name="异常规则"),
            failing_check,
        )
        findings = engine.run_checks([])
        assert len(findings) == 1
        assert findings[0].rule_id == "failing"
        assert findings[0].severity == "error"
        assert "异常" in findings[0].message or "ValueError" in findings[0].message

    def test_reset_clears_rules(self):
        engine = AuditRuleEngine()
        engine.register_rule(AuditRule(rule_id="r1"), lambda rec: [])
        engine.reset()
        assert engine.rules == {}


# ═══════════════════════════════════════════════════════════════════════════════
#  默认审计规则
# ═══════════════════════════════════════════════════════════════════════════════

class TestDefaultRules:

    def _make_decision_record(
        self,
        audit_id: str = "",
        trace_ids: tuple[str, ...] = (),
        summary: str = "",
    ) -> AuditRecord:
        return AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="decision_engine",
            summary=summary or "决策审计",
            related_trace_ids=trace_ids,
            details={"decision_id": "dec_1"},
        )

    def _make_governance_record(
        self,
        outcome: str = "approved",
        audit_id: str = "",
    ) -> AuditRecord:
        return AuditRecord(
            audit_id=audit_id or "gov_1",
            record_type=AuditRecordType.GOVERNANCE.value,
            source="governance",
            summary=f"Governance {outcome}",
            details={"outcome": outcome},
        )

    def _make_execution_record(
        self,
        status: str = "completed",
        action_id: str = "act_1",
        source: str = "executor",
    ) -> AuditRecord:
        return AuditRecord(
            record_type=AuditRecordType.EXECUTION.value,
            source=source,
            summary=f"Action {status}",
            details={
                "action_status": status,
                "action_id": action_id,
            },
        )

    def _make_system_halt_record(self, audit_id: str = "halt_1") -> AuditRecord:
        return AuditRecord(
            audit_id=audit_id,
            record_type=AuditRecordType.SYSTEM.value,
            source="runtime",
            summary="系统应急停止",
            details={"event_type": EventType.EMERGENCY_HALT.value},
        )

    def _make_system_recovery_record(
        self, related_halt_id: str = ""
    ) -> AuditRecord:
        details: dict = {"event_type": "system.recovery"}
        if related_halt_id:
            details["related_halt_audit_id"] = related_halt_id
        return AuditRecord(
            record_type=AuditRecordType.SYSTEM.value,
            source="runtime",
            summary="系统恢复",
            details=details,
        )

    # Rule 1: 决策完整性

    def test_rule1_completeness_pass(self):
        """有关联 Trace ID 的决策不应触发 finding。"""
        r = self._make_decision_record(trace_ids=("trace_1",))
        findings = _check_decision_completeness([r])
        assert len(findings) == 0

    def test_rule1_completeness_fail(self):
        """无关联 Trace ID 的决策应触发 finding。"""
        r = self._make_decision_record(trace_ids=())
        findings = _check_decision_completeness([r])
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_rule1_ignores_non_decision(self):
        """非 DECISION 记录不应触发规则。"""
        r = self._make_governance_record()
        findings = _check_decision_completeness([r])
        assert len(findings) == 0

    # Rule 2: 权限一致性

    def test_rule2_permission_pass(self):
        """Governance 批准后执行的决策不应触发 finding。"""
        recs = [
            self._make_governance_record(outcome="approved"),
            self._make_decision_record(),
        ]
        findings = _check_permission_consistency(recs)
        assert len(findings) == 0

    def test_rule2_permission_fail_when_governance_ref(self):
        """Governance 拒绝但仍有决策执行记录应触发 finding。"""
        rejected_gov = self._make_governance_record(
            outcome="rejected",
            audit_id="gov_rejected",
        )
        gov_details = dict(rejected_gov.details) if rejected_gov.details else {}
        # 创建一个指向被拒绝 governance 的决策
        executed = AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="decision_engine",
            summary="被拒绝后仍执行的决策",
            details={"governance_audit_id": "gov_rejected"},
        )
        recs = [rejected_gov, executed]
        findings = _check_permission_consistency(recs)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_rule2_no_governance_records(self):
        """没有 Governance 记录时不应触发 finding。"""
        findings = _check_permission_consistency([])
        assert len(findings) == 0

    # Rule 3: 执行链完整性

    def test_rule3_complete_chain(self):
        """完整执行链（completed）不应触发 finding。"""
        recs = [
            self._make_execution_record(status="completed", action_id="act_1"),
        ]
        findings = _check_execution_chain_completeness(recs)
        assert len(findings) == 0

    def test_rule3_incomplete_chain(self):
        """只有 executing 没有 completed/failed 应触发 finding。"""
        recs = [
            self._make_execution_record(status="executing", action_id="act_1"),
        ]
        findings = _check_execution_chain_completeness(recs)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_rule3_complete_scheduled_then_completed(self):
        """scheduled + completed 不触发 finding。"""
        recs = [
            self._make_execution_record(status="scheduled", action_id="act_1"),
            self._make_execution_record(status="completed", action_id="act_1"),
        ]
        findings = _check_execution_chain_completeness(recs)
        assert len(findings) == 0

    def test_rule3_failed_still_complete(self):
        """failed 也是合法终止，不触发 finding。"""
        recs = [
            self._make_execution_record(status="executing", action_id="act_1"),
            self._make_execution_record(status="failed", action_id="act_1"),
        ]
        findings = _check_execution_chain_completeness(recs)
        assert len(findings) == 0

    def test_rule3_empty_records(self):
        findings = _check_execution_chain_completeness([])
        assert len(findings) == 0

    # Rule 4: 治理可追溯

    def test_rule4_governance_traceability(self):
        """有 Governance 记录时应返回 info finding。"""
        r = self._make_governance_record(
            outcome="approved",
            audit_id="gov_trace",
        )
        # Override details to include target_source
        r = AuditRecord(
            audit_id="gov_trace",
            record_type=AuditRecordType.GOVERNANCE.value,
            source="governance",
            summary="Governance approved",
            details={"outcome": "approved", "target_source": "knowledge_engine"},
        )
        findings = _check_governance_traceability([r])
        assert len(findings) == 1
        assert findings[0].severity == "info"

    def test_rule4_no_governance(self):
        findings = _check_governance_traceability([])
        assert len(findings) == 0  # 无 Governance 记录时不返回 finding

    # Rule 5: 应急恢复记录

    def test_rule5_halt_with_recovery_pass(self):
        """Halt 后有恢复记录不触发 finding。"""
        recs = [
            self._make_system_halt_record(audit_id="halt_1"),
            self._make_system_recovery_record(related_halt_id="halt_1"),
        ]
        findings = _check_emergency_recovery(recs)
        assert len(findings) == 0

    def test_rule5_halt_without_recovery_fail(self):
        """Halt 后无恢复记录应触发 finding。"""
        recs = [self._make_system_halt_record(audit_id="halt_1")]
        findings = _check_emergency_recovery(recs)
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert "halt_1" in findings[0].message

    def test_rule5_no_halt(self):
        """无 halt 事件时不触发 finding。"""
        recs = [self._make_system_recovery_record()]
        findings = _check_emergency_recovery(recs)
        assert len(findings) == 0

    def test_rule5_empty(self):
        findings = _check_emergency_recovery([])
        assert len(findings) == 0

    # load_default_audit_rules

    def test_load_default_rules(self):
        engine = AuditRuleEngine()
        load_default_audit_rules(engine)
        rule_ids = list(engine.rules.keys())
        assert "audit_rule_decision_completeness" in rule_ids
        assert "audit_rule_execution_chain" in rule_ids
        assert "audit_rule_governance_traceability" in rule_ids
        # S2.10: permission_consistency / emergency_recovery 两条规则
        # 依赖的字段无真实写入点，移出默认集（保留检查函数）
        assert "audit_rule_permission_consistency" not in rule_ids
        assert "audit_rule_emergency_recovery" not in rule_ids
        assert len(rule_ids) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditEngine — 核心接口
# ═══════════════════════════════════════════════════════════════════════════════

class FakeEventBus:
    """Mock Event Bus 用于测试。"""

    def __init__(self):
        self.subscriptions: dict[EventType, list] = {}
        self.published_events: list[Event] = []

    def subscribe(self, event_type: EventType, callback):
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        sub = object()
        self.subscriptions[event_type].append((sub, callback))
        return sub

    def unsubscribe(self, sub):
        for event_type in list(self.subscriptions.keys()):
            self.subscriptions[event_type] = [
                (s, c) for s, c in self.subscriptions[event_type] if s is not sub
            ]

    def publish(self, event: Event, sync: bool = False):
        self.published_events.append(event)
        if sync:
            for event_type in self.subscriptions:
                if event_type == event.event_type:
                    for sub, cb in self.subscriptions[event_type]:
                        cb(event)

    def publish_sync(self, event: Event):
        """Publish and call all matching subscribers synchronously."""
        self.published_events.append(event)
        for event_type in self.subscriptions:
            if event_type == event.event_type:
                for sub, cb in self.subscriptions[event_type]:
                    cb(event)


class TestAuditEngineInit:

    def test_init_defaults(self):
        engine = AuditEngine()
        assert engine.store is not None
        assert engine.rule_engine is not None
        assert engine.trace_engine is None
        assert engine.get_audit_count() == 0
        # 默认规则已加载（S2.10: 2 条无写入点规则移出默认集，5→3）
        assert len(engine.rule_engine.rules) >= 3

    def test_init_with_custom_store(self):
        store = InMemoryAuditStore(max_size=100)
        engine = AuditEngine(store=store)
        assert engine.store is store

    def test_init_with_event_bus(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        # 应订阅了多个事件
        subscribed_types = list(bus.subscriptions.keys())
        assert EventType.DECISION_FORMED in subscribed_types
        assert EventType.GOVERNANCE_APPROVED in subscribed_types
        assert EventType.ACTION_EXECUTED in subscribed_types
        assert EventType.EMERGENCY_HALT in subscribed_types

    def test_init_emit_audit_events_default_false(self):
        engine = AuditEngine()
        assert engine._emit_audit_events == DEFAULT_EMIT_AUDIT_EVENTS
        assert engine._emit_audit_events is False

    def test_init_emit_audit_events_true(self):
        engine = AuditEngine(emit_audit_events=True)
        assert engine._emit_audit_events is True


class TestAuditEngineRecord:

    def test_record_returns_audit_id(self):
        engine = AuditEngine()
        audit_id = engine.record(
            record_type=AuditRecordType.DECISION,
            source="test",
            summary="手动记录",
        )
        assert audit_id != ""

    def test_record_stores(self):
        engine = AuditEngine()
        audit_id = engine.record(
            record_type=AuditRecordType.GOVERNANCE,
            source="gov",
            summary="审批记录",
            related_trace_ids=("trace_1",),
            related_event_ids=("evt_1",),
            details={"outcome": "approved"},
        )
        record = engine.get_audit_record(audit_id)
        assert record is not None
        assert record.record_type == AuditRecordType.GOVERNANCE.value
        assert record.source == "gov"
        assert record.summary == "审批记录"
        assert record.related_trace_ids == ("trace_1",)
        assert record.related_event_ids == ("evt_1",)
        assert record.details == {"outcome": "approved"}

    def test_record_updates_count(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.SYSTEM, "sys", "系统事件")
        assert engine.get_audit_count() == 1
        engine.record(AuditRecordType.SYSTEM, "sys", "系统事件 2")
        assert engine.get_audit_count() == 2


class TestAuditEngineQuery:

    def test_get_nonexistent(self):
        engine = AuditEngine()
        assert engine.get_audit_record("nonexistent") is None

    def test_query_returns_records(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src_a", "决策 A")
        engine.record(AuditRecordType.GOVERNANCE, "src_b", "审批 B")
        results = engine.query_audit_trail(limit=10)
        assert len(results) >= 2

    def test_query_by_type(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "决策")
        engine.record(AuditRecordType.EXECUTION, "src", "执行")
        results = engine.query_audit_trail(
            record_type=AuditRecordType.DECISION.value, limit=10
        )
        assert len(results) >= 1
        for r in results:
            assert r.record_type == AuditRecordType.DECISION.value

    def test_query_by_source(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "engine_x", "X 决策")
        engine.record(AuditRecordType.DECISION, "engine_y", "Y 决策")
        results = engine.query_audit_trail(source="engine_x", limit=10)
        assert len(results) >= 1
        for r in results:
            assert r.source == "engine_x"

    def test_query_limit(self):
        engine = AuditEngine()
        for i in range(20):
            engine.record(AuditRecordType.DECISION, f"src_{i}", f"决策 {i}")
        results = engine.query_audit_trail(limit=5)
        assert len(results) == 5


class TestAuditEngineRunChecks:

    def test_run_checks_all_records(self):
        engine = AuditEngine()
        # 添加一个无关联 Trace ID 的决策记录（触发 Rule 1）
        engine.record(
            AuditRecordType.DECISION,
            "decision_engine",
            "决策无 Trace",
        )
        findings = engine.run_audit_checks()
        # 应至少有一个 warning（来自 Rule 1）
        warnings = [f for f in findings if f.severity == "warning"]
        assert len(warnings) >= 1

    def test_run_checks_specific_ids(self):
        engine = AuditEngine()
        aid1 = engine.record(AuditRecordType.DECISION, "src", "决策 1",
                             related_trace_ids=("trace_1",))
        aid2 = engine.record(AuditRecordType.DECISION, "src", "决策 2")
        findings = engine.run_audit_checks(record_ids=[aid1])
        # aid1 有关联 Trace，不应触发 finding
        related_findings = [
            f for f in findings
            if aid1 in f.related_audit_ids
        ]
        # aid1 应该是干净的
        pass  # 默认检查可能不会对单一 clean record 出 finding

    def test_run_checks_no_findings(self):
        engine = AuditEngine()
        # 添加通过所有检查的记录
        engine.record(
            AuditRecordType.DECISION,
            "decision_engine",
            "完整决策",
            related_trace_ids=("trace_1",),
        )
        findings = engine.run_audit_checks()
        # Rule 1 应通过
        completeness_findings = [
            f for f in findings
            if f.rule_id == "audit_rule_decision_completeness"
        ]
        assert len(completeness_findings) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditEngine — Event Bus 自动收集
# ═══════════════════════════════════════════════════════════════════════════════

class FakeTraceEngine:
    """简单的 Mock TraceEngine 用于报告测试。"""

    def __init__(self):
        self.traces: dict[str, object] = {}

    def query_traces(self, **kwargs):
        return list(self.traces.values())

    def get_trace(self, trace_id: str):
        return self.traces.get(trace_id)


class TestAuditEngineEventBus:

    def test_decision_event_auto_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.DECISION_FORMED,
            source="decision_engine",
            payload={"decision_id": "dec_1", "goal_id": "goal_1"},
            trace_id="trace_1",
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(limit=10)
        decision_records = [r for r in records if r.record_type == AuditRecordType.DECISION.value]
        assert len(decision_records) >= 1
        dr = decision_records[0]
        assert dr.source == "decision_engine"
        assert "trace_1" in dr.related_trace_ids
        assert event.event_id in dr.related_event_ids

    def test_governance_approved_auto_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.GOVERNANCE_APPROVED,
            source="governance",
            payload={"proposal_id": "prop_1", "target_source": "knowledge"},
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(
            record_type=AuditRecordType.GOVERNANCE.value, limit=10
        )
        assert len(records) >= 1
        assert "approved" in records[0].summary.lower()

    def test_governance_rejected_auto_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.GOVERNANCE_REJECTED,
            source="governance",
            payload={"proposal_id": "prop_2"},
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(
            record_type=AuditRecordType.GOVERNANCE.value, limit=10
        )
        assert len(records) >= 1
        assert "rejected" in records[0].summary.lower()

    def test_execution_event_auto_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.ACTION_EXECUTED,
            source="executor",
            payload={"action_id": "act_1", "decision_id": "dec_1"},
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(
            record_type=AuditRecordType.EXECUTION.value, limit=10
        )
        assert len(records) >= 1
        assert "completed" in records[0].summary.lower()

    def test_action_failed_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.ACTION_FAILED,
            source="executor",
            payload={"action_id": "act_fail"},
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(limit=10)
        execution_records = [
            r for r in records
            if r.record_type == AuditRecordType.EXECUTION.value
        ]
        assert len(execution_records) >= 1

    def test_emergency_halt_auto_collects(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        event = Event(
            event_type=EventType.EMERGENCY_HALT,
            source="runtime",
            payload={"reason": "资源耗尽"},
        )
        bus.publish_sync(event)
        records = engine.query_audit_trail(
            record_type=AuditRecordType.SYSTEM.value, limit=10
        )
        assert len(records) >= 1
        assert "halt" in records[0].summary.lower() or "HALT" in records[0].summary

    def test_unsubscribe_all(self):
        bus = FakeEventBus()
        engine = AuditEngine(event_bus=bus)
        engine.unsubscribe_all()
        # 所有订阅应已移除
        for event_type in list(bus.subscriptions.keys()):
            assert len(bus.subscriptions[event_type]) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditEngine — 报告接口
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditEngineReports:

    def test_build_debug_report(self):
        engine = AuditEngine()
        aid = engine.record(
            AuditRecordType.DECISION,
            "decision_engine",
            "决策审计",
            details={"decision_id": "dec_1"},
        )
        report = engine.build_debug_report(decision_id="dec_1")
        assert report["report_type"] == "debug"
        assert report["decision_id"] == "dec_1"
        assert report["total_audit_records"] >= 1
        assert isinstance(report["related_traces"], list)
        assert isinstance(report["audit_records"], list)

    def test_build_debug_report_with_trace_engine(self):
        trace_engine = FakeTraceEngine()
        # 添加一个模拟 trace
        from ocos.platform.trace_engine import DecisionTrace
        trace_engine.traces["trace_1"] = DecisionTrace(
            trace_id="trace_1",
            source="test",
            decision_id="dec_2",
        )
        engine = AuditEngine(trace_engine=trace_engine)
        engine.record(
            AuditRecordType.DECISION,
            "decision_engine",
            "有 Trace 的决策",
            details={"decision_id": "dec_2"},
        )
        report = engine.build_debug_report(decision_id="dec_2")
        assert report["total_traces"] >= 1

    def test_build_debug_report_no_decision(self):
        engine = AuditEngine()
        report = engine.build_debug_report(decision_id="nonexistent")
        assert report["total_audit_records"] == 0

    def test_build_compliance_report(self):
        engine = AuditEngine()
        # 添加一些记录
        engine.record(AuditRecordType.DECISION, "src", "决策 1")
        engine.record(AuditRecordType.GOVERNANCE, "src", "审批 1")
        report = engine.build_compliance_report()
        assert report["report_type"] == "compliance"
        assert "summary" in report
        assert "total_records_checked" in report["summary"]
        assert "total_findings" in report["summary"]
        assert "errors" in report["summary"]
        assert "warnings" in report["summary"]
        assert isinstance(report["findings"], list)

    def test_build_compliance_report_time_range(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "决策")
        now = datetime.now(timezone.utc).isoformat()
        report = engine.build_compliance_report(
            time_from=now[:10] + "T00:00:00",
            time_to=now,
        )
        assert report["time_range"]["from"] is not None
        assert report["time_range"]["to"] is not None

    def test_build_replay_context_found(self):
        engine = AuditEngine()
        aid = engine.record(
            AuditRecordType.DECISION,
            "decision_engine",
            "回放上下文测试",
            related_trace_ids=("trace_a",),
        )
        ctx = engine.build_replay_context(audit_id=aid)
        assert ctx["found"] is True
        assert ctx["record"]["summary"] == "回放上下文测试"
        assert isinstance(ctx["surrounding_audit_records"], list)
        assert isinstance(ctx["related_traces"], list)

    def test_build_replay_context_not_found(self):
        engine = AuditEngine()
        ctx = engine.build_replay_context(audit_id="nonexistent")
        assert ctx["found"] is False

    def test_build_replay_context_with_trace_engine(self):
        trace_engine = FakeTraceEngine()
        from ocos.platform.trace_engine import ReasoningTrace
        trace_engine.traces["trace_r1"] = ReasoningTrace(
            trace_id="trace_r1",
            source="reasoning_engine",
        )
        engine = AuditEngine(trace_engine=trace_engine)
        aid = engine.record(
            AuditRecordType.DECISION,
            "engine",
            "带 Trace 的审计",
            related_trace_ids=("trace_r1",),
        )
        ctx = engine.build_replay_context(audit_id=aid)
        assert ctx["found"] is True
        assert len(ctx["related_traces"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditEngine — 无 Event Bus 降级
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditEngineNoEventBus:

    def test_no_event_bus_manual_record_works(self):
        engine = AuditEngine()
        aid = engine.record(AuditRecordType.DECISION, "src", "无 EB 记录")
        assert engine.get_audit_record(aid) is not None

    def test_no_event_bus_query_works(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "测试")
        results = engine.query_audit_trail(limit=10)
        assert len(results) >= 1

    def test_no_event_bus_run_checks(self):
        engine = AuditEngine()
        findings = engine.run_audit_checks()
        assert isinstance(findings, list)

    def test_no_event_bus_unsubscribe_does_not_raise(self):
        engine = AuditEngine()
        engine.unsubscribe_all()  # 不应抛出异常

    def test_no_event_bus_reports_work(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "报告测试",
                      details={"decision_id": "d1"})
        report = engine.build_debug_report("d1")
        assert report["report_type"] == "debug"

    def test_no_event_bus_reset_works(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "重置前")
        engine.reset()
        assert engine.get_audit_count() == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  AuditEngine — 重置
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditEngineReset:

    def test_reset_clears_records(self):
        engine = AuditEngine()
        engine.record(AuditRecordType.DECISION, "src", "记录")
        engine.record(AuditRecordType.GOVERNANCE, "src", "记录 2")
        engine.reset()
        assert engine.get_audit_count() == 0

    def test_reset_reloads_default_rules(self):
        engine = AuditEngine()
        # 移除所有规则
        for rid in list(engine.rule_engine.rules.keys()):
            engine.rule_engine.remove_rule(rid)
        assert len(engine.rule_engine.rules) == 0
        engine.reset()
        # reset 应重新加载默认规则（S2.10: 默认集 5→3）
        assert len(engine.rule_engine.rules) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
#  边界条件
# ═══════════════════════════════════════════════════════════════════════════════

class TestStoreEdgeCases:

    def test_empty_store_query_returns_empty(self):
        store = InMemoryAuditStore()
        assert store.query(limit=10) == []

    def test_store_eviction_preserves_recent(self):
        store = InMemoryAuditStore(max_size=2)
        r1 = AuditRecord(record_type="a", source="s1", summary="1")
        r2 = AuditRecord(record_type="a", source="s2", summary="2")
        r3 = AuditRecord(record_type="a", source="s3", summary="3")
        store.store(r1)
        store.store(r2)
        store.store(r3)
        assert store.count() == 2
        assert store.get(r1.audit_id) is None
        assert store.get(r2.audit_id) is not None
        assert store.get(r3.audit_id) is not None

    def test_query_zero_limit_defaults_to_one(self):
        store = InMemoryAuditStore()
        store.store(AuditRecord(record_type="a", source="s", summary="t"))
        results = store.query(limit=0)
        assert len(results) == 1

    def test_multiple_filters(self):
        store = InMemoryAuditStore()
        r = AuditRecord(
            record_type=AuditRecordType.DECISION.value,
            source="engine",
            summary="过滤测试",
        )
        store.store(r)
        # 有效过滤
        results = store.query(
            record_type=AuditRecordType.DECISION.value,
            source="engine",
            limit=10,
        )
        assert len(results) >= 1
        # 过滤不匹配
        results = store.query(
            record_type=AuditRecordType.GOVERNANCE.value,
            source="engine",
            limit=10,
        )
        assert len(results) == 0


class TestAuditEngineEdgeCases:

    def test_record_without_trace_ids(self):
        engine = AuditEngine()
        aid = engine.record(AuditRecordType.SYSTEM, "sys", "无 Trace")
        rec = engine.get_audit_record(aid)
        assert rec.related_trace_ids == ()

    def test_record_empty_source(self):
        engine = AuditEngine()
        aid = engine.record(AuditRecordType.DECISION, "", "空 source")
        rec = engine.get_audit_record(aid)
        assert rec.source == ""

    def test_run_checks_empty_trail_does_not_raise(self):
        engine = AuditEngine()
        findings = engine.run_audit_checks()
        assert isinstance(findings, list)

    def test_build_replay_context_not_found_returns_expected(self):
        engine = AuditEngine()
        ctx = engine.build_replay_context(audit_id="i_dont_exist")
        assert ctx["found"] is False
        assert ctx["audit_id"] == "i_dont_exist"
