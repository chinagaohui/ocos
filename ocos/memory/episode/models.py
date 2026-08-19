"""Phase 24.2-B — Episode Schema。

Episode = ExperienceCandidate + Significance PASS + Boundary PASS。

Episode 是经过三重门控后，获得跨时间存在资格的完整经历。

核心原则:
    Episode is not a stored experience.
    Episode is an experience that passed significance evaluation
    and is allowed to influence future cognition.

Schema 约束:
    - (What, How, Result, Why) 四元组 — 没有 Who-I-am
    - 禁止字段: self, identity, personality, value, mission
    - evaluation_trace 强制保留，供 Phase 25 Governance 审计
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── 状态枚举 ──────────────────────────────────────────────────────────────────


class EpisodeStatus(Enum):
    ACTIVE = "active"            # 当前有效的记忆
    ARCHIVED = "archived"        # 不再活跃但保留
    CONSOLIDATED = "consolidated"  # 已被聚合为 Pattern/Semantic


# ── Episode ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Episode:
    """一次完整经历的长期记忆。

    Episode 是 Phase 24 Memory 的核心单位。
    只有通过 Completion + Significance + Boundary 三重门控
    的 ExperienceCandidate 才能提升为 Episode。
    """

    # 标识
    id: str                                    # EPI-{timestamp}-{uuid}
    experience_id: str                         # 源 ExperienceCandidate ID

    # 时间
    created_at: datetime
    session_id: str = "default"

    # ── 客观事实 (What, How, Result, Why) ──
    context: dict = field(default_factory=dict)    # 环境/输入
    goal: Optional[str] = None                     # 关联目标 (GoalRef)
    decision: str = ""                              # 决策内容
    action: str = ""                                # 执行动作
    outcome: dict = field(default_factory=dict)     # 结果 {success, result, error, ...}
    condition: str = ""                             # 条件 (时间/资源/状态)

    # ── 门控结果 ──
    significance_score: float = 0.0                 # SignificanceEvaluator 加权总分
    evaluation_trace: dict = field(default_factory=dict)  # 完整评估记录 (可审计)
    source: str = "decision"                        # decision / reflection / anomaly / goal_completion

    # ── 元数据 ──
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    tags: list[str] = field(default_factory=list)


    # ── 禁止字段 ──
    # NO self_attribution
    # NO identity_impact
    # NO personality_shift
    # NO value_judgment

    # ── 工厂方法 ──

    @classmethod
    def from_candidate(
        cls,
        experience_id: str,
        context: dict,
        goal: Optional[str],
        decision: str,
        action: str,
        outcome: dict,
        condition: str,
        significance_score: float,
        evaluation_trace: dict,
        source: str = "decision",
        session_id: str = "default",
        tags: Optional[list[str]] = None,
    ) -> "Episode":
        """从 ExperienceCandidate + Significance 评估结果创建 Episode。"""
        timestamp = datetime.now(timezone.utc)
        return cls(
            id=f"EPI-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            experience_id=experience_id,
            created_at=timestamp,
            session_id=session_id,
            context=context,
            goal=goal,
            decision=decision,
            action=action,
            outcome=outcome,
            condition=condition,
            significance_score=round(significance_score, 4),
            evaluation_trace=evaluation_trace,
            source=source,
            status=EpisodeStatus.ACTIVE,
            tags=tags or [],
        )

    # ── 查询辅助 ──

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def is_active(self) -> bool:
        return self.status == EpisodeStatus.ACTIVE

    def summary(self) -> str:
        """单行摘要。"""
        goal_str = f"[{self.goal}] " if self.goal else ""
        return (
            f"Episode({self.id}) {goal_str}"
            f"score={self.significance_score:.3f} "
            f"status={self.status.value}"
        )
