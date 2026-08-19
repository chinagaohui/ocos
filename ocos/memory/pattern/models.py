"""Phase 24.3-A — Pattern 数据模型。

PatternCandidate: 从多个 Episode 中提取的候选 Pattern。
    冻结约束:
        - 不含 self/identity/personality/value 字段
        - 不引用具体 Episode ID (只保留计数)
        - 使用第三人称客观描述

Pattern: 经过 Validator 审核的正式 Pattern。
    继承 PatternCandidate 所有字段，额外包含:
        - validated_at: 验证时间戳
        - abstraction_score: 抽象程度评分
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class PatternStatus(Enum):
    CANDIDATE = "candidate"    # 提取中，未验证
    VALIDATED = "validated"    # 通过 Validator 审核
    REJECTED = "rejected"      # 被拒绝 (Self 泄露 / 无因果)


@dataclass(frozen=True)
class PatternCandidate:
    """从 Episode 集合中提取的候选 Pattern。

    Pattern 描述"世界如何运行"，而非"系统是什么"。

    约束:
        - 不引用 Episode ID (只保留计数)
        - 不含 self/identity/personality/value
        - 必须包含 trigger_condition + observed_relation
    """

    id: str
    trigger_condition: str       # 触发条件: "并发 > 80"
    observed_relation: str        # 观察到关系: "方案 A → 超时概率增加"
    causal_explanation: str       # 因果解释: "方案 A 的连接池在高并发下耗尽"
    confidence: float             # 置信度 [0.0, 1.0]
    supporting_episode_count: int # 支持的 Episode 数量
    source: str = "episode_aggregation"  # episode_aggregation / single_anomaly
    status: PatternStatus = PatternStatus.CANDIDATE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 禁止字段:
    # NO owner
    # NO identity_impact
    # NO personality_relevance
    # NO value_judgment

    @classmethod
    def create(
        cls,
        trigger_condition: str,
        observed_relation: str,
        causal_explanation: str,
        confidence: float,
        supporting_episode_count: int,
        source: str = "episode_aggregation",
    ) -> "PatternCandidate":
        timestamp = datetime.now(timezone.utc)
        return cls(
            id=f"PAT-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            trigger_condition=trigger_condition,
            observed_relation=observed_relation,
            causal_explanation=causal_explanation,
            confidence=round(confidence, 4),
            supporting_episode_count=supporting_episode_count,
            source=source,
            status=PatternStatus.CANDIDATE,
            created_at=timestamp,
        )

    @property
    def is_validated(self) -> bool:
        return self.status == PatternStatus.VALIDATED

    @property
    def is_rejected(self) -> bool:
        return self.status == PatternStatus.REJECTED

    def summary(self) -> str:
        return (
            f"Pattern({self.id}): "
            f"IF {self.trigger_condition} "
            f"THEN {self.observed_relation} "
            f"(n={self.supporting_episode_count}, conf={self.confidence:.3f})"
        )


@dataclass(frozen=True)
class Pattern:
    """通过 Validator 审核的正式 Pattern。

    相比 PatternCandidate 增加:
        - validated_at: 验证时间戳
        - abstraction_score: 抽象程度 [0.0, 1.0]
    """

    candidate: PatternCandidate
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validation_notes: str = ""

    @property
    def id(self) -> str:
        return self.candidate.id

    @property
    def trigger_condition(self) -> str:
        return self.candidate.trigger_condition

    @property
    def observed_relation(self) -> str:
        return self.candidate.observed_relation

    @property
    def confidence(self) -> float:
        return self.candidate.confidence

    def summary(self) -> str:
        return f"Pattern({self.id}) [validated] " + self.candidate.summary().split(": ", 1)[1]
