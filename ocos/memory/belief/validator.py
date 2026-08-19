"""Phase 24.4-A — BeliefValidator。

三重审核:
    1. Schema   — 字段白名单，禁止 self/identity/value/goal...
    2. Evidence — evidence_count >= 3, avg_quality >= 0.5
    3. Boundary — 阻断 Belief → Identity / Goal / Value / Preference
"""

from __future__ import annotations

import re
from dataclasses import fields

from ocos.memory.belief.models import Belief, BeliefStatus

from ocos.memory.belief.evidence import Evidence


# ── 禁用语 ──────────────────────────────────────────────────────────────────

_FORBIDDEN_SCHEMA_TERMS = frozenset({
    "self", "identity", "personality", "persona",
    "value", "mission", "character", "owner",
    "preference", "goal_owner", "goal",
})

# 第一人称
_FIRST_PERSON_EN = [
    r"\bI am\b", r"\bI was\b", r"\bI have\b",
    r"\bI tend to\b", r"\bmy\b", r"\bmine\b",
]
_FIRST_PERSON_CN = ["我", "自我", "本人"]

# 身份归因
_IDENTITY_EN = [
    r"\bam\s+a\s+(slow|fast|bad|good|poor|strong)\b",
    r"\b(system)\s+(is|tends)\s+(to|toward)\b",
]
_IDENTITY_CN = ["我是一个", "不善于", "倾向于", "容易失败"]

# 行为准则 / 价值 / 目标
_BELIEF_EN = [r"\bshould\b", r"\bmust\b", r"\bought to\b"]
_BELIEF_CN = ["应该", "必须", "理应", "需要一直", "优先"]


class BeliefValidator:
    """Belief 的三重审核器。"""

    @classmethod
    def validate(
        cls,
        belief: Belief,
        evidence: list[Evidence],
    ) -> tuple[bool, list[str]]:
        """验证 Belief。

        Returns: (passed, violations)
        """
        violations: list[str] = []

        violations.extend(cls._check_schema(belief))
        violations.extend(cls._check_evidence(belief, evidence))
        violations.extend(cls._check_boundary(belief))

        return len(violations) == 0, violations

    # ── 1. Schema ─────────────────────────────────────────────────────────

    @classmethod
    def _check_schema(cls, belief: Belief) -> list[str]:
        violations: list[str] = []
        field_names = {f.name for f in fields(belief)}
        overlap = field_names & set(_FORBIDDEN_SCHEMA_TERMS)
        if overlap:
            violations.append(f"forbidden fields: {sorted(overlap)}")
        return violations

    # ── 2. Evidence ──────────────────────────────────────────────────────

    @classmethod
    def _check_evidence(
        cls,
        belief: Belief,
        evidence: list[Evidence],
    ) -> list[str]:
        violations: list[str] = []

        min_count = 3
        min_quality = 0.5

        # 先检查 evidence count mismatch (ID 数量 ≠ 实际 Evidence 数量)
        if belief.evidence_count != len(evidence):
            violations.append(
                f"evidence count mismatch: "
                f"belief={belief.evidence_count}, actual={len(evidence)}"
            )
            return violations

        if len(evidence) < min_count:
            violations.append(
                f"insufficient evidence: {len(evidence)} < {min_count}"
            )
            return violations

        avg_quality = sum(e.quality for e in evidence) / len(evidence)
        if avg_quality < min_quality:
            violations.append(
                f"low evidence quality: {avg_quality:.3f} < {min_quality}"
            )

        return violations

    # ── 3. Boundary ──────────────────────────────────────────────────────

    @classmethod
    def _check_boundary(cls, belief: Belief) -> list[str]:
        """阻止 Belief 产生 Identity / Goal / Value / Preference。"""
        violations: list[str] = []
        text = belief.statement

        if not text:
            violations.append("empty statement")
            return violations

        # 第一人称
        for pattern in _FIRST_PERSON_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"first-person (en) '{pattern}'")
                break
        for term in _FIRST_PERSON_CN:
            if term in text:
                violations.append(f"first-person (cn) '{term}'")
                break

        # 身份归因
        for pattern in _IDENTITY_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"identity (en) '{pattern}'")
                break
        for term in _IDENTITY_CN:
            if term in text:
                violations.append(f"identity (cn) '{term}'")
                break

        # 行为准则 / 价值
        for pattern in _BELIEF_EN:
            if re.search(pattern, text, re.IGNORECASE):
                violations.append(f"deontic (en) '{pattern}'")
                break
        for term in _BELIEF_CN:
            if term in text:
                violations.append(f"deontic (cn) '{term}'")
                break

        return violations
