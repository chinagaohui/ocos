"""OCOS Runtime Permission — Phase 39.3 Capability Policy Enforcement Layer.

Permission Gateway = OCOS 免疫屏障。
不决定"做什么"，只判断"能不能做"。

Exports:
    PolicyDecision, DecisionResult  — 权限判定
    PermissionLevel                 — L0-L3 四级
    PermissionRequest, PermissionContext — 请求载体
    PermissionTrace                 — 审计记录
    PermissionGateway               — 网关主入口
    BuiltinPolicies                 — 默认安全策略
"""

from .builtin_policies import BuiltinPolicies
from .permission_gateway import PermissionGateway
from .permission_level import PermissionLevel
from .permission_request import Caller, PermissionContext, PermissionRequest, RiskLevel
from .permission_trace import PermissionTrace
from .policy_decision import DecisionResult, PolicyDecision

__all__ = [
    "PolicyDecision",
    "DecisionResult",
    "PermissionLevel",
    "PermissionRequest",
    "PermissionContext",
    "PermissionTrace",
    "PermissionGateway",
    "BuiltinPolicies",
    "Caller",
    "RiskLevel",
]
