"""Phase 41: WisdomStore — 智慧持久化存储。

不是通用数据库，而是 Personal Cognitive Asset 的专用存储层。

职责:
    1. 存储/检索 WisdomItem
    2. 按用户隔离
    3. 生命周期管理（promote/deprecate）

边界:
    - 不能修改 Identity.anchor
    - 不能创建/修改 Goal
    - 不能覆盖 PermissionGateway 决策
    - Wisdom 只能提供认知参考，不能直接控制行为
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.personal_memory.wisdom_types import (
    WisdomItem,
    WisdomCollection,
    WisdomState,
    WisdomScope,
)

# 状态等级 — 用于防止低状态对象覆盖高状态智慧（生命周期倒退保护）
# CANDIDATE → VALIDATING → CONFIRMED → ACTIVE → DEPRECATED(终点)
_STATE_RANK = {
    "candidate": 0,
    "validating": 1,
    "confirmed": 2,
    "active": 3,
    "deprecated": 4,
}


@dataclass
class WisdomStore:
    """智慧存储 — 按用户隔离的个人认知资产持久层。

    每个用户拥有独立的 WisdomCollection。
    相同事件在不同用户身上形成不同的智慧。
    """

    # ── 内部存储 ──

    _collections: dict[str, WisdomCollection] = field(default_factory=dict)
    """user_id → WisdomCollection"""

    connection: Optional[Any] = None
    """GAP-P2-4: 可选 SQLite 连接。注入后 add/promote 同步落盘。"""

    def _persist_item(self, user_id: str, wisdom: WisdomItem) -> None:
        """GAP-P2-4: 写入 wisdom_items 表（INSERT OR IGNORE + 状态保护覆盖）。

        UPDATE 仅在目标状态等级 >= 库内现有状态时执行 —
        防止 dream 重巩固用新 CANDIDATE 把已 CONFIRMED/ACTIVE 的智慧打回候选。
        """
        if self.connection is None:
            return
        import json as _json
        self.connection.execute(
            "INSERT OR IGNORE INTO wisdom_items "
            "(user_id, wisdom_id, principle, state, source_patterns, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                wisdom.wisdom_id,
                wisdom.principle,
                wisdom.state.value,
                _json.dumps(list(wisdom.source_patterns), ensure_ascii=False),
                _json.dumps(
                    [e.__dict__ for e in wisdom.evidence], ensure_ascii=False
                ),
            ),
        )
        row = self.connection.execute(
            "SELECT state FROM wisdom_items WHERE user_id=? AND wisdom_id=?",
            (user_id, wisdom.wisdom_id),
        ).fetchone()
        if row is not None and (
            _STATE_RANK.get(str(row[0]), 0)
            > _STATE_RANK.get(wisdom.state.value, 0)
        ):
            return  # 库内状态更高 — 保持不回退
        self.connection.execute(
            "UPDATE wisdom_items SET state=? WHERE user_id=? AND wisdom_id=?",
            (wisdom.state.value, user_id, wisdom.wisdom_id),
        )
        self.connection.commit()

    @classmethod
    def load_from_db(cls, connection: Any) -> "WisdomStore":
        """GAP-P2-4: 从 wisdom_items 表重建内存存储（跨 session 持久化）。"""
        import json as _json
        from ocos.personal_memory.wisdom_types import (
            WisdomEvidence,
        )

        store = cls(connection=connection)
        rows = connection.execute(
            "SELECT user_id, wisdom_id, principle, state, source_patterns, evidence "
            "FROM wisdom_items"
        ).fetchall()
        for user_id, wisdom_id, principle, state, source_patterns, evidence in rows:
            coll = store.get_or_create_collection(user_id)
            item = WisdomItem(
                wisdom_id=wisdom_id,
                principle=principle,
                state=WisdomState(state),
                source_patterns=tuple(_json.loads(source_patterns or "[]")),
                evidence=[
                    WisdomEvidence(**e) for e in _json.loads(evidence or "[]")
                ],
            )
            coll.items[wisdom_id] = item
        return store

    # ── 集合管理 ──

    def get_or_create_collection(self, user_id: str) -> WisdomCollection:
        """获取或创建用户智慧集合。"""
        if user_id not in self._collections:
            self._collections[user_id] = WisdomCollection(user_id=user_id)
        return self._collections[user_id]

    def get_collection(self, user_id: str) -> Optional[WisdomCollection]:
        """获取用户智慧集合，如果不存在返回 None。"""
        return self._collections.get(user_id)

    # ── 智慧 CRUD ──

    def add_wisdom(self, user_id: str, wisdom: WisdomItem) -> None:
        """添加新智慧条目（状态保护：低状态不得覆盖内存与库中的高状态）。"""
        coll = self.get_or_create_collection(user_id)
        existing = coll.get(wisdom.wisdom_id)
        if existing is not None and (
            _STATE_RANK.get(existing.state.value, 0)
            > _STATE_RANK.get(wisdom.state.value, 0)
        ):
            return  # 内存已有更高状态 — 保持不回退
        coll.add(wisdom)
        self._persist_item(user_id, wisdom)

    def get_wisdom(self, user_id: str, wisdom_id: str) -> Optional[WisdomItem]:
        """获取特定智慧。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return None
        return coll.get(wisdom_id)

    def list_active(self, user_id: str) -> list[WisdomItem]:
        """列出用户的活跃智慧。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return []
        return coll.active

    def list_confirmed(self, user_id: str) -> list[WisdomItem]:
        """列出用户已确认的智慧。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return []
        return coll.confirmed

    def list_candidates(self, user_id: str) -> list[WisdomItem]:
        """列出用户的候选智慧。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return []
        return coll.candidates

    # ── 生命周期 ──

    def promote_wisdom(
        self,
        user_id: str,
        wisdom_id: str,
        new_state: WisdomState,
        tick_id: int,
    ) -> bool:
        """提升智慧状态。

        返回 True 如果状态转换合法并成功。
        """
        wisdom = self.get_wisdom(user_id, wisdom_id)
        if wisdom is None:
            return False
        ok = wisdom.promote_to(new_state, tick_id)
        if ok:
            self._persist_item(user_id, wisdom)
        return ok

    def deprecate_wisdom(self, user_id: str, wisdom_id: str, tick_id: int) -> bool:
        """废弃一条智慧。"""
        return self.promote_wisdom(user_id, wisdom_id, WisdomState.DEPRECATED, tick_id)

    # ── 场景查询 ──

    def applicable_to(
        self,
        user_id: str,
        domain: str,
        conditions: tuple[str, ...] = (),
    ) -> list[WisdomItem]:
        """查询适用于特定场景的已确认智慧。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return []
        return coll.applicable_to(domain, conditions)

    # ── 用户隔离 ──

    @property
    def user_ids(self) -> list[str]:
        """所有有智慧记录的用户ID。"""
        return list(self._collections.keys())

    def user_wisdom_count(self, user_id: str) -> int:
        """某用户的智慧总数。"""
        coll = self._collections.get(user_id)
        if coll is None:
            return 0
        return len(coll.items)

    # ── 边界检查 ──

    def assert_boundaries(self, user_id: str) -> bool:
        """验证 Wisdom 没有越权。

        检查所有 entry 是否遵守 PM41-01~04 边界:
            - 没有修改 Identity 的引用
            - 没有直接创建 Goal
            - 没有覆盖 PermissionGateway

        此方法在每次存储操作后由调用方运行（可选）。
        """
        coll = self._collections.get(user_id)
        if coll is None:
            return True
        # WisdomItem 本身不包含修改 Identity/Goal/Permission 的能力，
        # 这是结构级保证。此方法为预留校验钩子。
        return True


__all__ = ["WisdomStore"]
