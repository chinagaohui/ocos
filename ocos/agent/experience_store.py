"""ExperienceStore — 结构化经验记录与重放。

经验 = <情境, 动作, 结果, 反思> 四元组。
支持基于重要性/随机/时序的重放。
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Experience:
    """一次完整经验。"""
    situation: str              # 发生了什么
    action: str                 # 做了什么
    outcome: str                # 结果如何
    reflection: str = ""        # 学到了什么
    importance: float = 0.5    # 0.0 ~ 1.0
    duration: float = 0.0      # 耗时（秒）
    tags: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    replayed_count: int = 0
    id: Optional[str] = None


class ExperienceStore:
    """经验存储与重放。"""

    def __init__(self, max_size: int = 1000,
                 replay_batch_size: int = 5):
        self._experiences: list[Experience] = []
        self._max_size = max_size
        self._replay_batch_size = replay_batch_size
        self._lock = threading.RLock()

    @property
    def total_count(self) -> int:
        with self._lock:
            return len(self._experiences)

    def record(self, situation: str, action: str, outcome: str,
               reflection: str = "",
               importance: float = 0.5,
               duration: float = 0.0,
               tags: Optional[list[str]] = None) -> str:
        """记录一次经验。超出 max_size 时淘汰最旧的。"""
        with self._lock:
            exp = Experience(
                situation=situation,
                action=action,
                outcome=outcome,
                reflection=reflection,
                importance=importance,
                duration=duration,
                tags=tags or [],
                id=f"exp-{len(self._experiences) + 1}",
            )
            self._experiences.append(exp)

            if len(self._experiences) > self._max_size:
                self._experiences.pop(0)

            return exp.id or ""

    def replay_random(self, count: Optional[int] = None) -> list[Experience]:
        """随机重放经验。"""
        with self._lock:
            n = count or self._replay_batch_size
            n = min(n, len(self._experiences))
            if n == 0:
                return []
            selected = random.sample(self._experiences, n)
            for exp in selected:
                exp.replayed_count += 1
            return selected

    def replay_recent(self, count: Optional[int] = None) -> list[Experience]:
        """按时间重放最新经验。"""
        with self._lock:
            n = count or self._replay_batch_size
            selected = self._experiences[-n:]
            for exp in selected:
                exp.replayed_count += 1
            return selected

    def replay_important(self, count: Optional[int] = None) -> list[Experience]:
        """按重要性重放最高价值经验。"""
        with self._lock:
            n = count or self._replay_batch_size
            sorted_exps = sorted(
                self._experiences,
                key=lambda x: x.importance,
                reverse=True,
            )
            selected = sorted_exps[:n]
            for exp in selected:
                exp.replayed_count += 1
            return selected

    def get_stats(self) -> dict[str, Any]:
        """获取经验统计。"""
        with self._lock:
            if not self._experiences:
                return {"total": 0, "avg_importance": 0.0,
                        "total_replays": 0}

            return {
                "total": len(self._experiences),
                "avg_importance": round(
                    sum(e.importance for e in self._experiences)
                    / len(self._experiences), 3),
                "total_replays": sum(
                    e.replayed_count for e in self._experiences),
                "avg_duration": round(
                    sum(e.duration for e in self._experiences)
                    / len(self._experiences), 3),
            }

    def clear(self) -> None:
        with self._lock:
            self._experiences.clear()
