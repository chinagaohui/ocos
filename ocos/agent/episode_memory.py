"""EpisodeMemory — 情景记忆。

记录 Agent 经历过的有意义的片段（Episode）。
每个 Episode 包含事件序列、上下文和情感标记。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Episode:
    """情景片段。"""
    episode_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    summary: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    importance: float = 1.0          # 重要性 0-10
    emotional_mark: Optional[str] = None  # "positive" / "negative" / "neutral"
    archived: bool = False


class EpisodeMemory:
    """情景记忆存储。

    管理 Agent 的经历片段。
    Phase 24 将接入持久化存储。
    """

    def __init__(self, max_episodes: int = 100):
        self._episodes: list[Episode] = []
        self._max_episodes = max_episodes

    def record(self, episode: Episode) -> str:
        """记录一个情景。"""
        self._episodes.append(episode)
        # 超出容量时归档最不重要的
        if len(self._episodes) > self._max_episodes:
            least_important = min(self._episodes, key=lambda e: e.importance)
            least_important.archived = True
        return episode.episode_id

    def recall(self, query: str | None = None, limit: int = 10) -> list[Episode]:
        """回忆情景。"""
        if not query:
            return self._episodes[:limit]

        query_lower = query.lower()
        results = []
        for ep in self._episodes:
            if query_lower in ep.title.lower() or query_lower in ep.summary.lower():
                results.append(ep)
                if len(results) >= limit:
                    break
        return results

    def recall_recent(self, n: int = 5) -> list[Episode]:
        """回忆最近 N 个情景。"""
        return self._episodes[-n:]

    def recall_important(self, threshold: float = 5.0) -> list[Episode]:
        """回忆高于重要性阈值的情景。"""
        return [e for e in self._episodes if e.importance >= threshold and not e.archived]

    def count(self) -> int:
        return len(self._episodes)

    def clear(self) -> None:
        self._episodes.clear()
