"""Phase 53: InteractionScheduler — 管理交互候选的发送节奏。

核心职责:
    - 速率限制: 不超过 max_interactions_per_hour
    - 冷却: 两次交互间至少 cooldown_seconds
    - 队列管理: CRITICAL 优先于 HIGH 优先于 MEDIUM
    - 自动撤回: 过期未读的交互
    - 去重: 同源同类信号不重复发送

IS53-03: 每次发送前必须经过验证。
IS53-04: 速率限制防止骚扰。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import OrderedDict
import time as _time
from typing import Iterator

from ocos.interaction.interaction_types import (
    InteractionCandidate, InteractionStatus, InteractionPriority,
    InteractionMode, InteractionConfig, InteractionHistory, NeedSignal,
)


@dataclass
class InteractionScheduler:
    """交互调度器 — OCOS 的"发声节奏控制器"。

    类似人:
        有很多话想说 → 但不能一次说完 → 选最重要、最紧急的先说。
    """

    config: InteractionConfig = field(default_factory=InteractionConfig)
    history: InteractionHistory = field(default_factory=InteractionHistory)

    # 队列: id → InteractionCandidate
    _pending: OrderedDict[str, InteractionCandidate] = field(default_factory=OrderedDict)
    _dequeue_order: OrderedDict[str, InteractionCandidate] = field(default_factory=OrderedDict)
    _sent: OrderedDict[str, InteractionCandidate] = field(default_factory=OrderedDict)

    # 速率追踪
    _hourly_window: list[float] = field(default_factory=list)
    _critical_hourly: list[float] = field(default_factory=list)

    # 去重: (NeedType, source) → timestamp
    _dedup_map: dict[tuple[str, str], float] = field(default_factory=dict)

    def submit(self, candidate: InteractionCandidate) -> bool:
        """提交交互候选到队列。

        返回:
            True — 接受并加入队列
            False — 被拒绝 (去重/速率限制)
        """
        now = _time.time()

        # 去重
        if candidate.need:
            dedup_key = (candidate.need.need_type.value, candidate.need.source)
            last = self._dedup_map.get(dedup_key, 0)
            if now - last < self.config.dedup_seconds:
                candidate.status = InteractionStatus.WITHDRAWN
                candidate.metadata["withdraw_reason"] = "dedup"
                return False

        # 加入队列
        candidate.id = candidate.id or f"int-{now}-{hash(candidate.title)}"
        candidate.status = InteractionStatus.PENDING
        self._pending[candidate.id] = candidate
        if candidate.need:
            dedup_key = (candidate.need.need_type.value, candidate.need.source)
            self._dedup_map[dedup_key] = now

        return True

    def dequeue(self, max_count: int = 1) -> list[InteractionCandidate]:
        """从队列取出可发送的交互。

        按优先级排序: CRITICAL > HIGH > MEDIUM > LOW。
        检查速率限制。
        """
        if not self._pending:
            return []

        now = _time.time()
        self._clean_expired(now)
        self._prune_hourly_window(now)

        # 按优先级排序
        sorted_candidates = sorted(
            self._pending.values(),
            key=lambda c: self._priority_order(c.priority),
        )

        results: list[InteractionCandidate] = []
        for candidate in sorted_candidates:
            if len(results) >= max_count:
                break

            # 速率检查
            if not self._can_send(candidate, now):
                continue

            # 发送
            candidate.mark_sent()
            self._sent[candidate.id] = candidate
            del self._pending[candidate.id]
            self._record_sent(candidate, now)
            results.append(candidate)

        return results

    def withdraw(self, candidate_id: str, reason: str = "") -> bool:
        """撤回一个已发送但未被确认的交互。"""
        if candidate_id in self._sent:
            c = self._sent[candidate_id]
            if c.status == InteractionStatus.SENT:
                c.withdraw(reason)
                self.history.total_withdrawn += 1
                return True
        return False

    def acknowledge(self, candidate_id: str, response: str = "") -> bool:
        """用户确认交互。"""
        if candidate_id in self._sent:
            self._sent[candidate_id].acknowledge(response)
            self.history.total_acknowledged += 1
            return True
        return False

    def ignore(self, candidate_id: str) -> bool:
        """标记为被忽略。"""
        if candidate_id in self._sent:
            self._sent[candidate_id].ignore()
            self.history.total_ignored += 1
            return True
        return False

    def has_pending(self) -> bool:
        return len(self._pending) > 0

    def pending_count(self) -> int:
        return len(self._pending)

    def get_pending(self) -> list[InteractionCandidate]:
        return list(self._pending.values())

    def get_sent(self) -> list[InteractionCandidate]:
        return list(self._sent.values())

    # ——— 内部方法 ———

    def _priority_order(self, p: InteractionPriority) -> int:
        order = {
            InteractionPriority.CRITICAL: 0,
            InteractionPriority.HIGH: 1,
            InteractionPriority.MEDIUM: 2,
            InteractionPriority.LOW: 3,
        }
        return order.get(p, 4)

    def _can_send(self, candidate: InteractionCandidate, now: float) -> bool:
        # 总数限制
        if len(self._hourly_window) >= self.config.max_interactions_per_hour:
            return False

        # CRITICAL 限制
        if candidate.priority == InteractionPriority.CRITICAL:
            if len(self._critical_hourly) >= self.config.max_critical_per_hour:
                return False

        # 冷却
        if self.history.last_sent_at > 0:
            if now - self.history.last_sent_at < self.config.cooldown_seconds:
                return False

        return True

    def _record_sent(self, candidate: InteractionCandidate, now: float) -> None:
        self._hourly_window.append(now)
        if candidate.priority == InteractionPriority.CRITICAL:
            self._critical_hourly.append(now)
        self.history.last_sent_at = now
        self.history.total_sent += 1

    def _prune_hourly_window(self, now: float) -> None:
        cutoff = now - 3600
        self._hourly_window = [t for t in self._hourly_window if t > cutoff]
        self._critical_hourly = [t for t in self._critical_hourly if t > cutoff]

    def _clean_expired(self, now: float) -> None:
        expired = [
            cid for cid, c in self._pending.items()
            if c.is_expired(now)
        ]
        for cid in expired:
            self._pending[cid].status = InteractionStatus.WITHDRAWN
            self._pending[cid].metadata["withdraw_reason"] = "expired"
            self._sent[cid] = self._pending.pop(cid)
            self.history.total_withdrawn += 1

    def get_state(self) -> dict:
        return {
            "total_sent": self.history.total_sent,
            "total_acknowledged": self.history.total_acknowledged,
            "total_ignored": self.history.total_ignored,
            "pending_count": self.pending_count(),
        }


__all__ = ["InteractionScheduler"]
