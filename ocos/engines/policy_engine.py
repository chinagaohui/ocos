"""
PolicyEngine — 策略评估能力引擎。

Phase 19 — 第四个能力引擎。

职责:
1. 持有预定义的策略规则集合
2. 对目标（决策/行动/计划）进行策略符合性评估
3. 产生 PolicyTrace 记录
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessType
from ocos.models.policy import (
    PolicyEffect,
    PolicyDomain,
    PolicyRule,
    PolicyEvaluation,
    PolicyTrace,
)
from ocos.runtime.context_manager import WorkingMemory

from ocos.logging import get_logger

_SOURCE = "policy_engine"

logger = get_logger(__name__)


class RuntimeResult:
    """策略引擎的结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
        all_passed: bool = True,
        evaluated_count: int = 0,
        output_addresses: tuple[str, ...] = (),
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id
        self.all_passed = all_passed
        self.evaluated_count = evaluated_count
        self.output_addresses = output_addresses

    def __repr__(self) -> str:
        return (
            f"RuntimeResult(success={self.success}, trace_id={self.trace_id!r}, "
            f"all_passed={self.all_passed}, rules={self.evaluated_count})"
        )


# ── 自定义评估器注册表 ──────────────────────────────────────────────────────

_EVALUATORS: dict[str, Callable] = {}  # rule_id → evaluator


def register_rule_evaluator(
    rule_id: str,
    evaluator: Callable[[PolicyRule, dict[str, Any]], PolicyEvaluation],
) -> None:
    """注册自定义规则评估器。"""
    _EVALUATORS[rule_id] = evaluator


# ═══════════════════════════════════════════════════════════════════════════════
# PolicyEngine
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyEngine:
    """策略引擎 — 为 ProcessType.POLICY 提供策略评估能力。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, PolicyTrace] = {}
        self._rules: list[PolicyRule] = []
        logger.debug("__init__ completed", component="policy_engine")

    def __repr__(self) -> str:
        return f"PolicyEngine(traces={len(self._traces)}, rules={len(self._rules)})"

    # ── 规则管理 ─────────────────────────────────────────────────────────

    def add_rule(self, rule: PolicyRule) -> None:
        """添加一条策略规则。"""
        self._rules.append(rule)

    def add_rules(self, rules: list[PolicyRule]) -> None:
        """批量添加策略规则。"""
        self._rules.extend(rules)

    def remove_rule(self, rule_id: str) -> bool:
        """移除一条策略规则。"""
        for i, r in enumerate(self._rules):
            if r.rule_id == rule_id:
                self._rules.pop(i)
                return True
        return False

    def list_rules(self) -> list[PolicyRule]:
        """列出所有策略规则。"""
        return list(self._rules)

    def clear_rules(self) -> None:
        """清空所有策略规则。"""
        self._rules.clear()

    # ── 评估执行 ─────────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        target: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """基于 TransformProcess 执行策略评估。

        Args:
            process: 待评估的 POLICY Process
            targets: 评估目标（决策/行动/计划描述）

        Returns:
            RuntimeResult 包含评估结果
        """
        logger.info("evaluate policy", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.POLICY.value:
            return RuntimeResult(
                success=False,
                message=f"Not a POLICY process: {process.process_type}",
                process_id=process.process_id,
            )

        # 优先评估已注册的自定义规则
        rules_to_evaluate = self._resolve_rules(process)
        target_desc = target or "unnamed target"
        ctx = context or {}

        evaluations: list[PolicyEvaluation] = []
        for rule in rules_to_evaluate:
            eval_result = self._evaluate_rule(rule, ctx)
            evaluations.append(eval_result)

        # L1: 自主级别闸门 — 合成一条 autonomy_gate 评估（context.autonomy_level
        # 可覆盖，供测试/显式注入）；LEVEL=0 时策略评估整体不通过
        level = ctx.get("autonomy_level")
        if level is None:
            from ocos.execution.autonomy import get_autonomy_level
            level = get_autonomy_level()
        gate_passed = level >= 1
        level_desc = ("可自主执行" if level >= 2
                      else "可自主提案(需审批)" if level == 1
                      else "自主行为关闭")
        evaluations.append(PolicyEvaluation(
            rule_id="autonomy_gate",
            rule_name="autonomy_gate",
            effect=PolicyEffect.DENY,
            passed=gate_passed,
            detail=(
                f"autonomy_level={level} ({level_desc}): "
                f"{'PASS' if gate_passed else 'FAIL — LEVEL=0 禁止自主行为'}"
            ),
        ))

        all_passed = all(e.passed for e in evaluations)
        output_addrs = (
            (f"addr:policy:pass:{uuid.uuid4().hex}",) if all_passed
            else (f"addr:policy:fail:{uuid.uuid4().hex}",)
        )

        trace = PolicyTrace(
            process_id=process.process_id,
            target_description=target_desc,
            rules=tuple(rules_to_evaluate),
            evaluations=tuple(evaluations),
            all_passed=all_passed,
            input_addresses=tuple(str(a) for a in process.input_addresses),
            output_addresses=output_addrs,
        )
        self._traces[trace.trace_id] = trace

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "process_type": ProcessType.POLICY.value,
                "target": target_desc,
                "rule_count": len(rules_to_evaluate),
                "all_passed": all_passed,
                "trace_id": trace.trace_id,
            },
            source=_SOURCE,
        ))

        return RuntimeResult(
            success=True,
            message=f"Policy evaluation: {'ALL PASSED' if all_passed else 'VIOLATIONS DETECTED'} "
                    f"({len(evaluations)} rules)",
            trace_id=trace.trace_id,
            process_id=process.process_id,
            all_passed=all_passed,
            evaluated_count=len(evaluations),
            output_addresses=output_addrs,
        )

    def get_trace(self, trace_id: str) -> PolicyTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[PolicyTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _resolve_rules(self, process: TransformProcess) -> list[PolicyRule]:
        """确定要评估哪些规则。"""
        if not self._rules:
            # 默认规则：演示用途
            return [
                PolicyRule(
                    name="quality_minimum",
                    description="质量评分不低于 4",
                    domain=PolicyDomain.QUALITY,
                    effect=PolicyEffect.DENY,
                    priority=10,
                    condition="quality >= 4",
                ),
                PolicyRule(
                    name="cost_threshold",
                    description="成本不超过 8",
                    domain=PolicyDomain.RESOURCE,
                    effect=PolicyEffect.WARN,
                    priority=5,
                    condition="cost <= 8",
                ),
                PolicyRule(
                    name="risk_tolerance",
                    description="风险评分不超过 7",
                    domain=PolicyDomain.COMPLIANCE,
                    effect=PolicyEffect.DENY,
                    priority=8,
                    condition="risk <= 7",
                ),
            ]
        return list(self._rules)

    def _evaluate_rule(
        self,
        rule: PolicyRule,
        context: dict[str, Any],
    ) -> PolicyEvaluation:
        """评估单条规则。"""
        # 检查自定义评估器
        if rule.rule_id in _EVALUATORS:
            try:
                return _EVALUATORS[rule.rule_id](rule, context)
            except Exception as e:
                return PolicyEvaluation(
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    effect=rule.effect,
                    passed=False,
                    detail=f"Evaluator error: {e}",
                )

        # 默认评估：基于 context 中的数值判断
        return self._default_evaluate(rule, context)

    def _default_evaluate(
        self,
        rule: PolicyRule,
        context: dict[str, Any],
    ) -> PolicyEvaluation:
        """默认规则评估逻辑。"""
        # 从 condition 解析维度名和阈值
        parts = rule.condition.split()
        if len(parts) >= 3:
            dim = parts[0]
            op = parts[1]
            threshold = float(parts[2])
            value = context.get(dim, 0)

            if op == ">=":
                passed = value >= threshold
            elif op == "<=":
                passed = value <= threshold
            elif op == ">":
                passed = value > threshold
            elif op == "<":
                passed = value < threshold
            elif op == "==":
                passed = value == threshold
            else:
                passed = True

            detail = f"{dim}={value} vs {op} {threshold}: {'PASS' if passed else 'FAIL'}"
        else:
            passed = True
            detail = "No evaluable condition"

        # DENY 规则失败 → 不通过；WARN 规则失败 → 仍通过但标记
        if rule.effect == PolicyEffect.WARN:
            actual_passed = True  # 警告不阻止
            if not passed:
                detail += " (WARNING)"
        elif rule.effect == PolicyEffect.DENY:
            actual_passed = passed
        else:  # ALLOW
            actual_passed = passed

        return PolicyEvaluation(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            effect=rule.effect,
            passed=actual_passed,
            detail=detail,
        )

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="policy_engine",
    name="Policy Engine",
    version="1.0.0",
    engine_class="ocos.engines.policy_engine.PolicyEngine",
    capabilities=['policy'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
