"""Phase 24.1 — ExperienceValidator。

Self 字段扫描 + 语义模式检测 + 必需字段检查。

从 Phase 24.1 开始扫描 Self 污染，而非等到 Phase 25。
"""

from __future__ import annotations

from ocos.memory.experience.models import TraceBundle, ExperienceCandidate


class ExperienceValidator:
    """边界检查: 防止 Memory 越权进入 Self。"""

    # 禁止出现在 Experience 中的字段名
    FORBIDDEN_FIELDS: frozenset[str] = frozenset({
        "self",
        "identity",
        "personality",
        "value",
        "mission",
        "purpose",
        "self_attribution",
        "self_label",
        "personality_trait",
        "identity_impact",
    })

    # 禁止出现在描述中的语义模式
    FORBIDDEN_PATTERNS: list[str] = [
        "I am",
        "I should become",
        "My value is",
        "I am not",
        "I have always been",
        "I realized that I",
    ]

    # ── TraceBundle 验证 ───────────────────────────────────────────────────

    @classmethod
    def validate_trace_bundle(cls, trace_bundle: TraceBundle) -> list[str]:
        """检查 TraceBundle 是否包含 Self 字段。

        Returns:
            违规字段列表。空列表 = 通过。
        """
        violations: list[str] = []

        # 顶层字段检查
        for key in trace_bundle.__dataclass_fields__:
            if key in cls.FORBIDDEN_FIELDS:
                violations.append(f"forbidden field '{key}' in TraceBundle")

        # 嵌套 dict 检查
        for field_name in ("observation", "action_result", "outcome"):
            field_data = getattr(trace_bundle, field_name, None)
            if isinstance(field_data, dict):
                for key in field_data:
                    if key in cls.FORBIDDEN_FIELDS:
                        violations.append(
                            f"forbidden field '{key}' in {field_name}"
                        )

        return violations

    # ── ExperienceCandidate 验证 ───────────────────────────────────────────

    @classmethod
    def validate_candidate(cls, candidate: ExperienceCandidate) -> list[str]:
        """检查 ExperienceCandidate 是否包含 Self 字段。"""
        violations: list[str] = []

        for key in candidate.__dataclass_fields__:
            if key in cls.FORBIDDEN_FIELDS:
                violations.append(
                    f"forbidden field '{key}' in ExperienceCandidate"
                )

        if isinstance(candidate.context, dict):
            for key in candidate.context:
                if key in cls.FORBIDDEN_FIELDS:
                    violations.append(f"forbidden field '{key}' in context")

        return violations

    @classmethod
    def scan_for_self_patterns(
        cls, candidate: ExperienceCandidate
    ) -> list[str]:
        """扫描语义中是否包含 Self 归因模式。

        扫描 candidate 所有字符串字段 + trace_bundle 嵌套结构。
        """
        violations: list[str] = []

        def _scan_value(value: object) -> None:
            if isinstance(value, str):
                lower_text = value.lower()
                for pattern in cls.FORBIDDEN_PATTERNS:
                    if pattern.lower() in lower_text:
                        violations.append(
                            f"self-pattern detected: '{pattern}' in '{value[:80]}'"
                        )
            elif isinstance(value, dict):
                for v in value.values():
                    _scan_value(v)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    _scan_value(item)

        # 扫描 candidate 所有顶层字段
        for field_name in candidate.__dataclass_fields__:
            _scan_value(getattr(candidate, field_name, None))

        # 递归扫描 trace_bundle 的嵌套 dict 字段
        bundle = candidate.trace_bundle
        for field_name in bundle.__dataclass_fields__:
            _scan_value(getattr(bundle, field_name, None))

        return violations

    # ── 必需字段检查 ───────────────────────────────────────────────────────

    @classmethod
    def required_fields_present(
        cls, trace_bundle: TraceBundle
    ) -> tuple[bool, list[str]]:
        """检查五要素是否齐全。

        Returns:
            (complete, missing_fields)
        """
        required = [
            "observation",
            "reasoning_trace_id",
            "decision_trace_id",
            "action_result",
            "outcome",
        ]
        missing = []
        for field in required:
            value = getattr(trace_bundle, field, None)
            if value is None or (isinstance(value, str) and not value):
                missing.append(field)
        return len(missing) == 0, missing

    # ── 全量验证 ───────────────────────────────────────────────────────────

    @classmethod
    def full_validation(
        cls, candidate: ExperienceCandidate
    ) -> tuple[bool, list[str]]:
        """对 Candidate 执行全量验证。

        Returns:
            (passed, all_violations)
        """
        all_violations: list[str] = []
        all_violations.extend(cls.validate_trace_bundle(candidate.trace_bundle))
        all_violations.extend(cls.validate_candidate(candidate))
        all_violations.extend(cls.scan_for_self_patterns(candidate))
        return len(all_violations) == 0, all_violations
