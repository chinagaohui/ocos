"""Phase 39.3: Permission Request & Context — 权限请求不可变载体。

PermissionRequest = 谁请求什么操作。
PermissionContext = 请求发生的认知上下文。

两者组成完整的 Permission Evaluation 输入。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .permission_level import PermissionLevel


class RiskLevel(str, Enum):
    """请求风险评级。"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Caller(str, Enum):
    """请求方标识。

    冻结约束 (Phase 38): 只有 OCOS_EXECUTIVE 可以发起外部请求。
    Capability 不能反向请求 OCOS 核心。
    """
    OCOS_EXECUTIVE = "OCOS_EXECUTIVE"  # Tick Pipeline 执行意图
    MAINTENANCE = "MAINTENANCE"         # 系统维护任务
    EXTERNAL_AGENT = "EXTERNAL_AGENT"   # 被调用的外部 Agent 的反馈请求


@dataclass(frozen=True)
class PermissionRequest:
    """权限请求 — 不可变。

    Fields:
        capability_id: 请求的 Capability 标识 (e.g. 'file.write', 'agent.invoke')
        action:         具体操作 (e.g. 'write', 'invoke')
        resource:       目标资源 (e.g. '/project/a.py')，None = 无资源
        caller:         请求方标识
        risk_level:     风险评估
        level:          操作所需权限级别
        metadata:       扩展信息
    """

    capability_id: str
    action: str
    level: PermissionLevel  # 必须明确指定操作级别
    resource: str | None = None
    caller: Caller = Caller.OCOS_EXECUTIVE
    risk_level: RiskLevel = RiskLevel.LOW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.capability_id:
            raise ValueError("capability_id must not be empty")
        if not self.action:
            raise ValueError("action must not be empty")


@dataclass(frozen=True)
class PermissionContext:
    """权限请求的认知上下文 — 不可变。

    记录请求发生时的运行时状态，用于审计追溯。
    """

    tick_id: int = 0
    goal_id: str | None = None
    task_id: str | None = None
    requested_by: str = Caller.OCOS_EXECUTIVE.value
    previous_decisions: tuple[str, ...] = ()  # 前序决策 policy_id 链

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick_id": self.tick_id,
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "requested_by": self.requested_by,
            "previous_decisions": list(self.previous_decisions),
        }
