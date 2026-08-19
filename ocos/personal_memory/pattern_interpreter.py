"""Phase 41: PatternInterpreter — 从统计模式到候选智慧。

Pattern ≠ Principle: 统计规律不是必然规律。
PatternInterpreter 负责:
    1. 接收 ExperiencePattern 列表
    2. 分析模式语义含义
    3. 产出 Candidate Wisdom

防止:
    - 一次经历变规则（需要证据阈值）
    - 相关性变因果性（需要因果分析）
    - 局部规律变全局原则（需要范围限定）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import ExperiencePattern
from ocos.personal_memory.wisdom_types import (
    WisdomItem,
    WisdomState,
    WisdomScope,
    WisdomEvidence,
)


@dataclass
class InterpretationResult:
    """单次解释的结果。"""

    pattern: ExperiencePattern
    candidate_wisdom: Optional[WisdomItem]
    reasoning: str
    rejected: bool = False
    reject_reason: str = ""


@dataclass
class PatternInterpreter:
    """从统计模式推导候选智慧。

    不是通用推理引擎，而是专门针对 ExperiencePattern → Wisdom 的转化。

    约束:
        - 单个模式不能直接成为智慧
        - 需要相似模式的聚集
        - 区分成功模式和失败模式的不同含义
    """

    # ── 配置 ──

    min_patterns_for_wisdom: int = 2
    """最少需要多少个相似模式才能形成候选智慧。"""

    min_frequency: int = 3
    """单模式最少出现次数。"""

    max_wisdom_length: int = 200
    """智慧原则最大长度（字符数）。"""

    # ── 解释 ──

    def interpret(
        self,
        patterns: list[ExperiencePattern],
        current_tick: int,
    ) -> list[InterpretationResult]:
        """将一组 ExperiencePattern 解释为候选智慧。

        一次调用只处理同 category (successful/failure) 的 patterns。
        调用方负责分类分组。
        """
        results: list[InterpretationResult] = []

        if not patterns:
            return results

        # 按类别分组
        category = patterns[0].category
        if category not in ("successful", "failure"):
            # Neutral patterns 不产生 wisdom
            return [InterpretationResult(
                pattern=p,
                candidate_wisdom=None,
                reasoning="Neutral patterns do not produce wisdom.",
                rejected=True,
                reject_reason="neutral_category",
            ) for p in patterns]

        # 数量不足 → 全部拒绝
        if len(patterns) < self.min_patterns_for_wisdom:
            for p in patterns:
                results.append(InterpretationResult(
                    pattern=p,
                    candidate_wisdom=None,
                    reasoning=f"Need at least {self.min_patterns_for_wisdom} "
                              f"similar patterns, got {len(patterns)}.",
                    rejected=True,
                    reject_reason="insufficient_patterns",
                ))
            return results

        # 频次不足 → 拒绝单个
        qualified = [p for p in patterns if p.frequency >= self.min_frequency]
        rejected_low_freq = [p for p in patterns if p.frequency < self.min_frequency]

        for p in rejected_low_freq:
            results.append(InterpretationResult(
                pattern=p,
                candidate_wisdom=None,
                reasoning=f"Frequency {p.frequency} < min {self.min_frequency}.",
                rejected=True,
                reject_reason="low_frequency",
            ))

        if len(qualified) < self.min_patterns_for_wisdom:
            return results  # 不够形成 wisdom

        # 从合格 patterns 推导 wisdom
        principle_text = self._derive_principle(qualified, category)

        wisdom_id = f"wisdom-{category}-{current_tick}-{len(qualified)}"
        candidate = WisdomItem(
            wisdom_id=wisdom_id,
            principle=principle_text,
            state=WisdomState.CANDIDATE,
            source_patterns=tuple(p.pattern_id for p in qualified),
            evidence=[
                WisdomEvidence(
                    evidence_id=f"ev-{p.pattern_id}",
                    source_type="pattern",
                    source_id=p.pattern_id,
                    supports=True if category == "successful" else False,
                    strength=p.confidence,
                    tick_id=p.abstracted_at_tick,
                    note=f"Source pattern: {p.label}",
                )
                for p in qualified
            ],
            scope=self._infer_scope(qualified),
            created_tick=current_tick,
        )

        # 为每个 qualified pattern 创建结果
        for p in qualified:
            results.append(InterpretationResult(
                pattern=p,
                candidate_wisdom=candidate,
                reasoning=f"Derived from {len(qualified)} qualified {category} patterns.",
            ))

        return results

    # ── 内部方法 ──

    def _derive_principle(
        self,
        patterns: list[ExperiencePattern],
        category: str,
    ) -> str:
        """从多个模式中提取原则表述。"""
        # 聚合标签
        labels = [p.label for p in patterns]
        label_summary = ", ".join(labels[:3])
        if len(labels) > 3:
            label_summary += f" (and {len(labels) - 3} more)"

        total_freq = sum(p.frequency for p in patterns)
        avg_confidence = sum(p.confidence for p in patterns) / len(patterns)

        if category == "successful":
            return (
                f"In contexts involving {label_summary}, "
                f"the approach is consistently effective "
                f"(observed across {total_freq} instances, "
                f"confidence {avg_confidence:.2f})."
            )
        else:
            return (
                f"In contexts involving {label_summary}, "
                f"the approach tends to be ineffective "
                f"(observed across {total_freq} instances, "
                f"confidence {avg_confidence:.2f})."
            )

    def _infer_scope(self, patterns: list[ExperiencePattern]) -> WisdomScope:
        """从模式标签推断适用范围。"""
        all_notes = [p.note for p in patterns if p.note]
        labels = set(p.label for p in patterns)

        return WisdomScope(
            domains=tuple(sorted(labels)) if len(labels) <= 3 else (),
            conditions=(),
            exclusions=(),
            user_scope="current_user",
        )


__all__ = ["PatternInterpreter", "InterpretationResult"]
