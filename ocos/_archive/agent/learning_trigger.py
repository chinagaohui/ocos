# ARCHIVED（收敛裁决 P1，2026-09-08）— 本模块已冻结归档，非生产代码。
# 依据: docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md（FROZEN DECISION）
# 禁止从生产路径 import 本模块（违冻条款见来源文档第七节）。

"""P1-A — learning_trigger: Episode 聚合 → Pattern 写路径。

确定性规则（零 LLM）:
    将最近 window 条 Active Episode 按 (condition, action) 分组，
    同组出现次数 ≥ min_support 时，生成 PatternCandidate 写入 hub.pattern。

设计约束:
    - 幂等: 已存在同 observed_relation 的 CANDIDATE pattern 则跳过。
    - 只读不删: 不修改 Episode。

用法:
    from ocos.agent.learning_trigger import scan_for_patterns
    created = scan_for_patterns(hub, min_support=3)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ocos.memory.hub import MemoryHub


@dataclass(frozen=True)
class PatternTriggerRecord:
    """单次 Pattern 触发记录（可审计）。"""

    pattern_id: str            # 空字符串 = 未生成
    relation: str
    support: int               # 命中 episode 数
    status: str                # created / skipped_duplicate
    reason: str = ""


def _group_key(episode) -> str:
    """聚合键: condition + action（condition 空则 default）。"""
    condition = (episode.condition or "").strip() or "default"
    action = (episode.action or episode.decision or "").strip()
    return f"{condition}|{action}"


def _observed_relation(condition: str, action: str) -> str:
    return f"条件[{condition}] → 动作[{action}] 重复出现"


def scan_for_patterns(
    hub: MemoryHub,
    min_support: int = 3,
    window: int = 50,
) -> list[PatternTriggerRecord]:
    """扫描最近 window 条 Episode，聚合出重复 (condition, action) 模式。

    返回触发记录列表；达到 min_support 的组生成 PatternCandidate 并持久化。
    """
    records: list[PatternTriggerRecord] = []
    if not hub.is_initialized() or min_support < 1:
        return records

    episodes = hub.episode.query_by_time(limit=window, active_only=True)
    if not episodes:
        return records

    from ocos.memory.pattern.models import PatternStatus

    # 已存在的 CANDIDATE pattern relation 集合（幂等）
    existing_relations: set[str] = {
        p.observed_relation
        for p in hub.pattern.query_by_status(PatternStatus.CANDIDATE)
    }

    # 按 (condition, action) 分组
    groups: dict[str, list] = {}
    for ep in episodes:
        key = _group_key(ep)
        groups.setdefault(key, []).append(ep)

    for key, eps in groups.items():
        count = len(eps)
        if count < min_support:
            continue
        condition, action = key.split("|", 1)
        relation = _observed_relation(condition, action)
        if relation in existing_relations:
            records.append(
                PatternTriggerRecord("", relation, count,
                                     "skipped_duplicate", "pattern exists")
            )
            continue

        from ocos.memory.pattern.models import PatternCandidate

        candidate = PatternCandidate.create(
            trigger_condition=f"同条件同动作 episode 出现 {count} 次",
            observed_relation=relation,
            causal_explanation="episode 聚合（确定性规则，零 LLM）",
            confidence=round(min(0.9, 0.5 + count * 0.1), 4),
            supporting_episode_count=count,
            source=f"learning_trigger:{eps[0].source}",
        )
        hub.pattern.save(candidate)
        records.append(
            PatternTriggerRecord(candidate.id, relation, count,
                                 "created", "min_support reached")
        )

    return records
