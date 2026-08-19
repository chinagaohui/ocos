"""Phase 25.3 — StatementValidator。

确保 SelfModel.statement 是事实描述而非叙事/人格表达。

六类禁止词汇:
    - 情感 (emotion)
    - 偏好 (preference)
    - 价值判断 (value)
    - 目标 (goal)
    - 人格 (personality)
    - 叙事 (narrative)

额外规则:
    - 事实主语检查
    - 长度限制 ≤200 字符
"""

from __future__ import annotations

import re


class StatementValidator:
    """验证 SelfModel.statement 不含人格/情感/偏好/价值/目标/叙事表达。

    用法:
        valid, reason = StatementValidator.validate(statement)
        if not valid:
            raise ValueError(reason)
    """

    # ── 禁止词汇 ──────────────────────────────────────────────────────────

    # 情感类
    FORBIDDEN_EMOTION: tuple[str, ...] = (
        "喜欢", "讨厌", "热爱", "害怕", "担心", "渴望", "希望",
        "愤怒", "悲伤", "喜悦", "焦虑", "满足", "后悔", "期待",
        "happy", "sad", "love", "hate", "fear", "hope",
        "angry", "anxious", "regret", "excited",
    )

    # 偏好类
    FORBIDDEN_PREFERENCE: tuple[str, ...] = (
        "倾向", "偏好", "更喜欢", "偏爱",
        "prefer", "tend to", "inclined",
    )

    # 价值判断类
    FORBIDDEN_VALUE: tuple[str, ...] = (
        "应该", "重要", "有意义", "有价值", "必要", "必须",
        "should", "important", "valuable", "necessary", "must",
        "essential", "meaningful",
    )

    # 目标类
    FORBIDDEN_GOAL: tuple[str, ...] = (
        "想要", "打算", "计划", "目标是", "目的是",
        "want", "plan to", "intend", "goal is", "aim to",
    )

    # 人格类
    FORBIDDEN_PERSONALITY: tuple[str, ...] = (
        "友好", "善良", "诚实", "忠诚", "幽默", "温柔", "体贴",
        "friendly", "kind", "honest", "loyal", "gentle",
        "humble", "caring",
    )

    # 叙事类
    FORBIDDEN_NARRATIVE: tuple[str, ...] = (
        "成为", "变成", "成长", "进化成", "发展成",
        "become", "evolve into", "grow into", "transform into",
    )

    # 汇总（用于扫描）
    ALL_FORBIDDEN: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("emotion", "情感", FORBIDDEN_EMOTION),
        ("preference", "偏好", FORBIDDEN_PREFERENCE),
        ("value", "价值判断", FORBIDDEN_VALUE),
        ("goal", "目标", FORBIDDEN_GOAL),
        ("personality", "人格", FORBIDDEN_PERSONALITY),
        ("narrative", "叙事", FORBIDDEN_NARRATIVE),
    )

    # ── 事实主语模式 ──────────────────────────────────────────────────────

    FACTUAL_SUBJECTS: tuple[str, ...] = (
        "当前系统", "本系统", "ocos", "the system",
    )

    # ── 长度限制 ──────────────────────────────────────────────────────────

    MAX_STATEMENT_CHARS: int = 200

    # ── 验证方法 ──────────────────────────────────────────────────────────

    @classmethod
    def validate(cls, statement: str) -> tuple[bool, str]:
        """返回 (is_valid, reason)。

        reason 为空字符串表示通过。
        """
        if not statement or not statement.strip():
            return False, "Statement must not be empty"

        lower = statement.lower()

        # 1. 禁止词汇检查——按优先级返回最严重的违规类别
        for category_en, category_zh, words in cls.ALL_FORBIDDEN:
            for word in words:
                if word in lower:
                    return False, (
                        f"Forbidden {category_zh}({category_en}) word "
                        f"'{word}' in statement"
                    )

        # 2. 长度检查
        if len(statement) > cls.MAX_STATEMENT_CHARS:
            return False, (
                f"Statement too long ({len(statement)} chars, "
                f"max {cls.MAX_STATEMENT_CHARS})"
            )

        # 3. 事实主语检查
        lower_stripped = statement.strip().lower()
        has_factual_subject = any(
            lower_stripped.startswith(s) for s in cls.FACTUAL_SUBJECTS
        )
        if not has_factual_subject:
            return False, (
                f"Statement must start with a factual subject: "
                f"{', '.join(cls.FACTUAL_SUBJECTS)}"
            )

        return True, ""

    @classmethod
    def scan_for_forbidden(cls, text: str) -> list[tuple[str, str, str]]:
        """扫描文本中所有禁止词汇，返回 [(类别_en, 类别_zh, 匹配词), ...]。

        用于代码审计（扫描源文件防止人格泄露）。
        """
        hits: list[tuple[str, str, str]] = []
        lower = text.lower()
        for category_en, category_zh, words in cls.ALL_FORBIDDEN:
            for word in words:
                if word in lower:
                    hits.append((category_en, category_zh, word))
        return hits
