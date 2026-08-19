"""Phase 28 — AgentSelector: 选择最优 Agent 执行 Task。

逻辑:
  1. 按 task.agent_type 匹配
  2. 过滤 available
  3. 按 success_rate 降序
  4. 可选 capability 过滤
"""

from __future__ import annotations

from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.planning.models import Task


class AgentSelector:
    """Agent 选择器。"""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def select(self, task: Task) -> AgentDescriptor | None:
        """选择最适合执行 Task 的 Agent。"""
        # 1. 按类型查找 available 的
        candidates = [
            a for a in self._registry.find_by_type(task.agent_type)
            if a.status == "available"
        ]
        if not candidates:
            return None

        # 2. 如果 task 隐含 capability 要求（通过描述推断）
        #    过滤匹配 capability 的
        capability_hint = self._infer_capability(task.task_type)
        if capability_hint:
            matched = [a for a in candidates if capability_hint in a.capabilities]
            if matched:
                candidates = matched

        # 3. 按 success_rate 降序，返回最优
        candidates.sort(key=lambda a: a.success_rate, reverse=True)
        return candidates[0]

    def select_fallback(self, task: Task, exclude_id: str) -> AgentDescriptor | None:
        """选择备选 Agent（排除指定 ID）。"""
        candidates = [
            a for a in self._registry.find_by_type(task.agent_type)
            if a.status == "available" and a.agent_id != exclude_id
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda a: a.success_rate, reverse=True)
        return candidates[0]

    @staticmethod
    def _infer_capability(task_type: str) -> str | None:
        """从 task_type 推断需要的 capability。"""
        _map = {
            "create": "generation",
            "modify": "modification",
            "analyze": "analysis",
            "execute": "execution",
            "verify": "verification",
        }
        return _map.get(task_type)
