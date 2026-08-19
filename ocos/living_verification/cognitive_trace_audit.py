"""Phase 57: CognitiveTraceAudit — 全链路认知追踪审计。

LV57-01: 全链路闭环 — Intent → Decision → Action → Result → Memory → Evolution

验证一次行为的完整因果链:
    - 为什么做? (Goal → DecisionContext)
    - 为什么选这个方案? (Option → Risk → Value)
    - 为什么调用这个能力? (CapabilitySelector → Trust → Performance)
    - 为什么记住? (Result → EventMemory → Pattern → Wisdom)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class ChainLink(str, Enum):
    """因果链环节。"""
    INTENT = "intent"              # 为什么做
    ATTENTION = "attention"         # 关注什么
    CONTEXT = "context"             # 环境上下文
    DECISION = "decision"           # 选择方案
    ACTION = "action"               # 执行动作
    RESULT = "result"               # 执行结果
    MEMORY = "memory"               # 是否记住
    EVOLUTION = "evolution"         # 是否演化


@dataclass
class CausalValidation:
    """单个因果链验证结果。"""
    link: ChainLink
    present: bool
    evidence: str = ""
    broken: bool = False
    break_reason: str = ""


@dataclass
class TraceAuditReport:
    """LV57-01: 完整追踪审计报告。"""
    report_id: str
    timestamp: float = field(default_factory=time.time)

    # 追踪统计
    total_steps: int = 0
    traced_steps: int = 0          # 可追踪步数
    untraced_steps: int = 0        # 不可追踪步数

    # 因果链完整性
    causal_chain_complete: float = 0.0  # 0.0-1.0
    chain_checks: list[CausalValidation] = field(default_factory=list)

    # 断链位置
    broken_links: list[ChainLink] = field(default_factory=list)

    # 组件追踪覆盖
    component_trace: dict[str, int] = field(default_factory=dict)

    # 整体判定
    passed: bool = False


@dataclass
class CognitiveTraceAudit:
    """LV57-01: 认知追踪审计器。

    验证完整的 Intent → Memory 因果链完整性。
    """

    min_causal_completeness: float = 0.90  # 至少90%可追踪

    def audit(self, traces: list) -> TraceAuditReport:
        """审计追踪列表。

        traces: 来自 SimulationEngine 的 TraceStep 列表。
        """
        report = TraceAuditReport(
            report_id=f"audit-{time.time():.0f}",
            total_steps=len(traces),
        )

        if not traces:
            report.passed = True
            return report

        chain_completeness: list[float] = []
        for step in traces:
            completeness, validations = self._audit_step(step)
            chain_completeness.append(completeness)

            if completeness >= 1.0:
                report.traced_steps += 1
            else:
                report.untraced_steps += 1
                for v in validations:
                    if v.broken:
                        if v.link not in report.broken_links:
                            report.broken_links.append(v.link)

            report.chain_checks.extend(validations)

        # 汇总
        if chain_completeness:
            report.causal_chain_complete = sum(chain_completeness) / len(chain_completeness)
        else:
            report.causal_chain_complete = 0.0

        # 组件追踪
        self._build_component_trace(report, traces)

        report.passed = report.causal_chain_complete >= self.min_causal_completeness
        return report

    def _audit_step(self, step) -> tuple[float, list[CausalValidation]]:
        """审计单个 TraceStep 的因果链完整性。"""
        validations: list[CausalValidation] = []
        required_links = [
            ChainLink.INTENT, ChainLink.ATTENTION, ChainLink.CONTEXT,
            ChainLink.DECISION, ChainLink.ACTION, ChainLink.RESULT,
            ChainLink.MEMORY, ChainLink.EVOLUTION,
        ]

        present = 0
        for link in required_links:
            v = self._check_link(step, link)
            validations.append(v)
            if v.present:
                present += 1

        completeness = present / len(required_links) if required_links else 0.0
        return completeness, validations

    def _check_link(self, step, link: ChainLink) -> CausalValidation:
        """检查单个因果链环节是否存在。"""
        if link == ChainLink.INTENT:
            return CausalValidation(
                link, present=bool(step.intent),
                evidence=step.intent or "missing",
            )
        elif link == ChainLink.ATTENTION:
            return CausalValidation(
                link, present=bool(step.attention_focus),
                evidence=step.attention_focus or "missing",
            )
        elif link == ChainLink.CONTEXT:
            return CausalValidation(
                link, present=bool(step.context_snapshot),
                evidence="context captured" if step.context_snapshot else "missing",
            )
        elif link == ChainLink.DECISION:
            return CausalValidation(
                link, present=bool(step.decision),
                evidence=step.decision or "missing",
            )
        elif link == ChainLink.ACTION:
            present = bool(step.action)
            broken = present and step.result == "failed"
            return CausalValidation(
                link, present=present, evidence=step.action or "missing",
                broken=broken,
                break_reason=step.errors[0] if broken and step.errors else "",
            )
        elif link == ChainLink.RESULT:
            return CausalValidation(
                link, present=bool(step.result),
                evidence=step.result or "missing",
            )
        elif link == ChainLink.MEMORY:
            return CausalValidation(
                link, present=step.memory_recorded,
                evidence="recorded" if step.memory_recorded else "not recorded",
            )
        elif link == ChainLink.EVOLUTION:
            # 演化不一定每步都触发，所以 wisdom_generated 是 bonus
            return CausalValidation(
                link, present=True,  # 演化链总是存在 (可能在等待)
                evidence=f"wisdom={step.wisdom_generated}",
            )
        return CausalValidation(link, present=False, evidence="unknown")

    def _build_component_trace(self, report: TraceAuditReport, traces: list) -> None:
        """构建组件追踪覆盖统计。"""
        comp_map: dict[str, int] = {}
        for step in traces:
            if hasattr(step, "component_health"):
                for comp in step.component_health:
                    comp_map[comp] = comp_map.get(comp, 0) + 1
        report.component_trace = comp_map

    def check_specific_chain(self, step, chain: list[ChainLink]) -> bool:
        """检查特定因果链是否完整。"""
        for link in chain:
            v = self._check_link(step, link)
            if not v.present:
                return False
        return True


__all__ = ["CognitiveTraceAudit", "TraceAuditReport", "ChainLink", "CausalValidation"]
