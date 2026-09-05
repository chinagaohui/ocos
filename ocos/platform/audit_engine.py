"""C2 Audit Engine — 平台层统一审计入口（v1.0 拆分版）。

职责：
- 自动收集审计事件（通过 Event Bus 订阅 Decision/Governance/Execution/System 事件）
- 审计规则检查（完整性 / 权限越界 / 合规）
- 统一入口：Debug / Compliance / Replay 全部通过 Audit Engine
- C1 TraceEngine 是内部数据源，外部只通过 Audit Engine 查询审计信息

架构定位：
  Audit Engine 是平台的审计统一入口，不是 Trace Engine 的替代。
  Trace Engine (C1) 负责记录可解释性 Trace；
  Audit Engine (C2) 负责将这些 Trace 与 Event 自动关联，
  运行审计规则，产出合规报告。

v1.0 拆分说明：
  本文件保留 AuditEngine 主类 + InMemoryAuditStore。
  数据模型 → audit_models.py
  规则引擎 → audit_rule_engine.py
  报告生成 → audit_report.py
"""

from __future__ import annotations

from typing import Any, Optional

from ocos.kernel.abi import Event, EventType
from ocos.platform.audit_models import (
    DEFAULT_AUDIT_STORE_SIZE,
    DEFAULT_EMIT_AUDIT_EVENTS,
    QUERY_DEFAULT_LIMIT,
    QUERY_MAX_LIMIT,
    AuditFinding,
    AuditRecord,
    AuditRecordType,
    AuditRule,
    CheckFn,
)
from ocos.platform.audit_rule_engine import (
    AuditRuleEngine,
    DEFAULT_AUDIT_RULES,
    _check_decision_completeness,
    _check_emergency_recovery,
    _check_execution_chain_completeness,
    _check_governance_traceability,
    _check_permission_consistency,
    load_default_audit_rules,
)
from ocos.platform.audit_report import AuditReportGenerator
from ocos.logging import get_logger

# ── 重新导出（向后兼容） ──────────────────────────────────────────────────────

__all__ = [
    "DEFAULT_AUDIT_STORE_SIZE",
    "DEFAULT_EMIT_AUDIT_EVENTS",
    "QUERY_DEFAULT_LIMIT",
    "QUERY_MAX_LIMIT",
    "AuditEngine",
    "AuditEngine",
    "AuditFinding",
    "AuditRecord",
    "AuditRecordType",
    "AuditRule",
    "AuditRuleEngine",
    "InMemoryAuditStore",
    "load_default_audit_rules",
    "_check_decision_completeness",
    "_check_permission_consistency",
    "_check_execution_chain_completeness",
    "_check_governance_traceability",
    "_check_emergency_recovery",
]


logger = get_logger(__name__)


# ── 存储 ────────────────────────────────────────────────────────────────────

class InMemoryAuditStore:
    """内存审计记录存储。

    - 环形缓冲区，max_size 可配置（默认 10,000）
    - FIFO 淘汰：超上限时移除最旧记录
    - 按 record_type / source / time_range 过滤查询
    """

    def __init__(self, max_size: int = DEFAULT_AUDIT_STORE_SIZE):
        self._max_size = max(max_size, 1)
        self._records: dict[str, AuditRecord] = {}
        self._order: list[str] = []
        logger.debug("InMemoryAuditStore __init__ completed", component="audit_engine", max_size=self._max_size)

    def store(self, record: AuditRecord) -> None:
        """写入一条审计记录。超过上限时淘汰最旧记录。"""
        if len(self._order) >= self._max_size:
            oldest_id = self._order.pop(0)
            self._records.pop(oldest_id, None)
        self._records[record.audit_id] = record
        self._order.append(record.audit_id)

    def get(self, audit_id: str) -> Optional[AuditRecord]:
        """按 audit_id 查询。"""
        return self._records.get(audit_id)

    def query(
        self,
        record_type: Optional[str] = None,
        source: Optional[str] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = QUERY_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """查询审计记录，按存储顺序逆序（最新优先）。

        Args:
            record_type: 按 AuditRecordType 过滤
            source: 按来源过滤
            time_from: 起始时间（ISO 格式，包含）
            time_to: 结束时间（ISO 格式，包含）
            limit: 最多返回条数（上限 QUERY_MAX_LIMIT）
            offset: 跳过的条数

        Returns:
            匹配的记录列表（最新优先）
        """
        limit = min(max(limit, 1), QUERY_MAX_LIMIT)
        offset = max(offset, 0)

        results: list[AuditRecord] = []
        for rid in reversed(self._order):
            record = self._records[rid]
            if record_type is not None and record.record_type != record_type:
                continue
            if source is not None and record.source != source:
                continue
            if time_from is not None and record.timestamp < time_from:
                continue
            if time_to is not None and record.timestamp > time_to:
                continue
            results.append(record)

        return results[offset:offset + limit]

    def count(self) -> int:
        """当前存储的审计记录总数。"""
        return len(self._order)

    def clear(self) -> None:
        """清空所有审计记录。"""
        self._records.clear()
        self._order.clear()


# ── Audit 引擎 ──────────────────────────────────────────────────────────────

class AuditEngine:
    """审计引擎主入口。

    职责：
    1. 自动收集审计事件（通过 Event Bus 订阅）
    2. 手动记录审计事件
    3. 运行审计规则检查
    4. 构建 Debug / Compliance / Replay 报告
    """

    def __init__(
        self,
        trace_engine: Any = None,
        event_bus: Any = None,
        store: Optional[InMemoryAuditStore] = None,
        rule_engine: Optional[AuditRuleEngine] = None,
        max_size: int = DEFAULT_AUDIT_STORE_SIZE,
        emit_audit_events: bool = DEFAULT_EMIT_AUDIT_EVENTS,
    ):
        self._trace_engine = trace_engine
        self._event_bus = event_bus
        self._store = store or InMemoryAuditStore(max_size=max_size)
        self._rule_engine = rule_engine or AuditRuleEngine()
        self._emit_audit_events = emit_audit_events
        self._report_generator = AuditReportGenerator(
            store=self._store,
            trace_engine=self._trace_engine,
            rule_engine=self._rule_engine,
        )

        # 加载默认规则
        load_default_audit_rules(self._rule_engine)

        # 订阅 Event Bus（如果提供）
        self._subscriptions: list[Any] = []
        if event_bus is not None:
            self._subscribe()

        logger.debug("AuditEngine __init__ completed", component="audit_engine", max_size=max_size, emit_audit_events=emit_audit_events)

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def store(self) -> InMemoryAuditStore:
        """暴露底层存储。"""
        return self._store

    @property
    def rule_engine(self) -> AuditRuleEngine:
        """暴露规则引擎。"""
        return self._rule_engine

    @property
    def trace_engine(self) -> Any:
        """暴露关联的 Trace Engine。"""
        return self._trace_engine

    # ── Event Bus 订阅 ──────────────────────────────────────────────────────

    def _subscribe(self) -> None:
        """订阅关键事件以自动收集审计记录。"""
        if self._event_bus is None:
            return

        # 订阅 Decision 事件
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.DECISION_FORMED, self._on_decision_event
            )
        )
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.DECISION_VALIDATED, self._on_decision_event
            )
        )

        # 订阅 Governance 事件
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.GOVERNANCE_APPROVED, self._on_governance_event
            )
        )
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.GOVERNANCE_REJECTED, self._on_governance_event
            )
        )

        # 订阅 Execution 事件
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.ACTION_EXECUTED, self._on_execution_event
            )
        )
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.ACTION_FAILED, self._on_execution_event
            )
        )

        # 订阅 System 事件
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.EMERGENCY_HALT, self._on_system_event
            )
        )

    # ── Event Bus 回调 ──────────────────────────────────────────────────────

    def _on_decision_event(self, event: Event) -> None:
        """处理决策事件的自动收集回调。"""
        related_trace_ids: tuple[str, ...] = ()
        if event.trace_id:
            related_trace_ids = (event.trace_id,)

        payload = event.payload or {}
        self.record(
            record_type=AuditRecordType.DECISION,
            source=event.source,
            summary=f"决策 {event.event_type.value} — {payload.get('decision_id', '')}",
            related_trace_ids=related_trace_ids,
            related_event_ids=(event.event_id,),
            details={
                "event_type": event.event_type.value,
                "decision_id": payload.get("decision_id", ""),
                "goal_id": payload.get("goal_id", ""),
            },
        )

    def _on_governance_event(self, event: Event) -> None:
        """处理治理事件的自动收集回调。"""
        payload = event.payload or {}
        outcome = "approved" if event.event_type == EventType.GOVERNANCE_APPROVED else "rejected"
        self.record(
            record_type=AuditRecordType.GOVERNANCE,
            source=event.source,
            summary=f"Governance {outcome} — {payload.get('proposal_id', '')}",
            related_trace_ids=(),
            related_event_ids=(event.event_id,),
            details={
                "event_type": event.event_type.value,
                "outcome": outcome,
                "proposal_id": payload.get("proposal_id", ""),
                "target_source": payload.get("target_source", ""),
            },
        )

    def _on_execution_event(self, event: Event) -> None:
        """处理执行事件的自动收集回调。"""
        payload = event.payload or {}
        action_status = (
            "completed" if event.event_type == EventType.ACTION_EXECUTED else "failed"
        )
        self.record(
            record_type=AuditRecordType.EXECUTION,
            source=event.source,
            summary=f"Action {action_status} — {payload.get('action_id', '')}",
            related_trace_ids=(),
            related_event_ids=(event.event_id,),
            details={
                "event_type": event.event_type.value,
                "action_status": action_status,
                "action_id": payload.get("action_id", ""),
                "decision_id": payload.get("decision_id", ""),
            },
        )

    def _on_system_event(self, event: Event) -> None:
        """处理系统事件的自动收集回调。

        S2.10 备注：audit_rule_emergency_recovery 依赖
        details.related_halt_audit_id，其写入点要求 recover/reset 类
        SYSTEM 事件——kernel.abi.EventType 当前不存在此类事件，该规则
        已移出默认集（见 audit_rule_engine.DEFAULT_AUDIT_RULES 注释）。
        未来新增恢复类事件时，需在此回填 related_halt_audit_id。
        """
        payload = event.payload or {}
        self.record(
            record_type=AuditRecordType.SYSTEM,
            source=event.source,
            summary=f"系统事件 {event.event_type.value}",
            related_trace_ids=(),
            related_event_ids=(event.event_id,),
            details={
                "event_type": event.event_type.value,
                "reason": payload.get("reason", ""),
            },
        )

    # ── 手动记录 ────────────────────────────────────────────────────────────

    def record(
        self,
        record_type: AuditRecordType,
        source: str,
        summary: str,
        related_trace_ids: tuple[str, ...] = (),
        related_event_ids: tuple[str, ...] = (),
        details: Optional[dict[str, Any]] = None,
    ) -> str:
        """手动记录一条审计记录。

        Args:
            record_type: 审计记录类型
            source: 来源模块名
            summary: 摘要描述
            related_trace_ids: 关联的 Trace ID 列表
            related_event_ids: 关联的 Event ID 列表
            details: 结构化详情

        Returns:
            新创建的 audit_id
        """
        record = AuditRecord(
            record_type=record_type.value,
            source=source,
            summary=summary,
            related_trace_ids=tuple(related_trace_ids),
            related_event_ids=tuple(related_event_ids),
            details=dict(details or {}),
        )
        self._store.store(record)
        logger.info("Audit record created", component="audit_engine", audit_id=record.audit_id, src=source, record_type=record_type.value)
        return record.audit_id

    # ── 查询接口 ────────────────────────────────────────────────────────────

    def query_audit_trail(
        self,
        record_type: Optional[str] = None,
        source: Optional[str] = None,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: int = QUERY_DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """查询审计轨迹。

        Args:
            record_type: 审计记录类型（AuditRecordType.value）
            source: 来源过滤
            time_from: 起始时间（ISO）
            time_to: 结束时间（ISO）
            limit: 最多返回条数
            offset: 跳过的条数

        Returns:
            匹配的审计记录列表（最新优先）
        """
        logger.info("Querying audit trail", component="audit_engine", record_type=record_type, src=source, limit=limit, offset=offset)
        return self._store.query(
            record_type=record_type,
            source=source,
            time_from=time_from,
            time_to=time_to,
            limit=limit,
            offset=offset,
        )

    def get_audit_record(self, audit_id: str) -> Optional[AuditRecord]:
        """按 audit_id 获取单条审计记录。"""
        return self._store.get(audit_id)

    def get_audit_count(self) -> int:
        """当前存储的审计记录总数。"""
        return self._store.count()

    # ── 审计规则检查 ────────────────────────────────────────────────────────

    def run_audit_checks(
        self,
        record_ids: Optional[list[str]] = None,
    ) -> list[AuditFinding]:
        """运行注册的审计规则检查。

        Args:
            record_ids: 要检查的审计记录 ID 列表。None 表示检查所有记录。

        Returns:
            所有规则的 Finding 列表
        """
        if record_ids is not None:
            records = [
                self._store.get(rid)
                for rid in record_ids
                if self._store.get(rid) is not None
            ]
        else:
            records = self._store.query(limit=QUERY_MAX_LIMIT)

        findings = self._rule_engine.run_checks(records)

        logger.info("Audit checks completed", component="audit_engine", record_count=len(records), finding_count=len(findings))

        # 发射审计事件（可选）
        if self._emit_audit_events and self._event_bus is not None:
            passed_findings = [f for f in findings if f.severity not in ("error", "warning")]
            failed_findings = [f for f in findings if f.severity in ("error", "warning")]

            if failed_findings:
                self._emit_audit_event(
                    EventType.AUDIT_CHECK_FAILED,
                    {"finding_count": len(failed_findings)},
                )
            if passed_findings or not findings:
                self._emit_audit_event(
                    EventType.AUDIT_CHECK_PASSED,
                    {"finding_count": len(passed_findings)},
                )

        return findings

    # ── 报告接口（委托给 AuditReportGenerator） ─────────────────────────────

    def build_debug_report(self, decision_id: str) -> dict[str, Any]:
        """构建决策级 Debug 报告。"""
        logger.info("Building debug report", component="audit_engine", decision_id=decision_id)
        return self._report_generator.build_debug_report(decision_id)

    def build_compliance_report(
        self,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """构建合规报告。"""
        logger.info("Building compliance report", component="audit_engine", time_from=time_from, time_to=time_to)
        return self._report_generator.build_compliance_report(
            time_from=time_from, time_to=time_to
        )

    def build_replay_context(self, audit_id: str) -> dict[str, Any]:
        """构建 Replay 上下文。"""
        logger.info("Building replay context", component="audit_engine", audit_id=audit_id)
        return self._report_generator.build_replay_context(audit_id)

    # ── 管理 ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """清空所有审计记录和 Findings。"""
        logger.info("Resetting audit engine", component="audit_engine")
        self._store.clear()
        self._rule_engine.reset()
        load_default_audit_rules(self._rule_engine)

    def unsubscribe_all(self) -> None:
        """取消所有 Event Bus 订阅。"""
        logger.info("Unsubscribing all event bus subscriptions", component="audit_engine")
        if self._event_bus is None:
            return
        for sub in self._subscriptions:
            try:
                self._event_bus.unsubscribe(sub)
            except Exception as e:
                logger.error("Failed to unsubscribe", component="audit_engine", exception=e)
        self._subscriptions.clear()

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _emit_audit_event(self, event_type: EventType, payload: dict[str, Any]) -> None:
        """发射审计事件。"""
        logger.debug("Emitting audit event", component="audit_engine", event_type=event_type.value, payload=payload)
        if self._event_bus is None:
            return
        event = Event(
            event_type=event_type,
            source="audit_engine",
            payload=payload,
        )
        self._event_bus.publish(event, sync=True)
