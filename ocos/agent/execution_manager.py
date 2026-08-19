"""ExecutionManager — Agent 当前执行状态。

Agent 知道自己当前在做什么。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional


class ExecutionManager:
    """执行管理器。

    跟踪 Agent 正在执行的动作。
    """

    def __init__(self) -> None:
        self._current_action: Optional[dict[str, Any]] = None
        self._history: list[dict[str, Any]] = []

    def begin(self, action_type: str, params: Optional[dict[str, Any]] = None) -> str:
        """开始执行一个动作。"""
        action_id = uuid.uuid4().hex
        self._current_action = {
            "action_id": action_id,
            "type": action_type,
            "params": params or {},
            "status": "executing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        return action_id

    def complete(self, result: Any = None) -> Optional[dict[str, Any]]:
        """完成当前动作。"""
        if self._current_action:
            self._current_action["status"] = "completed"
            self._current_action["result"] = result
            self._current_action["ended_at"] = datetime.now(timezone.utc).isoformat()
            completed = self._current_action
            self._history.append(completed)
            self._current_action = None
            return completed
        return None

    def cancel(self) -> bool:
        """取消当前动作。"""
        if self._current_action:
            self._current_action["status"] = "cancelled"
            self._current_action["ended_at"] = datetime.now(timezone.utc).isoformat()
            self._history.append(self._current_action)
            self._current_action = None
            return True
        return False

    def is_executing(self) -> bool:
        return self._current_action is not None

    def get_current_action(self) -> Optional[dict[str, Any]]:
        return self._current_action

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._history[-limit:]

    def clear_history(self) -> None:
        self._history.clear()
