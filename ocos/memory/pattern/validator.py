"""Phase 24.3-A — Pattern Validator。

双层防护: Schema Validator (字段名检查) + Semantic Validator (语义检测)。

验证内容:
    1. Schema: 不含 self/identity/personality/value 字段
    2. Semantic: 不含第一人称 / 身份归因 / 行为准则
    3. Causality: 必须存在 trigger_condition → observed_relation 关系
    4. Abstraction: 不引用 Episode ID
"""

from __future__ import annotations

import re
from dataclasses import fields

from ocos.memory.pattern.models import PatternCandidate, PatternStatus


# ── 禁用语 ──────────────────────────────────────────────────────────────────

_FORBIDDEN_SCHEMA_TERMS = {
    "self", "identity", "personality", "persona",
    "value", "mission", "character", "owner",
}

# 第一人称模式
_FIRST_PERSON_EN = [
    r"\bI am\b", r"\bI was\b", r"\bI have\b", r"\bI should\b",
    r"\bI must\b", r"\bI will\b", r"\bI can\b", r"\bI cannot\b",
    r"\bI tend to\b", r"\bmy\b", r"\bmine\b", r"\bwe\b",
]
_FIRST_PERSON_CN = [
    "我", "自我", "本人",
]

# 身份归因模式
_IDENTITY_EN = [
    r"\bam\s+a\s+(slow|fast|bad|good|poor|strong)\b",
    r"\bis\s+a\s+(slow|fast|bad|good|poor|strong)\b",
    r"\b(system)\s+(is|tends)\s+(to|toward)\b",
]
_IDENTITY_CN = [
    "我是一个", "我是一个", "不善于", "适合", "倾向于", "容易",
]

# 行为准则模式 (属于 Belief, 非 Knowledge)
_BELIEF_EN = [
    r"\bshould\b", r"\bmust\b", r"\bought to\b", r"\bsupposed to\b",
]
_BELIEF_CN = [
    "应该", "必须", "理应", "需要一直", "始终要",
]

# Episode ID 引用模式
_EPISODE_ID_PATTERN = re.compile(r'\bEPI-\d{8}-[A-F0-9]{8}\b', re.IGNORECASE)


class PatternValidator:
    """PatternCandidate → Validated Pattern 的审核器。

    使用:
        validator = PatternValidator()
        result = validator.validate(candidate)
    """

    @classmethod
    def validate(cls, candidate: PatternCandidate) -> tuple[bool, list[str], PatternStatus]:
        """验证 PatternCandidate 是否可作为正式 Pattern。

        Returns:
            (passed, violations, final_status)
        """
        violations: list[str] = []

        # 第1层: Schema 检查
        violations.extend(cls._check_schema(candidate))

        # 第2层: 语义检查
        violations.extend(cls._check_semantics(candidate))

        # 第3层: 因果性检查
        violations.extend(cls._check_causality(candidate))

        # 第4层: 抽象性检查
        violations.extend(cls._check_abstraction(candidate))

        passed = len(violations) == 0
        status = PatternStatus.VALIDATED if passed else PatternStatus.REJECTED
        return passed, violations, status

    @classmethod
    def _check_schema(cls, candidate: PatternCandidate) -> list[str]:
        """检查字段名不含禁止词。"""
        violations: list[str] = []
        field_names = {f.name for f in fields(candidate)}
        overlap = field_names & _FORBIDDEN_SCHEMA_TERMS
        if overlap:
            violations.append(
                f"forbidden schema fields: {sorted(overlap)}"
            )
        return violations

    @classmethod
    def _check_semantics(cls, candidate: PatternCandidate) -> list[str]:
        """检查所有文本字段不含 Self 语义。"""
        violations: list[str] = []
        texts = [
            candidate.trigger_condition,
            candidate.observed_relation,
            candidate.causal_explanation,
        ]

        for text in texts:
            if not text:
                continue

            # 检查第一人称 (English — regex with word boundaries)
            for pattern in _FIRST_PERSON_EN:
                if re.search(pattern, text, re.IGNORECASE):
                    violations.append(
                        f"first-person (en) '{pattern}' in '{text[:60]}'"
                    )
                    break

            # 检查第一人称 (中文 — substring match)
            for term in _FIRST_PERSON_CN:
                if term in text:
                    violations.append(
                        f"first-person (cn) '{term}' in '{text[:60]}'"
                    )
                    break

            # 检查身份归因 (English)
            for pattern in _IDENTITY_EN:
                if re.search(pattern, text, re.IGNORECASE):
                    violations.append(
                        f"identity (en) '{pattern}' in '{text[:60]}'"
                    )
                    break

            # 检查身份归因 (中文)
            for term in _IDENTITY_CN:
                if term in text:
                    violations.append(
                        f"identity (cn) '{term}' in '{text[:60]}'"
                    )
                    break

            # 检查行为准则 (English)
            for pattern in _BELIEF_EN:
                if re.search(pattern, text, re.IGNORECASE):
                    violations.append(
                        f"belief (en) '{pattern}' in '{text[:60]}'"
                    )
                    break

            # 检查行为准则 (中文)
            for term in _BELIEF_CN:
                if term in text:
                    violations.append(
                        f"belief (cn) '{term}' in '{text[:60]}'"
                    )
                    break

        return violations

    @classmethod
    def _check_causality(cls, candidate: PatternCandidate) -> list[str]:
        """检查必须存在因果结构: trigger_condition 和 observed_relation 都非空。"""
        violations: list[str] = []
        if not candidate.trigger_condition.strip():
            violations.append("missing trigger_condition")
        if not candidate.observed_relation.strip():
            violations.append("missing observed_relation")
        return violations

    @classmethod
    def _check_abstraction(cls, candidate: PatternCandidate) -> list[str]:
        """检查不引用具体 Episode ID。"""
        violations: list[str] = []
        all_text = " ".join([
            candidate.trigger_condition,
            candidate.observed_relation,
            candidate.causal_explanation,
        ])
        if _EPISODE_ID_PATTERN.search(all_text):
            violations.append("Pattern contains raw Episode ID references")
        return violations
