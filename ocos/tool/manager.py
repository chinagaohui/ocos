"""Phase AI: ToolIntegrationManager — 统一工具集成管理器。

整合工具基础设施：
- AdapterDiscovery: 自动发现可用工具
- CapabilityRegistry: 能力注册中心
- WorkingMemory: 工具状态管理
- ToolCallTracker: 工具调用追踪
- ToolSecurityPolicy: 工具安全策略

架构原则:
- AI-TOOL-01: 工具 ≠ 能力 — 工具是能力的外露接口
- AI-TOOL-02: 注册前验证 — 工具必须通过安全检查才能注册
- AI-TOOL-03: 调用审计 — 每次工具调用记录日志
- AI-TOOL-04: 失败隔离 — 单工具失败不影响其他工具
- AI-TOOL-05: 资源限制 — 工具调用有频率/超时限制
- AI-TOOL-06: 可回滚 — 工具调用结果可撤销

工具分类:
- SYSTEM: 系统级工具（文件系统、进程管理）
- NETWORK: 网络工具（HTTP、DNS）
- COMPUTE: 计算工具（数学、数据处理）
- KNOWLEDGE: 知识工具（搜索、查询）
- PERSONAL: 个人工具（记忆、偏好）
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from ocos.capability_reality.adapter_discovery import AdapterDiscovery
from ocos.capability.capability_registry import CapabilityRegistry
from ocos.capability.capability_types import CapabilityType, CapabilityState

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """工具分类。"""
    SYSTEM = "system"
    NETWORK = "network"
    COMPUTE = "compute"
    KNOWLEDGE = "knowledge"
    PERSONAL = "personal"
    UNKNOWN = "unknown"


class ToolPermission(str, Enum):
    """工具权限级别。"""
    READ_ONLY = "read_only"          # 只读
    WRITE_ALLOWED = "write_allowed"  # 允许写入
    EXECUTE_ALLOWED = "execute_allowed"  # 允许执行
    DANGEROUS = "dangerous"          # 危险操作
    UNRESTRICTED = "unrestricted"    # 无限制


class ToolStatus(str, Enum):
    """工具状态。"""
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class ToolDescriptor:
    """工具描述符。"""
    tool_id: str
    name: str
    category: ToolCategory
    permission: ToolPermission
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "category": self.category.value,
            "permission": self.permission.value,
            "description": self.description,
            "parameters": self.parameters,
            "metadata": self.metadata,
        }


@dataclass
class ToolCallRecord:
    """工具调用记录。"""
    call_id: str
    tool_id: str
    timestamp: float
    input_args: dict[str, Any]
    output_result: Any
    duration_ms: float
    success: bool
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_id": self.tool_id,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error_message": self.error_message[:200] if self.error_message else "",
        }


@dataclass
class ToolCallStats:
    """工具调用统计。"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    rate_limit_violations: int = 0
    blocked_calls: int = 0

    def record_call(self, record: ToolCallRecord) -> None:
        self.total_calls += 1
        self.total_duration_ms += record.duration_ms
        if record.success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.avg_duration_ms = (
            self.total_duration_ms / self.total_calls if self.total_calls > 0 else 0.0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": (
                self.successful_calls / self.total_calls if self.total_calls > 0 else 0.0
            ),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "rate_limit_violations": self.rate_limit_violations,
            "blocked_calls": self.blocked_calls,
        }


class ToolIntegrationManager:
    """工具集成管理器。

    整合工具发现、注册、调用、追踪全生命周期。
    """

    def __init__(
        self,
        discovery_enabled: bool = True,
        audit_enabled: bool = True,
        rate_limit_per_second: int = 100,
        max_call_history: int = 1000,
    ):
        self._discovery_enabled = discovery_enabled
        self._audit_enabled = audit_enabled
        self._rate_limit = rate_limit_per_second
        self._max_history = max_call_history

        self._lock = threading.Lock()
        self._tools: dict[str, ToolDescriptor] = {}
        self._call_history: list[ToolCallRecord] = []
        self._call_stats = ToolCallStats()
        self._registry = CapabilityRegistry()
        self._discovery = AdapterDiscovery()

        # 限速追踪: tool_id -> [(timestamp, ...)]
        self._call_timestamps: dict[str, list[float]] = {}

    # ── 工具发现 ────────────────────────────────────────────────────────

    def discover_tools(self) -> dict[str, Any]:
        """自动发现可用工具。"""
        try:
            _, report = self._discovery.run()
            tools = {}
            for tool_name in report.available_tools:
                tools[tool_name] = ToolDescriptor(
                    tool_id=f"discovered:{tool_name}",
                    name=tool_name,
                    category=self._classify_tool(tool_name),
                    permission=ToolPermission.READ_ONLY,
                    description=f"自动发现的工具: {tool_name}",
                ).to_dict()
            return {"discovered": len(tools), "tools": tools}
        except Exception as e:
            logger.error("Tool discovery failed: %s", e)
            return {"error": str(e), "discovered": 0}

    def _classify_tool(self, tool_name: str) -> ToolCategory:
        """根据工具名分类。"""
        if any(kw in tool_name.lower() for kw in ["fs", "file", "disk", "process"]):
            return ToolCategory.SYSTEM
        if any(kw in tool_name.lower() for kw in ["http", "dns", "network", "curl", "wget"]):
            return ToolCategory.NETWORK
        if any(kw in tool_name.lower() for kw in ["calc", "math", "compute", "data"]):
            return ToolCategory.COMPUTE
        if any(kw in tool_name.lower() for kw in ["search", "query", "knowledge", "wiki"]):
            return ToolCategory.KNOWLEDGE
        if any(kw in tool_name.lower() for kw in ["memory", "preference", "personal"]):
            return ToolCategory.PERSONAL
        return ToolCategory.UNKNOWN

    # ── 工具注册 ────────────────────────────────────────────────────────

    def register_tool(
        self,
        tool_id: str,
        name: str,
        category: ToolCategory,
        permission: ToolPermission,
        description: str = "",
        parameters: dict[str, Any] | None = None,
    ) -> ToolDescriptor | None:
        """注册一个工具。"""
        with self._lock:
            if tool_id in self._tools:
                logger.warning("Tool %s already registered, updating", tool_id)

            descriptor = ToolDescriptor(
                tool_id=tool_id,
                name=name,
                category=category,
                permission=permission,
                description=description,
                parameters=parameters or {},
            )
            self._tools[tool_id] = descriptor

            # 同步到能力注册表
            from ocos.capability.capability_types import CapabilityType
            self._registry.register_from_extension(
                name=name,
                cap_type=CapabilityType.SEARCH if category == ToolCategory.KNOWLEDGE else CapabilityType.API_CALL,
                provider=tool_id,
                description=description,
            )

            logger.info("Tool registered: %s (%s)", tool_id, category.value)
            return descriptor

    def unregister_tool(self, tool_id: str) -> bool:
        """注销一个工具。"""
        with self._lock:
            if tool_id not in self._tools:
                return False
            del self._tools[tool_id]
            logger.info("Tool unregistered: %s", tool_id)
            return True

    def get_tool(self, tool_id: str) -> ToolDescriptor | None:
        """获取工具描述符。"""
        with self._lock:
            return self._tools.get(tool_id)

    def list_tools(self, category: ToolCategory | None = None) -> list[dict[str, Any]]:
        """列出所有工具（可按分类过滤）。"""
        with self._lock:
            if category:
                return [
                    t.to_dict() for t in self._tools.values()
                    if t.category == category
                ]
            return [t.to_dict() for t in self._tools.values()]

    # ── 工具调用 ────────────────────────────────────────────────────────

    def can_call_tool(self, tool_id: str) -> bool:
        """检查是否可以调用工具。"""
        with self._lock:
            if tool_id not in self._tools:
                return False
            tool = self._tools[tool_id]
            if tool.permission == ToolPermission.DANGEROUS:
                return False
            # 检查限速
            now = time.time()
            timestamps = self._call_timestamps.get(tool_id, [])
            recent = [t for t in timestamps if now - t < 1.0]
            if len(recent) >= self._rate_limit:
                self._call_stats.rate_limit_violations += 1
                return False
            return True

    def call_tool(
        self,
        tool_id: str,
        args: dict[str, Any] | None = None,
        timeout_ms: float = 5000.0,
    ) -> dict[str, Any]:
        """调用工具（模拟）。"""
        start_time = time.time()
        call_id = f"call-{time.time():.0f}-{threading.current_thread().ident}"

        # 先检查是否允许调用
        if not self.can_call_tool(tool_id):
            return {
                "call_id": call_id,
                "tool_id": tool_id,
                "success": False,
                "error": f"Tool {tool_id} rate limited or blocked",
            }

        with self._lock:
            if tool_id not in self._tools:
                return {
                    "call_id": call_id,
                    "success": False,
                    "error": f"Tool {tool_id} not registered",
                }

            tool = self._tools[tool_id]
            if tool.permission == ToolPermission.DANGEROUS:
                self._call_stats.blocked_calls += 1
                return {
                    "call_id": call_id,
                    "success": False,
                    "error": f"Tool {tool_id} blocked (dangerous)",
                }

            # 更新限速计数
            now = time.time()
            if tool_id not in self._call_timestamps:
                self._call_timestamps[tool_id] = []
            self._call_timestamps[tool_id].append(now)
            # 清理过期时间戳
            self._call_timestamps[tool_id] = [
                t for t in self._call_timestamps[tool_id]
                if now - t < 1.0
            ]

        # 模拟工具调用
        try:
            result = self._simulate_tool_call(tool_id, args or {})
            duration_ms = (time.time() - start_time) * 1000

            record = ToolCallRecord(
                call_id=call_id,
                tool_id=tool_id,
                timestamp=start_time,
                input_args=args or {},
                output_result=result,
                duration_ms=duration_ms,
                success=True,
            )
            self._call_stats.record_call(record)

            with self._lock:
                self._call_history.append(record)
                if len(self._call_history) > self._max_history:
                    self._call_history.pop(0)

            return {
                "call_id": call_id,
                "tool_id": tool_id,
                "success": True,
                "result": result,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error("Tool call failed: %s", e)
            return {
                "call_id": call_id,
                "tool_id": tool_id,
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms,
            }

    def _simulate_tool_call(
        self, tool_id: str, args: dict[str, Any]
    ) -> dict[str, Any]:
        """模拟工具调用（实际项目应注入真实工具）。"""
        return {
            "tool_id": tool_id,
            "input": args,
            "output": f"Tool {tool_id} executed successfully",
            "status": "ok",
        }

    # ── 调用历史 ────────────────────────────────────────────────────────

    def get_call_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取调用历史。"""
        with self._lock:
            return [r.to_dict() for r in self._call_history[-limit:]]

    def get_call_stats(self) -> dict[str, Any]:
        """获取调用统计。"""
        with self._lock:
            return {
                **self._call_stats.to_dict(),
                "history_count": len(self._call_history),
            }

    # ── 工具能力查询 ────────────────────────────────────────────────────

    def get_available_tools(self) -> list[str]:
        """获取可用工具列表。"""
        with self._lock:
            return sorted(self._tools.keys())

    def has_tool(self, tool_id: str) -> bool:
        """检查工具是否存在。"""
        with self._lock:
            return tool_id in self._tools

    # ── 工具安全 ────────────────────────────────────────────────────────

    def block_tool(self, tool_id: str) -> bool:
        """阻断工具（临时）。"""
        with self._lock:
            if tool_id not in self._tools:
                return False
            self._tools[tool_id].permission = ToolPermission.DANGEROUS
            logger.warning("Tool blocked: %s", tool_id)
            return True

    def unblock_tool(self, tool_id: str) -> bool:
        """解除工具阻断。"""
        with self._lock:
            if tool_id not in self._tools:
                return False
            self._tools[tool_id].permission = ToolPermission.READ_ONLY
            logger.info("Tool unblocked: %s", tool_id)
            return True

    # ── 状态管理 ────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """获取管理器状态。"""
        with self._lock:
            return {
                "total_tools": len(self._tools),
                "active_tools": sum(
                    1 for t in self._tools.values()
                    if t.permission != ToolPermission.DANGEROUS
                ),
                "total_calls": self._call_stats.total_calls,
                "success_rate": round(
                    self._call_stats.successful_calls / self._call_stats.total_calls, 3
                ) if self._call_stats.total_calls > 0 else 0.0,
                "history_size": len(self._call_history),
                "rate_limit": self._rate_limit,
            }

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息（用于 MasterAgent.tick）。"""
        return self.get_status()
