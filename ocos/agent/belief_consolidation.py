"""P1-A — Episode → Belief 迁移轨迹（CLS 慢系统写路径）。

将 EpisodeStore 中最近的 Episode 巩固为持久化 Belief：
    Episode → Evidence(source_episode_id) → Belief(evidence_ids) → hub.belief.save()

设计约束（确定性规则优先）:
    - statement 由 Episode 的 action/decision 机械构造，
      保证经 StatementValidator 事实主语门控（六类禁止词仍会被拒）。
    - 幂等: 已存在引用同一 Episode 的 Belief 则跳过（不重复巩固）。
    - 只读不删: 不 archive / 不修改 Episode。

用法:
    from ocos.agent.belief_consolidation import consolidate_episodes
    records = consolidate_episodes(hub, limit=20)
    # [ConsolidationRecord(episode_id, belief_id, status, reason), ...]
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ocos.memory.hub import MemoryHub
from ocos.self.statement_validator import StatementValidator


@dataclass(frozen=True)
class ConsolidationRecord:
    """单条 Episode → Belief 迁移轨迹记录（可审计）。"""

    episode_id: str
    belief_id: str            # 空字符串 = 未生成 Belief
    status: str               # consolidated / skipped_rejected / skipped_duplicate
    reason: str = ""


def _statement_from_episode(episode) -> str:
    """从 Episode 构造符合事实主语门控的信念陈述。"""
    raw = (episode.action or episode.decision or "").strip()
    if not raw:
        return ""
    statement = f"当前系统 {raw}"
    if len(statement) > StatementValidator.MAX_STATEMENT_CHARS:
        statement = statement[: StatementValidator.MAX_STATEMENT_CHARS - 1] + "…"
    return statement


def consolidate_episodes(
    hub: MemoryHub,
    limit: int = 20,
    min_confidence: float = 0.6,
) -> list[ConsolidationRecord]:
    """将最近 limit 条 Active Episode 巩固为 Belief。

    返回 ConsolidationRecord 列表 — 即验收所需的「迁移轨迹」。
    """
    records: list[ConsolidationRecord] = []
    if not hub.is_initialized():
        return records

    episodes = hub.episode.query_by_time(limit=limit, active_only=True)
    if not episodes:
        return records

    # 已巩固的 Episode id 集合（幂等检查: 扫 active beliefs 的 evidence 溯源）
    consolidated_episode_ids: set[str] = set()
    for b in hub.belief.get_all_active(limit=500):
        for evd_id in b.evidence_ids:
            if evd_id.startswith("EVD-"):
                pass
            # evidence_ids 存的是 Evidence id，溯源 episode 需查 Evidence —— 简化:
            # 用 source_knowledge_ids 冗余标记（见下），此处直接扫证据字段不可行，
            # 改为按 scope.preconditions 中记录的 episode 溯源。
        # scope 冗余溯源: {"domain":..., "preconditions":..., "_trail": [episode_id,...]}
        trail = b.scope.get("_trail") if isinstance(b.scope, dict) else None
        if trail:
            consolidated_episode_ids.update(trail)

    for ep in episodes:
        if ep.id in consolidated_episode_ids:
            records.append(
                ConsolidationRecord(ep.id, "", "skipped_duplicate",
                                    "already consolidated")
            )
            continue

        statement = _statement_from_episode(ep)
        valid, reason = StatementValidator.validate(statement)
        if not valid:
            records.append(
                ConsolidationRecord(ep.id, "", "skipped_rejected", reason)
            )
            continue

        from ocos.memory.belief.models import Belief, Evidence

        conf = round(min(0.95, max(min_confidence, ep.significance_score)), 4)
        evd = Evidence.create(
            source_episode_id=ep.id,
            source_pattern_id="",
            quality=conf,
        )
        scope = {
            "domain": f"episode:{ep.source}",
            "preconditions": ep.condition or "",
            "_trail": [ep.id],
        }
        belief = Belief.create(
            statement=statement,
            source_knowledge_ids=[],
            evidence_ids=[evd.id],
            confidence=conf,
            uncertainty=round(1.0 - conf, 4),
            scope=scope,
        )
        hub.belief.save(belief)
        records.append(
            ConsolidationRecord(ep.id, belief.id, "consolidated",
                                f"evidence={evd.id}")
        )

    return records
