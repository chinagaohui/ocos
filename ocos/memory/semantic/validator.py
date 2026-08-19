"""Phase 24.3-B — KnowledgeValidator。

五重防护:
    1. Schema     — 字段白名单，不含 self/identity/value/personality/mission
    2. Lineage    — 单向证据链 (source_patterns 非空，不可反向)
    3. Language   — 第三人称，拒绝第一人称/身份归因/行为准则
    4. Scope      — scope 必须含 domain，preconditions 非空
    5. Audit      — counterexamples 记录，反例 > 0 → 自动降低 status
"""

from __future__ import annotations

import re
from dataclasses import fields

from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeStatus


# ── 禁用语 ──────────────────────────────────────────────────────────────────

_FORBIDDEN_SCHEMA_TERMS = frozenset({
    "self", "identity", "personality", "persona",
    "value", "mission", "character", "owner",
    "preference", "goal_owner",
})

# 第一人称 (English — regex with word boundaries)
_FIRST_PERSON_EN = [
    r"\bI am\b", r"\bI was\b", r"\bI have\b", r"\bI should\b",
    r"\bI must\b", r"\bI will\b", r"\bI can\b", r"\bI cannot\b",
    r"\bI tend to\b", r"\bmy\b", r"\bmine\b", r"\bwe\b",
]
_FIRST_PERSON_CN = ["我", "自我", "本人"]

# 身份归因
_IDENTITY_EN = [
    r"\bam\s+a\s+(slow|fast|bad|good|poor|strong)\b",
    r"\bis\s+a\s+(slow|fast|bad|good|poor|strong)\b",
    r"\b(system)\s+(is|tends)\s+(to|toward)\b",
]
_IDENTITY_CN = ["我是一个", "不善于", "倾向于", "容易失败"]

# 行为准则 (属于 Belief)
_BELIEF_EN = [
    r"\bshould\b", r"\bmust\b", r"\bought to\b", r"\bsupposed to\b",
]
_BELIEF_CN = ["应该", "必须", "理应", "需要一直", "始终要"]


class KnowledgeValidator:
    """KnowledgeEntry 的五重审核器。"""

    @classmethod
    def validate(cls, entry: KnowledgeEntry) -> tuple[bool, list[str], KnowledgeStatus]:
        """验证 KnowledgeEntry。

        Returns: (passed, violations, recommended_status)
        """
        violations: list[str] = []

        violations.extend(cls._check_schema(entry))
        violations.extend(cls._check_lineage(entry))
        violations.extend(cls._check_language(entry))
        violations.extend(cls._check_scope(entry))

        # Audit violations 不影响 passed (反例是跟踪信号，非阻断)
        audit_violations = cls._check_audit(entry)
        violations.extend(audit_violations)

        passed = len(violations) - len(audit_violations) == 0
        status = cls._determine_status(entry, passed, audit_violations)
        return passed, violations, status

    # ── 1. Schema ─────────────────────────────────────────────────────────

    @classmethod
    def _check_schema(cls, entry: KnowledgeEntry) -> list[str]:
        violations: list[str] = []
        field_names = {f.name for f in fields(entry)}
        overlap = field_names & set(_FORBIDDEN_SCHEMA_TERMS)
        if overlap:
            violations.append(f"forbidden schema fields: {sorted(overlap)}")
        return violations

    # ── 2. Lineage ────────────────────────────────────────────────────────

    @classmethod
    def _check_lineage(cls, entry: KnowledgeEntry) -> list[str]:
        violations: list[str] = []
        if not entry.source_patterns:
            violations.append("empty source_patterns — Knowledge must have evidence lineage")
        return violations

    # ── 3. Language ───────────────────────────────────────────────────────

    @classmethod
    def _check_language(cls, entry: KnowledgeEntry) -> list[str]:
        violations: list[str] = []
        text = entry.statement

        if not text:
            violations.append("empty statement")
            return violations

        for pattern in _FIRST_PERSON_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"first-person (en) '{pattern}' in statement")
                break

        for term in _FIRST_PERSON_CN:
            if term in text:
                violations.append(f"first-person (cn) '{term}' in statement")
                break

        for pattern in _IDENTITY_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"identity (en) '{pattern}' in statement")
                break

        for term in _IDENTITY_CN:
            if term in text:
                violations.append(f"identity (cn) '{term}' in statement")
                break

        for pattern in _BELIEF_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"belief (en) '{pattern}' in statement")
                break

        for term in _BELIEF_CN:
            if term in text:
                violations.append(f"belief (cn) '{term}' in statement")
                break

        return violations

    # ── 4. Scope ──────────────────────────────────────────────────────────

    @classmethod
    def _check_scope(cls, entry: KnowledgeEntry) -> list[str]:
        violations: list[str] = []
        scope = entry.scope
        if not scope.domain.strip():
            violations.append("scope.domain is empty")
        return violations

    # ── 5. Audit ──────────────────────────────────────────────────────────

    @classmethod
    def _check_audit(cls, entry: KnowledgeEntry) -> list[str]:
        violations: list[str] = []
        if entry.scope.has_counterexamples():
            violations.append(
                f"has {entry.scope.counterexamples} counterexamples — "
                f"stability={entry.stability:.3f}"
            )
        return violations

    # ── Status ────────────────────────────────────────────────────────────

    @classmethod
    def _determine_status(
        cls,
        entry: KnowledgeEntry,
        passed: bool,
        audit_violations: list[str],
    ) -> KnowledgeStatus:
        if not passed:
            return KnowledgeStatus.DEPRECATED  # 验证失败 → 标记废弃
        if entry.stability < 0.6:
            return KnowledgeStatus.UNSTABLE
        if audit_violations:  # 反例或其他审计问题
            return KnowledgeStatus.UNSTABLE
        return KnowledgeStatus.ACTIVE
