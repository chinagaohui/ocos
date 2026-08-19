"""IdentityAnchor — 身份锚点。

Agent 知道"我是谁"——这是 BOOT 顺序中**第一个**加载的模块。
Identity 的优先级高于 Memory（人格锚点 > 人格素材）。

Phase 21: born_at 持久化 + owner_id + SQLite 恢复。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional


class IdentityAnchor:
    """身份锚点。

    封装 Agent 的核心身份——基于 IDENTITY_MODEL.md 的 core/anchor/self_view/state 四层。

    Phase 21 变更:
      - born_at: 出生时间戳（持久化，永不改变）
      - owner_id: 所属人类主人 ID
      - created_at: 始终等于 born_at，不再每次 __init__ 重算
      - to_dict() / from_dict(): JSON 序列化支持
    """

    def __init__(
        self,
        agent_id: str,
        name: str = "OCOS Agent",
        version: str = "1.0.0",
        *,
        born_at: Optional[datetime] = None,
        owner_id: Optional[str] = None,
    ):
        self._agent_id = agent_id
        self._name = name
        self._version = version

        # born_at — 出生时间戳，一生不变
        self._born_at: datetime = born_at or datetime.now(timezone.utc)

        # owner_id — 所属人类主人
        self._owner_id: Optional[str] = owner_id

        # core — 绝不会改变
        self._core: dict[str, str] = {
            "agent_id": agent_id,
            "created_at": self._born_at.isoformat(),
        }
        # anchor — 很少改变
        self._anchor: dict[str, str] = {
            "name": name,
            "version": version,
        }
        # self_view — 缓慢变化
        self._self_view: dict[str, float] = {
            "confidence": 1.0,
            "integrity": 1.0,
        }
        # state — 实时变化
        self._state: dict[str, str] = {
            "current_mood": "neutral",
        }

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def born_at(self) -> datetime:
        return self._born_at

    @property
    def created_at(self) -> datetime:
        """始终等于 born_at，永不 recalc。"""
        return self._born_at

    @property
    def owner_id(self) -> Optional[str]:
        return self._owner_id

    # ── Public API ─────────────────────────────────────────────────────────

    def get_identity_id(self) -> str:
        return self._agent_id

    def get_name(self) -> str:
        return self._name

    def verify(self) -> bool:
        """验证身份完整性：core 必须包含 agent_id。"""
        return "agent_id" in self._core and self._core["agent_id"] == self._agent_id

    def get_born_at(self) -> str:
        """返回出生时间 ISO 字符串。"""
        return self._born_at.isoformat()

    def get_core(self) -> dict[str, str]:
        return dict(self._core)

    def get_anchor(self) -> dict[str, str]:
        return dict(self._anchor)

    def set_anchor(self, key: str, value: str) -> None:
        """更新锚点属性（如重命名）。"""
        if key in ("agent_id",):
            raise ValueError(f"Cannot modify core attribute: {key}")
        self._anchor[key] = value
        if key == "name":
            self._name = value

    def get_self_view(self) -> dict[str, float]:
        return dict(self._self_view)

    def update_self_view(self, confidence: Optional[float] = None) -> None:
        """更新自我认知（由 Reflection/Learning 调用）。"""
        if confidence is not None:
            self._self_view["confidence"] = max(0.0, min(1.0, confidence))

    def get_state(self) -> dict[str, str]:
        return dict(self._state)

    def set_state(self, key: str, value: str) -> None:
        """更新实时状态。"""
        self._state[key] = value

    # ── Phase 21: Serialization ────────────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化为 JSON 兼容字典（用于持久化）。"""
        return {
            "agent_id": self._agent_id,
            "born_at": self._born_at.isoformat(),
            "owner_id": self._owner_id,
            "name": self._name,
            "version": self._version,
            "self_view": json.dumps(self._self_view),
            "state": json.dumps(self._state),
            "anchor": json.dumps(self._anchor),
        }

    @classmethod
    def from_dict(cls, data: dict) -> IdentityAnchor:
        """从持久化字典恢复 IdentityAnchor。"""
        born_at = datetime.fromisoformat(data["born_at"])
        instance = cls(
            agent_id=data["agent_id"],
            name=data.get("name", "OCOS Agent"),
            version=data.get("version", "1.0.0"),
            born_at=born_at,
            owner_id=data.get("owner_id"),
        )
        instance._self_view = json.loads(data.get("self_view", "{}"))
        instance._state = json.loads(data.get("state", "{}"))
        instance._anchor = json.loads(data.get("anchor", "{}"))
        instance._name = data.get("name", instance._name)
        instance._version = data.get("version", instance._version)
        return instance

    def __repr__(self) -> str:
        return f"<IdentityAnchor: {self._name} ({self._agent_id}) born={self._born_at.isoformat()}>"
