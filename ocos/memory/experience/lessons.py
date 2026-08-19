"""Phase 21 — LessonsLearned: 从 ExperienceCandidate 综合教训。

LessonsLearned 不同于 Episode（事实记忆），它是跨经验的归纳结论。
存储方式：复用 EpisodeStore（source="lesson", tags=["synthesized"]），零新表。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ocos.memory.episode.models import Episode, EpisodeStatus
from ocos.memory.experience.models import ExperienceCandidate


@dataclass(frozen=True)
class LessonsLearned:
    """从多项经历中归纳的行为教训。

    Episode = 事实记忆 ("what happened")
    LessonsLearned = 归纳结论 ("what we should do differently next time")

    约束:
      - 不包含 Self 字段（identity, personality, value）
      - source_experiences 可审计追溯
    """

    id: str
    description: str           # 教训："当输入模糊时，先澄清再行动"
    category: str              # success_pattern | failure_pattern | conditional_insight
    confidence: float          # [0.0, 1.0] — 多少条经验支持这个教训
    source_experiences: list[str]  # ExperienceCandidate.id[]，可审计
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 结构化的 What / How / Result
    condition: str = ""        # 什么环境下教训成立
    action: str = ""           # 涉及的动作
    outcome: str = ""          # 预期结果

    # ── 转 Episode ──────────────────────────────────────────────────────

    def to_episode(
        self,
        session_id: str = "default",
        significance_score: float = 0.7,
    ) -> Episode:
        """转为 Episode 对象，可存入 EpisodeStore。

        Episode field mapping:
          - context: 条件 + 来源经历
          - goal: None (教训是元级别)
          - decision: self.description
          - action: self.action
          - outcome: {"predicted": self.outcome}
          - condition: self.condition
          - source: "lesson"
          - tags: ["synthesized", self.category]
        """
        return Episode(
            id=self.id,
            experience_id=f"LESSON-{self.id}",
            created_at=self.created_at,
            session_id=session_id,
            context={
                "lesson_type": self.category,
                "source_experiences": self.source_experiences,
            },
            goal=None,
            decision=self.description,
            action=self.action,
            outcome={"predicted": self.outcome, "confidence": self.confidence},
            condition=self.condition,
            significance_score=significance_score,
            evaluation_trace={
                "synthesizer_version": "phase21",
                "source_count": len(self.source_experiences),
            },
            source="lesson",
            tags=["synthesized", self.category],
        )

    # ── 摘要 ────────────────────────────────────────────────────────────

    def summary(self) -> str:
        cat_emoji = {
            "success_pattern": "✅",
            "failure_pattern": "❌",
            "conditional_insight": "🔍",
        }
        return (
            f"{cat_emoji.get(self.category, '📝')} "
            f"Lesson({self.id[:8]}): {self.description[:80]} "
            f"[conf={self.confidence:.2f}]"
        )


# ── LessonsSynthesizer ──────────────────────────────────────────────────────


class LessonsSynthesizer:
    """从 ExperienceCandidate 列表中综合教训。

    算法:
      1. 分组: success / failure
      2. 同组: 按 context keys 聚类
      3. 生成: success_pattern / failure_pattern / conditional_insight

    这是一个基于规则的简单合成器，Phase 21 版本。
    未来可升级为 LLM 驱动的合成。
    """

    def synthesize(
        self,
        candidates: list[ExperienceCandidate],
        min_confidence: float = 0.3,
        max_lessons: int = 10,
    ) -> list[LessonsLearned]:
        """从候选经验中合成教训。"""
        if len(candidates) < 2:
            return []  # 至少需要 2 条经验才能对比

        timestamp = datetime.now(timezone.utc)
        lessons: list[LessonsLearned] = []

        # 分组
        success_group = _group_by_success(candidates)
        by_goal = _group_by_goal(candidates)

        # 1. 成功模式: 什么条件下成功了？
        for goal_ref, group in by_goal.items():
            successes = [c for c in group if _outcome_bool(c) is True]
            if len(successes) >= 2:
                lesson = _extract_success_pattern(
                    successes, goal_ref, timestamp, min_confidence
                )
                if lesson:
                    lessons.append(lesson)

        # 2. 失败模式: 什么条件下失败了？
        for goal_ref, group in by_goal.items():
            failures = [c for c in group if _outcome_bool(c) is False]
            if len(failures) >= 2:
                lesson = _extract_failure_pattern(
                    failures, goal_ref, timestamp, min_confidence
                )
                if lesson:
                    lessons.append(lesson)

        # 3. 条件洞察: 同类 context + 不同动作 → 不同结果
        for goal_ref, group in by_goal.items():
            if len(group) < 2:
                continue
            paired = _pair_by_context_similarity(group)
            for c1, c2 in paired:
                o1 = _outcome_bool(c1)
                o2 = _outcome_bool(c2)
                if o1 is not None and o2 is not None and o1 != o2:
                    lesson = _extract_conditional_insight(
                        c1, c2, goal_ref, timestamp, min_confidence
                    )
                    if lesson:
                        lessons.append(lesson)

        # 去重（按 description 近似去重）
        seen: set[str] = set()
        unique: list[LessonsLearned] = []
        for l in lessons:
            key = l.description[:60]
            if key not in seen:
                seen.add(key)
                unique.append(l)

        # 限制数量
        return unique[:max_lessons]


# ── 辅助函数 ────────────────────────────────────────────────────────────────


def _outcome_bool(candidate: ExperienceCandidate) -> bool | None:
    """提取 ExperienceCandidate 的 outcome 布尔值。"""
    tb = candidate.trace_bundle
    outcome = tb.outcome
    if isinstance(outcome, dict):
        if "success" in outcome:
            return bool(outcome["success"])
    return None


def _group_by_success(
    candidates: list[ExperienceCandidate],
) -> dict[bool | None, list[ExperienceCandidate]]:
    result: dict[bool | None, list[ExperienceCandidate]] = {}
    for c in candidates:
        key = _outcome_bool(c)
        result.setdefault(key, []).append(c)
    return result


def _group_by_goal(
    candidates: list[ExperienceCandidate],
) -> dict[str, list[ExperienceCandidate]]:
    """按 trace_bundle.goal_context 中的 goal_id 分组。"""
    result: dict[str, list[ExperienceCandidate]] = {}
    for c in candidates:
        gc = c.trace_bundle.goal_context or {}
        goal_id = gc.get("goal_id", gc.get("id", "_unknown"))
        key = str(goal_id)
        result.setdefault(key, []).append(c)
    return result


def _extract_success_pattern(
    successes: list[ExperienceCandidate],
    goal_ref: str,
    timestamp: datetime,
    min_confidence: float,
) -> LessonsLearned | None:
    """从成功经验中提取模式。"""
    confidence = min(1.0, len(successes) / max(5, len(successes)))
    if confidence < min_confidence:
        return None

    # 提取共性 context keys 和 action
    contexts = [_ctx_keys(c) for c in successes]
    common_ctx = _intersect_keys(contexts)
    actions = [_action_str(c) for c in successes]
    common_action = _most_common(actions) if actions else "unknown_action"

    source_ids = [c.id for c in successes]
    ctx_str = ", ".join(sorted(common_ctx)[:5]) if common_ctx else "similar_context"

    return LessonsLearned(
        id=f"LESSON-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        description=f"在 [{goal_ref}] 中，{ctx_str} 条件下 {common_action} 通常成功",
        category="success_pattern",
        confidence=round(confidence, 2),
        source_experiences=source_ids,
        created_at=timestamp,
        condition=f"context keys: {ctx_str}" if common_ctx else "",
        action=common_action,
        outcome="success",
    )


def _extract_failure_pattern(
    failures: list[ExperienceCandidate],
    goal_ref: str,
    timestamp: datetime,
    min_confidence: float,
) -> LessonsLearned | None:
    """从失败经验中提取模式。"""
    confidence = min(1.0, len(failures) / max(5, len(failures)))
    if confidence < min_confidence:
        return None

    contexts = [_ctx_keys(c) for c in failures]
    common_ctx = _intersect_keys(contexts)
    actions = [_action_str(c) for c in failures]
    common_action = _most_common(actions) if actions else "unknown_action"
    source_ids = [c.id for c in failures]

    # 提取 error 信息
    errors = []
    for c in failures:
        outcome = c.trace_bundle.outcome
        if isinstance(outcome, dict):
            err = outcome.get("error", outcome.get("result", ""))
            if err:
                errors.append(str(err))
    error_summary = _most_common(errors) if errors else "repeated failure"

    ctx_str = ", ".join(sorted(common_ctx)[:5]) if common_ctx else "similar_context"

    return LessonsLearned(
        id=f"LESSON-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        description=f"在 [{goal_ref}] 中，{ctx_str} 条件下 {common_action} 常失败: {error_summary}",
        category="failure_pattern",
        confidence=round(confidence, 2),
        source_experiences=source_ids,
        created_at=timestamp,
        condition=f"context keys: {ctx_str}" if common_ctx else "",
        action=common_action,
        outcome=f"failure: {error_summary}",
    )


def _extract_conditional_insight(
    c1: ExperienceCandidate,
    c2: ExperienceCandidate,
    goal_ref: str,
    timestamp: datetime,
    min_confidence: float,
) -> LessonsLearned | None:
    """同 goal、不同动作 → 不同结果的洞察。"""
    a1, a2 = _action_str(c1), _action_str(c2)
    if a1 == a2:
        return None  # 动作相同，不是条件差异

    o1_ok = _outcome_bool(c1) is True
    o2_ok = _outcome_bool(c2) is True

    better = c1 if o1_ok else c2
    worse = c2 if o1_ok else c1

    return LessonsLearned(
        id=f"LESSON-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        description=f"[{goal_ref}]: 当 {a1} vs {a2} 时，"
                     f"{_action_str(better)} 优于 {_action_str(worse)}",
        category="conditional_insight",
        confidence=0.5,
        source_experiences=[c1.id, c2.id],
        created_at=timestamp,
        condition=f"goal={goal_ref}, action_comparison",
        action=f"{_action_str(better)} > {_action_str(worse)}",
        outcome="conditional_preference",
    )


# ── 低级辅助 ────────────────────────────────────────────────────────────────


def _ctx_keys(candidate: ExperienceCandidate) -> set[str]:
    """提取 context 中的键。"""
    ctx = candidate.trace_bundle.goal_context or {}
    return set(k for k in ctx.keys() if k not in ("goal_id", "id", "timestamp"))


def _action_str(candidate: ExperienceCandidate) -> str:
    """提取动作字符串。"""
    ar = candidate.trace_bundle.action_result
    if isinstance(ar, dict):
        return str(ar.get("action", ar.get("type", "unknown")))
    return str(ar)[:50]


def _pair_by_context_similarity(
    candidates: list[ExperienceCandidate],
) -> list[tuple[ExperienceCandidate, ExperienceCandidate]]:
    """将同组中 context 相似的候选两两配对。"""
    if len(candidates) < 2:
        return []
    pairs: list[tuple[ExperienceCandidate, ExperienceCandidate]] = []
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            ki = _ctx_keys(candidates[i])
            kj = _ctx_keys(candidates[j])
            if ki and kj and len(ki & kj) >= max(1, min(len(ki), len(kj)) // 2):
                pairs.append((candidates[i], candidates[j]))
    return pairs


def _intersect_keys(sets: list[set[str]]) -> set[str]:
    """求交集。"""
    if not sets:
        return set()
    result = sets[0].copy()
    for s in sets[1:]:
        result &= s
    return result


def _most_common(items: list[str]) -> str:
    """返回出现次数最多的项。"""
    if not items:
        return ""
    from collections import Counter
    return Counter(items).most_common(1)[0][0]
