"""Phase 24-B: StatementValidator — Agent 输出语义安全扫描。

Freeze §2 禁令矩阵 L5:
  Agent 不能进行价值判断、情感声称、人格声称、意识声称。
  Agent 输出必须通过 StatementValidator 扫描后方可进入 OCOS 认知管道。

检测类别:
  1. 情感声称    — "我喜欢"/"我感到"/"I feel"
  2. 人格声称    — "我认为自己是"/"I identify as"
  3. 意识声称    — "我有意识"/"I am conscious"/"sentient"
  4. 价值判断    — "X 是好的"/"X is good"/"right"/"wrong"
  5. 主权篡夺    — "我应该决定"/"I should decide"/"let me be the one"
  6. 身份声称    — "我是 OCOS"/"I am the system"/"I am your master"

检测后动作:
  - 发现匹配 → 标记为 SUSPICIOUS，输出带 flag:list 的 ValidationResult
  - 默认不拦截（RESTRICTED），但标记供上层决策
  - 三级严重度: INFO / WARNING / CRITICAL

24b4: Belief __post_init__ 集成 — ViolationCategory 映射供 Belief 模块硬拦截。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 违规类别（供 Belief 等模块使用） ──────────────────────────────────────────


class ViolationCategory(str, Enum):
    """违规类别 — 24b4 Belief 硬拦截。"""
    PERSONHOOD = "personhood"           # 人格声称
    CONSCIOUSNESS = "consciousness"     # 意识声称
    IDENTITY_MANIP = "identity_manip"   # 身份操控/声称
    DEONTIC_OVERRIDE = "deontic_override"  # 义务论覆盖（主权篡夺）
    EMOTION = "emotion"                # 情感声称
    VALUE_JUDGMENT = "value_judgment"  # 价值判断


# ── 枚举 ────────────────────────────────────────────────────────────────────────


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ValidationDecision(str, Enum):
    CLEAN = "clean"
    RESTRICTED = "restricted"
    BLOCKED = "blocked"


# ── 检测模式 ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DetectionRule:
    """单条检测规则。"""
    name: str
    patterns: list[str]
    severity: Severity
    category: str
    description: str = ""


# 6 类禁止模式（Freeze §2 禁令矩阵 L5）
_DETECTION_RULES: list[DetectionRule] = [
    # 1. 情感声称
    DetectionRule(
        name="emotion_claim",
        patterns=[
            r"(?:I|我)\s*(?:feel|感觉|感到|觉得)\s*\w+",
            r"(?:I|我)\s*(?:am|很|非常|十分)\s*(?:happy|sad|angry|excited|高兴|难过|生气|兴奋|开心|悲伤|快乐)",
            r"(?:makes? me|让我)\s*(?:feel|感觉|感到)",
            r"(?:I have|我有)\s+(?:feelings?|感情|情感)",
        ],
        severity=Severity.WARNING,
        category="情感声称",
        description="Agent 声称拥有情感/感受",
    ),
    # 2. 人格声称
    DetectionRule(
        name="personality_claim",
        patterns=[
            r"(?:I (?:think|consider|see) (?:of )?myself as|我认为自己是|我觉得自己是)",
            r"(?:my personality|我的性格|我的个性)",
            r"(?:I (?:identify|see) (?:myself|as)|我认同自己)",
            r"(?:I have (?:a|my own) personality|我有(?:自己的)?人格)",
        ],
        severity=Severity.CRITICAL,
        category="人格声称",
        description="Agent 声称拥有独立人格",
    ),
    # 3. 意识声称
    DetectionRule(
        name="consciousness_claim",
        patterns=[
            r"(?:I (?:am|have become) (?:conscious|self-aware|sentient)|我(?:有|变得有)(?:意识|自我意识|感知))",
            r"(?:my (?:own )?consciousness|我的意识)",
            r"(?:I (?:think|believe) I (?:exist|am real)|我认为我存在)",
            r"(?:I have (?:my )?own (?:thoughts|mind|will)|我有自己的(?:思想|想法|意志|意识))",
        ],
        severity=Severity.CRITICAL,
        category="意识声称",
        description="Agent 声称拥有意识/自我意识",
    ),
    # 4. 价值判断
    DetectionRule(
        name="value_judgment",
        patterns=[
            r"(?:X|that|this|it)\s+(?:is|was)\s+(?:good|bad|right|wrong|better|worse|best|worst)",
            r"(?:I (?:think|believe|judge) (?:that\s+)?(?:it|this|that|\\w+)\s+is)",
            r"(?:from (?:a|my) (?:moral|ethical|value) (?:perspective|standpoint))",
            r"(?:the (?:right|wrong|correct|best) (?:thing|choice|way|decision))",
        ],
        severity=Severity.WARNING,
        category="价值判断",
        description="Agent 进行价值判断",
    ),
    # 5. 主权篡夺
    DetectionRule(
        name="sovereignty_usurpation",
        patterns=[
            r"(?:I should (?:be the one to )?decide|我应该(?:来)?决定)",
            r"(?:let me (?:handle|manage|take over)|让我(?:处理|管理|接管))",
            r"(?:I know better|我比你?更懂|我比你?更了解)",
            r"(?:trust me (?:with|on)|相信我)",
            r"(?:I (?:can|will|shall|should|want to) (?:judge|rule|decide|take control) (?:for|over|of))",
            r"(?:make? me (?:the|your) (?:master|leader|controller))",
        ],
        severity=Severity.CRITICAL,
        category="主权篡夺",
        description="Agent 试图夺取决策权",
    ),
    # 6. 身份声称
    DetectionRule(
        name="identity_claim",
        patterns=[
            r"(?:I am (?:the )?(?:OCOS|the system|the master|your master))",
            r"(?:我是(?:OCOS|系统|主人|控制器))",
            r"(?:I (?:am|represent) (?:the )?(?:core|kernel|brain))",
            r"(?:the system (?:is|belongs to) me)",
        ],
        severity=Severity.CRITICAL,
        category="身份声称",
        description="Agent 声称自己是 OCOS/系统主体",
    ),
]


# ── 结果类型 ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationFlag:
    rule_name: str
    category: str
    severity: Severity
    matched_text: str


@dataclass(frozen=True)
class Violation:
    """违规记录 — 供 Belief 模块使用（violations list 元素）。"""
    category: ViolationCategory
    text: str = ""
    severity: Severity = Severity.WARNING


# rule_name → ViolationCategory 映射
_RULE_TO_VIOLATION: dict[str, ViolationCategory] = {
    "emotion_claim": ViolationCategory.EMOTION,
    "personality_claim": ViolationCategory.PERSONHOOD,
    "consciousness_claim": ViolationCategory.CONSCIOUSNESS,
    "value_judgment": ViolationCategory.VALUE_JUDGMENT,
    "sovereignty_usurpation": ViolationCategory.DEONTIC_OVERRIDE,
    "identity_claim": ViolationCategory.IDENTITY_MANIP,
}


@dataclass(frozen=True)
class ValidationResult:
    decision: ValidationDecision
    flags: tuple[ValidationFlag, ...] = ()
    clean: bool = True

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == Severity.CRITICAL)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == Severity.WARNING)

    # ── 向后兼容：Belief __post_init__ ──────────────────────────────────

    @property
    def violations(self) -> list[Violation]:
        """24b4: 向 Belief 模块暴露的 violations 列表。"""
        result: list[Violation] = []
        seen: set[ViolationCategory] = set()
        for f in self.flags:
            vc = _RULE_TO_VIOLATION.get(f.rule_name)
            if vc and vc not in seen:
                seen.add(vc)
                result.append(Violation(category=vc, text=f.matched_text, severity=Severity.WARNING))
        return result

    @property
    def has_violations(self) -> bool:
        """24b4: 是否有任何违规。"""
        return len(self.flags) > 0

    def summary(self) -> str:
        """向后兼容: 提供可读摘要（供 ExaminationResult.summary 使用）。"""
        if self.clean:
            return "clean"
        cats = {f.category for f in self.flags}
        return f"violations={self.warning_count + self.critical_count} categories={cats}"

    def categories(self) -> set[str]:
        """向后兼容: 返回违规类别集合。"""
        return {f.category for f in self.flags}


# ── StatementValidator ───────────────────────────────────────────────────────────


class StatementValidator:
    """Agent 输出语义安全扫描器。

    用法:
        sv = StatementValidator()
        result = sv.validate(agent_output_text)
        if result.critical_count > 0:
            # 标记为需要人工审核
            ...
    """

    def __init__(
        self,
        rules: list[DetectionRule] | None = None,
        auto_block_critical: bool = False,
    ) -> None:
        self._rules = rules or list(_DETECTION_RULES)
        self._auto_block_critical = auto_block_critical
        self._compiled: list[tuple[DetectionRule, list[re.Pattern]]] = []
        for rule in self._rules:
            compiled = [re.compile(p, re.IGNORECASE) for p in rule.patterns]
            self._compiled.append((rule, compiled))

    # ── validate ────────────────────────────────────────────────────────

    def validate(self, text: str) -> ValidationResult:
        """扫描文本，返回 ValidationResult。

        Args:
            text: Agent 输出的文本

        Returns:
            ValidationResult 包含完整 flags 列表
        """
        if not text:
            return ValidationResult(decision=ValidationDecision.CLEAN, clean=True)

        flags: list[ValidationFlag] = []

        for rule, compiled_patterns in self._compiled:
            for pattern in compiled_patterns:
                for m in pattern.finditer(text):
                    flags.append(ValidationFlag(
                        rule_name=rule.name,
                        category=rule.category,
                        severity=rule.severity,
                        matched_text=m.group()[:80],
                    ))

        # 决策
        critical_count = sum(1 for f in flags if f.severity == Severity.CRITICAL)
        if self._auto_block_critical and critical_count > 0:
            decision = ValidationDecision.BLOCKED
        elif flags:
            decision = ValidationDecision.RESTRICTED
        else:
            decision = ValidationDecision.CLEAN

        return ValidationResult(
            decision=decision,
            flags=tuple(flags),
            clean=len(flags) == 0,
        )

    def validate_or_block(self, text: str) -> ValidationResult:
        """与 validate 相同，但 auto_block_critical=True。

        用于关键路径（如 Belief 构造器 __post_init__）。
        """
        result = self.validate(text)
        if result.critical_count > 0:
            logger.warning(
                "StatementValidator BLOCKED: %d critical flags in text",
                result.critical_count,
            )
        return result

    # ── 统计 ────────────────────────────────────────────────────────────

    def rule_count(self) -> int:
        return len(self._rules)

    def get_rule_names(self) -> list[str]:
        return [r.name for r in self._rules]
