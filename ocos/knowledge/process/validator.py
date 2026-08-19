"""
M3 Knowledge Validator — 知识单元校验。

Validator 负责验证 KnowledgeUnit 的结构完整性、一致性和业务约束。

校验类别:
- Structural: 必填字段、类型约束
- Consistency: 层级与内容的匹配
- Constraint: 业务规则（同层级数量限制、命名规范等）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationResult:
    """
    单个校验结果。

    Attributes:
        field: 字段路径 (e.g. "level"、"payload.summary")
        severity: 校验严重级别
        message: 校验消息
    """
    field: str
    severity: ValidationSeverity
    message: str


@dataclass
class ValidationReport:
    """
    校验报告，包含所有校验结果。
    """
    results: list[ValidationResult]

    @property
    def has_errors(self) -> bool:
        return any(r.severity == ValidationSeverity.ERROR for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.severity == ValidationSeverity.WARNING for r in self.results)

    @property
    def errors(self) -> list[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationResult]:
        return [r for r in self.results if r.severity == ValidationSeverity.WARNING]


# ── 校验规则类型 ──────────────────────────────────────────────────────────

ValidatorFn = Callable[[KnowledgeUnit, dict[str, Any] | None], list[ValidationResult]]


@dataclass(frozen=True)
class ValidationRule:
    """校验规则定义。"""
    name: str
    description: str
    check_fn: ValidatorFn


# ── 内置校验规则 ──────────────────────────────────────────────────────────


def check_content_exists(unit: KnowledgeUnit, context: dict | None) -> list[ValidationResult]:
    """检查 content 是否为空。"""
    if not unit.content:
        logger.debug("check_content_exists failed: unit=%s content is empty", unit.unit_id)
        return [
            ValidationResult(
                field="content",
                severity=ValidationSeverity.ERROR,
                message="知识单元必须有 content 内容",
            )
        ]
    return []


def check_level_status_valid(unit: KnowledgeUnit, context: dict | None) -> list[ValidationResult]:
    """检查 level 和 status 的基本类型有效性。"""
    results: list[ValidationResult] = []
    if not isinstance(unit.level, KnowledgeLevel):
        logger.warning("check_level_status_valid: unit=%s level type invalid: %s",
                       unit.unit_id, type(unit.level))
        results.append(
            ValidationResult(
                field="level",
                severity=ValidationSeverity.ERROR,
                message=f"level 必须是 KnowledgeLevel 枚举类型，得到 {type(unit.level)}",
            )
        )
    if not isinstance(unit.status, KnowledgeStatus):
        logger.warning("check_level_status_valid: unit=%s status type invalid: %s",
                       unit.unit_id, type(unit.status))
        results.append(
            ValidationResult(
                field="status",
                severity=ValidationSeverity.ERROR,
                message=f"status 必须是 KnowledgeStatus 枚举类型，得到 {type(unit.status)}",
            )
        )
    return results


def check_tags_format(unit: KnowledgeUnit, context: dict | None) -> list[ValidationResult]:
    """检查 source 格式（替代原 tags）。"""
    results: list[ValidationResult] = []
    if unit.source and len(unit.source) > 128:
        logger.debug("check_tags_format: unit=%s source length %d exceeds 128",
                     unit.unit_id, len(unit.source))
        results.append(
            ValidationResult(
                field="source",
                severity=ValidationSeverity.WARNING,
                message=f"source 超过 128 字符建议长度 ({len(unit.source)})",
            )
        )
    return results


def check_elevation_chain(unit: KnowledgeUnit, context: dict | None) -> list[ValidationResult]:
    """检查提升链中的 parent_id 层级是否低于本单元层级。"""
    results: list[ValidationResult] = []
    if unit.parent_id and context and "registry" in context:
        registry = context["registry"]
        parent_entry = registry.get(unit.parent_id, requestor="*", scope_filter="*")
        if parent_entry:
            parent_level = parent_entry.unit.level
            if parent_level.value >= unit.level.value:
                logger.warning("check_elevation_chain: unit=%s parent=%s parent_level=%s >= unit_level=%s",
                               unit.unit_id, unit.parent_id, parent_level.value, unit.level.value)
                results.append(
                    ValidationResult(
                        field="parent_id",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"父单元层级 {parent_level.value} 不低于当前单元层级 "
                            f"{unit.level.value}，违反提升方向规则"
                        ),
                    )
                )
    return results


# ── 默认规则集 ──────────────────────────────────────────────────────────

DEFAULT_VALIDATION_RULES: list[ValidationRule] = [
    ValidationRule(
        name="content_exists",
        description="检查 content 不能为空",
        check_fn=check_content_exists,
    ),
    ValidationRule(
        name="level_status_valid",
        description="检查 level 和 status 值为枚举类型",
        check_fn=check_level_status_valid,
    ),
    ValidationRule(
        name="tags_format",
        description="检查 source 格式规范",
        check_fn=check_tags_format,
    ),
]


# ── Validator ──────────────────────────────────────────────────────────


class KnowledgeValidator:
    """
    知识校验器。

    支持注册自定义校验规则，并提供了多规则组合校验能力。
    """

    def __init__(self):
        self._rules: dict[str, ValidationRule] = {}
        self._load_default_rules()

    def _load_default_rules(self) -> None:
        for rule in DEFAULT_VALIDATION_RULES:
            self._rules[rule.name] = rule
        logger.debug("loaded %d default validation rules", len(DEFAULT_VALIDATION_RULES))

    def register_rule(self, rule: ValidationRule) -> None:
        """注册自定义校验规则。"""
        self._rules[rule.name] = rule
        logger.info("register_rule: %s - %s", rule.name, rule.description)

    def remove_rule(self, name: str) -> None:
        """移除校验规则。"""
        self._rules.pop(name, None)
        logger.debug("remove_rule: %s", name)

    def get_rule_names(self) -> list[str]:
        """获取所有已注册的规则名称。"""
        return list(self._rules.keys())

    def validate(
        self,
        unit: KnowledgeUnit,
        context: dict[str, Any] | None = None,
        rule_names: list[str] | None = None,
    ) -> ValidationReport:
        """
        对知识单元执行校验。

        Args:
            unit: 待校验的知识单元
            context: 可选的上下文信息 (如 "registry": KnowledgeRegistry 实例)
            rule_names: 指定要运行的规则列表，None 表示运行所有规则

        Returns:
            ValidationReport 校验报告
        """
        names = rule_names or list(self._rules.keys())
        results: list[ValidationResult] = []
        for name in names:
            rule = self._rules.get(name)
            if rule is None:
                logger.warning("validate: rule '%s' not registered, skipping", name)
                results.append(
                    ValidationResult(
                        field="*",
                        severity=ValidationSeverity.WARNING,
                        message=f"校验规则 '{name}' 未注册，已跳过",
                    )
                )
                continue
            try:
                rule_results = rule.check_fn(unit, context)
                results.extend(rule_results)
            except Exception as e:
                logger.error("validate: rule '%s' raised exception: %s", name, e)
                results.append(
                    ValidationResult(
                        field="*",
                        severity=ValidationSeverity.ERROR,
                        message=f"校验规则 '{name}' 执行异常: {e}",
                    )
                )
        report = ValidationReport(results=results)
        logger.debug("validate: unit=%s rules=%d errors=%d warnings=%d",
                     unit.unit_id, len(names), len(report.errors), len(report.warnings))
        return report
