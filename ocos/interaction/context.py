"""OCOS InteractionContext — 将内核 Store 接入 Interaction Layer。

责任:
    为 CLI / REPL / API 提供统一的 Store 注入点。
    所有 Store 只读，符合 Interaction Layer 权限边界。

设计:
    - 惰性初始化：首次查询时才创建连接
    - 共享 DB：所有 Store 共用同一个 db_path
    - 长连接：REPL 和 API 服务器持有单一上下文
    - Stateless：CLI 每次调用创建新上下文（用完即弃）

用法:
    ctx = InteractionContext(db_path="ocos.db")
    ctx.ensure_episode_store()
    episodes = ctx.episode_store.query_by_time(limit=10)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from ocos.memory.episode.store import EpisodeStore
from ocos.memory.belief.store import BeliefStore
from ocos.self.identity_boundary import IdentityBoundary
from ocos.memory.belief.models import BeliefStatus


class InteractionContext:
    """Interaction Layer 上下文——内核 Store 的统一注入器。

    所有交互入口（CLI、REPL、API）通过此上下文只读访问内核数据。
    入口层不能写入：没有 save() 暴露。

    Properties:
        episode_store  — Episode 查询（by goal, time, significance, tag）
        belief_store   — Belief 查询（by status, confidence, domain）
        identity       — IdentityBoundary 只读快照
    """

    def __init__(self, db_path: str | Path | None = None):
        """初始化上下文。

        Args:
            db_path: SQLite 数据库路径。
                     None → 使用 OCOS_DB_PATH 环境变量或 `:memory:`
                     推荐 REPL/API 使用 "ocos.db"
        """
        if db_path is None:
            db_path = os.environ.get("OCOS_DB_PATH", ":memory:")
        self.db_path = str(db_path)

        # 惰性初始化
        self._episode_store: Optional[EpisodeStore] = None
        self._belief_store: Optional[BeliefStore] = None
        self._identity: Optional[IdentityBoundary] = None

    # ── Episode ──────────────────────────────────────────────────────

    def ensure_episode_store(self) -> EpisodeStore:
        """确保 EpisodeStore 已初始化（惰性）。"""
        if self._episode_store is None:
            self._episode_store = EpisodeStore(self.db_path)
            self._episode_store.initialize()
        return self._episode_store

    @property
    def episode_store(self) -> EpisodeStore:
        """Episode 存储（只读查询）。"""
        return self.ensure_episode_store()

    # ── Belief ───────────────────────────────────────────────────────

    def ensure_belief_store(self) -> BeliefStore:
        """确保 BeliefStore 已初始化（惰性）。"""
        if self._belief_store is None:
            self._belief_store = BeliefStore(self.db_path)
            self._belief_store.initialize()
        return self._belief_store

    @property
    def belief_store(self) -> BeliefStore:
        """Belief 存储（只读查询）。"""
        return self.ensure_belief_store()

    # ── Self — Identity Boundary ─────────────────────────────────────

    def ensure_identity(self) -> IdentityBoundary:
        """确保 IdentityBoundary 已初始化（惰性）。"""
        if self._identity is None:
            self._identity = IdentityBoundary.create_default()
        return self._identity

    @property
    def identity(self) -> IdentityBoundary:
        """身份边界（只读快照）。"""
        return self.ensure_identity()

    # ── 便捷查询方法 ─────────────────────────────────────────────────

    def query_memory(self, limit: int = 10) -> list[dict]:
        """查询最近记忆（Episode）。返回可序列化的 dict 列表。"""
        ctx = self.ensure_episode_store()
        episodes = ctx.query_by_time(limit=limit, active_only=True)
        return [{
            "id": e.id,
            "decision": e.decision[:120],
            "goal": e.goal or "",
            "significance": e.significance_score,
            "created_at": e.created_at.isoformat() if e.created_at else "",
        } for e in episodes]

    def query_beliefs(self, domain: str | None = None, limit: int = 20) -> list[dict]:
        """查询信念列表。返回可序列化的 dict 列表。"""
        ctx = self.belief_store  # trigger lazy init
        try:
            results = ctx.query_by_status(BeliefStatus.ACTIVE, limit=limit)
        except Exception:
            results = []
        beliefs = []
        for b in results[:limit]:
            b_domain = b.scope.get("domain", "") if hasattr(b, "scope") else ""
            if domain and b_domain != domain:
                continue
            beliefs.append({
                "id": b.id,
                "statement": b.statement[:120],
                "confidence": b.confidence,
                "status": b.status.value,
                "domain": b_domain,
            })
        return beliefs

    def identity_summary(self) -> dict:
        """身份边界摘要。"""
        identity = self.ensure_identity()
        return {
            "id": identity.id,
            "principles": [p.name for p in list(identity.principles)[:5]] if identity.principles else [],
            "forbidden_transitions": [f"{ft.from_state}->{ft.to_state}" for ft in list(identity.forbidden_transitions)[:3]] if identity.forbidden_transitions else [],
            "evolution_constraints": {
                k: v for k, v in identity.evolution_constraints.items()
            } if identity.evolution_constraints else {},
        }

    # ── 生命周期 ────────────────────────────────────────────────────

    def close(self) -> None:
        """关闭所有连接。"""
        for store in [self._episode_store, self._belief_store]:
            if store is not None:
                try:
                    store.close()
                except Exception:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── 便捷工厂 ──────────────────────────────────────────────────────
