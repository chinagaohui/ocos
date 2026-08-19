"""审计报告生成器 — C2 Audit Engine 的报告层。

包含 AuditReportGenerator，提供：
- build_debug_report: 决策级 Debug 报告
- build_compliance_report: 合规报告（运行审计规则检查）
- build_replay_context: Replay 上下文

从 platform/audit_engine.py 提取（v1.0 拆分）。
"""

from __future__ import annotations

from typing import Any, Optional

from ocos.platform.audit_models import AuditRecord, QUERY_MAX_LIMIT


class AuditReportGenerator:
    """审计报告生成器。

    独立于 AuditEngine，接收 store / trace_engine / rule_engine 作为依赖。
    """

    def __init__(
        self,
        store: Any,
        trace_engine: Any = None,
        rule_engine: Any = None,
    ):
        self._store = store
        self._trace_engine = trace_engine
        self._rule_engine = rule_engine

    def build_debug_report(self, decision_id: str) -> dict[str, Any]:
        """构建决策级 Debug 报告。

        收集指定 decision_id 相关的所有 AuditRecord + 关联的 Trace 信息。

        Args:
            decision_id: 目标决策 ID

        Returns:
            结构化 dict 报告
        """
        all_records = self._store.query(limit=QUERY_MAX_LIMIT)
        related_audit_records: list[AuditRecord] = []
        traces_from_engine: list[dict[str, Any]] = []

        for r in all_records:
            details = r.details or {}
            if details.get("decision_id") == decision_id:
                related_audit_records.append(r)

            if self._trace_engine is not None:
                traces = self._trace_engine.query_traces(
                    decision_id=decision_id,
                    limit=50,
                )
                traces_from_engine = [
                    {
                        "trace_id": t.trace_id,
                        "trace_type": t.trace_type.value,
                        "source": t.source,
                        "timestamp": t.timestamp,
                    }
                    for t in traces
                ]

        return {
            "report_type": "debug",
            "decision_id": decision_id,
            "audit_records": [
                {
                    "audit_id": r.audit_id,
                    "record_type": r.record_type,
                    "source": r.source,
                    "summary": r.summary,
                    "timestamp": r.timestamp,
                }
                for r in related_audit_records
            ],
            "related_traces": traces_from_engine,
            "total_audit_records": len(related_audit_records),
            "total_traces": len(traces_from_engine),
        }

    def build_compliance_report(
        self,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
    ) -> dict[str, Any]:
        """构建合规报告。

        在指定时间范围内运行所有审计规则检查，汇总 Findings。

        Args:
            time_from: 起始时间（ISO）
            time_to: 结束时间（ISO）

        Returns:
            结构化 dict 报告
        """
        records = self._store.query(
            time_from=time_from,
            time_to=time_to,
            limit=QUERY_MAX_LIMIT,
        )
        findings = self._rule_engine.run_checks(records) if self._rule_engine else []

        errors = [f for f in findings if f.severity == "error"]
        warnings_list = [f for f in findings if f.severity == "warning"]
        infos = [f for f in findings if f.severity == "info"]

        return {
            "report_type": "compliance",
            "time_range": {
                "from": time_from,
                "to": time_to,
            },
            "summary": {
                "total_records_checked": len(records),
                "total_findings": len(findings),
                "errors": len(errors),
                "warnings": len(warnings_list),
                "infos": len(infos),
                "compliant": len(errors) == 0,
            },
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "message": f.message,
                    "timestamp": f.timestamp,
                }
                for f in findings
            ],
        }

    def build_replay_context(self, audit_id: str) -> dict[str, Any]:
        """构建 Replay 上下文。

        从指定的审计记录出发，收集关联的 Trace 和事件信息，
        用于回放或审计追溯。

        Args:
            audit_id: 审计记录 ID

        Returns:
            结构化 dict 报告
        """
        record = self._store.get(audit_id)
        if record is None:
            return {"report_type": "replay", "audit_id": audit_id, "found": False}

        related_traces: list[dict[str, Any]] = []
        if self._trace_engine is not None:
            for tid in record.related_trace_ids:
                trace = self._trace_engine.get_trace(tid)
                if trace is not None:
                    related_traces.append({
                        "trace_id": trace.trace_id,
                        "trace_type": trace.trace_type.value,
                        "source": trace.source,
                        "timestamp": trace.timestamp,
                    })

        all_records = self._store.query(limit=QUERY_MAX_LIMIT)
        surrounding_records: list[dict[str, Any]] = []
        found_idx = -1
        for i, r in enumerate(all_records):
            if r.audit_id == audit_id:
                found_idx = i
                break
        if found_idx >= 0:
            start = max(0, found_idx - 3)
            end = min(len(all_records), found_idx + 4)
            for r in all_records[start:end]:
                surrounding_records.append({
                    "audit_id": r.audit_id,
                    "record_type": r.record_type,
                    "summary": r.summary,
                    "timestamp": r.timestamp,
                })

        return {
            "report_type": "replay",
            "audit_id": audit_id,
            "found": True,
            "record": {
                "record_type": record.record_type,
                "source": record.source,
                "summary": record.summary,
                "timestamp": record.timestamp,
                "details": record.details,
            },
            "related_traces": related_traces,
            "surrounding_audit_records": surrounding_records,
            "total_surrounding": len(surrounding_records),
        }
