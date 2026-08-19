"""AgentSnapshot — Agent 完整状态切片模型。

Phase 21.01: Agent Snapshot System

设计约束:
- frozen=True: 快照不可变，防止并发修改
- working_memory_config: 仅保存容量/策略配置，items 强制为空
- 所有字段可选，支持增量恢复
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class AgentSnapshot:
    """Agent 完整状态切片。所有字段 frozen，不可变。"""

    snapshot_id: str
    version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    identity_state: dict[str, Any] = field(default_factory=dict)
    self_view_state: dict[str, Any] = field(default_factory=dict)
    goal_state: list[dict[str, Any]] = field(default_factory=list)
    # 关键约束：仅保存配置，不保存具体 items
    working_memory_config: dict[str, Any] = field(default_factory=dict)
    context_state: dict[str, Any] = field(default_factory=dict)
    runtime_state: dict[str, Any] = field(default_factory=dict)
    attention_state: dict[str, Any] = field(default_factory=dict)
    pending_decision_state: Optional[dict[str, Any]] = None
    governance_state: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """序列化为 JSON（供 SQLite 存储）。"""
        return json.dumps(
            {
                "snapshot_id": self.snapshot_id,
                "version": self.version,
                "created_at": self.created_at.isoformat(),
                "identity_state": self.identity_state,
                "self_view_state": self.self_view_state,
                "goal_state": self.goal_state,
                "working_memory_config": self.working_memory_config,
                "context_state": self.context_state,
                "runtime_state": self.runtime_state,
                "attention_state": self.attention_state,
                "pending_decision_state": self.pending_decision_state,
                "governance_state": self.governance_state,
            },
            default=str,
        )

    @classmethod
    def from_json(cls, data: str) -> AgentSnapshot:
        """从 JSON 字符串反序列化。"""
        obj = json.loads(data)
        return cls(
            snapshot_id=obj["snapshot_id"],
            version=obj.get("version", "1.0"),
            created_at=datetime.fromisoformat(obj["created_at"]),
            identity_state=obj.get("identity_state", {}),
            self_view_state=obj.get("self_view_state", {}),
            goal_state=obj.get("goal_state", []),
            working_memory_config=obj.get(
                "working_memory_config", {"capacity": 100, "items": []}
            ),
            context_state=obj.get("context_state", {}),
            runtime_state=obj.get("runtime_state", {}),
            attention_state=obj.get("attention_state", {}),
            pending_decision_state=obj.get("pending_decision_state"),
            governance_state=obj.get("governance_state", {}),
        )
