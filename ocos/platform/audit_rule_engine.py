"""审计规则引擎 — C2 Audit Engine 的规则执行器与规则注册表。

包含：
- AuditRuleEngine（规则注册/移除/运行/异常处理）
- 5 条默认审计规则的 check 函数
- DEFAULT_AUDIT_RULES 注册表
- load_default_audit_rules() 加载器

从 platform/audit_engine.py 提取（v1.0 拆分）。
"""

from __future__ import annotations

from ocos.kernel.abi import Event, EventType
from ocos.platform.audit_models import (
    AuditFinding,
    AuditRecord,
    AuditRecordType,
    AuditRule,
    CheckFn,
)
from ocos.logging import get_logger


logger = get_logger(__name__)


class AuditRuleEngine:
    """运行审计规则，返回 Findings。

    规则可注册、可禁用，每条规则的检查逻辑封装为独立 Callable。
    """

    def __init__(self):
        self._rules: dict[str, tuple[AuditRule, CheckFn]] = {}
        logger.debug("AuditRuleEngine __init__ completed", component="audit_rule_engine")

    @property
    def rules(self) -> dict[str, AuditRule]:
        """当前注册的规则（只读副本）。"""
        return {k: v[0] for k, v in self._rules.copy().items()}

    def register_rule(self, rule: AuditRule, check_fn: CheckFn) -> None:
        """注册一条审计规则。"""
        self._rules[rule.rule_id] = (rule, check_fn)

    def remove_rule(self, rule_id: str) -> bool:
        """移除一条审计规则。"""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def run_checks(
        self, records: list[AuditRecord]
    ) -> list[AuditFinding]:
        """对所有注册规则运行检查。

        Args:
            records: 待检查的审计记录

        Returns:
            所有规则产出的 Finding 列表
        """
        findings: list[AuditFinding] = []
        logger.info("Running audit checks", component="audit_rule_engine", rule_count=len(self._rules), record_count=len(records))
        for rule_id, (rule, check_fn) in self._rules.items():
            try:
                rule_findings = check_fn(records)
                for f in rule_findings:
                    f = AuditFinding(
                        finding_id=f.finding_id,
                        rule_id=rule.rule_id if f.rule_id == "" else f.rule_id,
                        severity=f.severity,
                        message=f.message,
                        related_audit_ids=f.related_audit_ids,
                        timestamp=f.timestamp,
                    )
                    findings.append(f)
            except Exception as exc:
                logger.error("Audit rule check failed", component="audit_rule_engine", rule_id=rule_id, rule_name=rule.name, exception=exc)
                findings.append(
                    AuditFinding(
                        rule_id=rule_id,
                        severity="error",
                        message=f"审计规则 {rule.name} 执行异常: {exc}",
                    )
                )
        return findings

    def reset(self) -> None:
        """清空所有注册的规则。"""
        logger.info("Resetting audit rule engine", component="audit_rule_engine")
        self._rules.clear()


# ── 默认审计规则 ────────────────────────────────────────────────────────────

def _check_decision_completeness(
    records: list[AuditRecord],
) -> list[AuditFinding]:
    """Rule 1: 决策完整性 — 每个 DECISION 审计记录应有相关 Trace IDs。"""
    findings: list[AuditFinding] = []
    for r in records:
        if r.record_type == AuditRecordType.DECISION.value:
            if not r.related_trace_ids:
                audit_ids = (r.audit_id,)
                findings.append(
                    AuditFinding(
                        rule_id="audit_rule_decision_completeness",
                        severity="warning",
                        message=(
                            f"决策审计记录 {r.audit_id} 缺少关联 Trace ID。"
                            f"来源: {r.source}，摘要: {r.summary}"
                        ),
                        related_audit_ids=audit_ids,
                    )
                )
    return findings


def _check_permission_consistency(
    records: list[AuditRecord],
) -> list[AuditFinding]:
    """Rule 2: 权限一致性 — Governance 拒绝的决策不应有后续执行记录。"""
    findings: list[AuditFinding] = []
    # 收集被 Governance 拒绝的 audit_ids
    rejected_sources: set[str] = set()
    rejected_summaries: dict[str, str] = {}
    for r in records:
        if r.record_type == AuditRecordType.GOVERNANCE.value:
            details = r.details or {}
            if details.get("outcome") == "rejected":
                rejected_summaries[r.audit_id] = r.summary

    # 检查是否有 Governance 拒绝后仍有 DECISION 执行记录
    for r in records:
        if r.record_type == AuditRecordType.DECISION.value:
            details = r.details or {}
            governance_ref = details.get("governance_audit_id", "")
            if governance_ref and governance_ref in rejected_summaries:
                audit_ids = (r.audit_id, governance_ref)
                findings.append(
                    AuditFinding(
                        rule_id="audit_rule_permission_consistency",
                        severity="error",
                        message=(
                            f"Governance 已拒绝的决策仍有执行记录。"
                            f"决策审计: {r.audit_id}，"
                            f"关联 Governance 审计: {governance_ref}"
                        ),
                        related_audit_ids=audit_ids,
                    )
                )
    return findings


def _check_execution_chain_completeness(
    records: list[AuditRecord],
) -> list[AuditFinding]:
    """Rule 3: 执行链完整性 — Action 生命周期应完整。"""
    findings: list[AuditFinding] = []
    execution_actions: dict[str, list[str]] = {}
    for r in records:
        if r.record_type == AuditRecordType.EXECUTION.value:
            details = r.details or {}
            action_status = details.get("action_status", "")
            action_key = f"{r.source}:{details.get('action_id', '')}"
            if action_key not in execution_actions:
                execution_actions[action_key] = []
            execution_actions[action_key].append(action_status)

    for action_key, statuses in execution_actions.items():
        has_start = any(s in ("scheduled", "executing") for s in statuses)
        has_end = any(s in ("completed", "failed") for s in statuses)
        if has_start and not has_end:
            findings.append(
                AuditFinding(
                    rule_id="audit_rule_execution_chain",
                    severity="warning",
                    message=(
                        f"Action 执行链不完整: {action_key}。"
                        f"有启动记录但缺少 completed/failed 终止记录。"
                        f"状态: {statuses}"
                    ),
                )
            )
    return findings


def _check_governance_traceability(
    records: list[AuditRecord],
) -> list[AuditFinding]:
    """Rule 4: 治理可追溯 — 知识变更必须有 Governance 审批记录。"""
    findings: list[AuditFinding] = []
    governance_sources: set[str] = set()
    for r in records:
        if r.record_type == AuditRecordType.GOVERNANCE.value:
            details = r.details or {}
            ref_source = details.get("target_source", "")
            if ref_source:
                governance_sources.add(ref_source)

    if governance_sources:
        findings.append(
            AuditFinding(
                rule_id="audit_rule_governance_traceability",
                severity="info",
                message=(
                    f"Governance 审批涉及 {len(governance_sources)} 个来源。"
                ),
            )
        )
    return findings


def _check_emergency_recovery(
    records: list[AuditRecord],
) -> list[AuditFinding]:
    """Rule 5: 应急恢复记录 — EMERGENCY_HALT 必须有恢复记录。"""
    findings: list[AuditFinding] = []
    halted: list[str] = []
    for r in records:
        if r.record_type == AuditRecordType.SYSTEM.value:
            details = r.details or {}
            event_type_name = details.get("event_type", "")
            if event_type_name == EventType.EMERGENCY_HALT.value:
                halted.append(r.audit_id)

    halted_set = set(halted)
    for r in records:
        if r.record_type == AuditRecordType.SYSTEM.value:
            details = r.details or {}
            event_type_name = details.get("event_type", "")
            if "reset" in event_type_name.lower() or "recover" in event_type_name.lower():
                related = details.get("related_halt_audit_id", "")
                if related in halted_set:
                    halted_set.discard(related)

    for halt_id in halted_set:
        audit_ids = (halt_id,)
        findings.append(
            AuditFinding(
                rule_id="audit_rule_emergency_recovery",
                severity="error",
                message=(
                    f"EMERGENCY_HALT 审计记录 {halt_id} 缺少对应的恢复记录。"
                ),
                related_audit_ids=audit_ids,
            )
        )
    return findings


# ── 默认规则注册表 ──────────────────────────────────────────────────────────

DEFAULT_AUDIT_RULES: list[tuple[AuditRule, CheckFn]] = [
    (
        AuditRule(
            rule_id="audit_rule_decision_completeness",
            name="决策完整性检查",
            description="每个 DECISION 审计记录应有至少一个关联 Trace ID",
            severity="warning",
            check_type="completeness",
        ),
        _check_decision_completeness,
    ),
    (
        AuditRule(
            rule_id="audit_rule_permission_consistency",
            name="权限一致性检查",
            description="Governance 拒绝的决策不应有后续执行记录",
            severity="error",
            check_type="permission",
        ),
        _check_permission_consistency,
    ),
    (
        AuditRule(
            rule_id="audit_rule_execution_chain",
            name="执行链完整性检查",
            description="Action 生命周期必须完整（有启动就有终止）",
            severity="warning",
            check_type="completeness",
        ),
        _check_execution_chain_completeness,
    ),
    (
        AuditRule(
            rule_id="audit_rule_governance_traceability",
            name="治理可追溯检查",
            description="知识变更必须有 Governance 审批记录",
            severity="info",
            check_type="compliance",
        ),
        _check_governance_traceability,
    ),
    (
        AuditRule(
            rule_id="audit_rule_emergency_recovery",
            name="应急恢复记录检查",
            description="EMERGENCY_HALT 必须有对应的恢复记录",
            severity="error",
            check_type="compliance",
        ),
        _check_emergency_recovery,
    ),
]


def load_default_audit_rules(rule_engine: AuditRuleEngine) -> None:
    """加载 5 条默认审计规则到引擎。"""
    logger.info("Loading default audit rules", component="audit_rule_engine", rule_count=len(DEFAULT_AUDIT_RULES))
    for rule, check_fn in DEFAULT_AUDIT_RULES:
        rule_engine.register_rule(rule, check_fn)
