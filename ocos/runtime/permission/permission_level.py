"""Phase 39.3: Permission Level — 四级权限模型。

冻结:
    L0 OBSERVE  — 读取状态、查询信息（运行时自省）
    L1 READ     — 读取外部资源（文件、API、数据库读）
    L2 WRITE    — 修改外部资源（文件写入、API POST/PUT）
    L3 EXECUTE  — 执行动作（调用外部工具、Agent、shell）

禁止:
    ADMIN 级别 — OCOS 不存在一个 Capability 能获得管理权。
    Capability 永远不能反向控制 OCOS 核心。
"""

from __future__ import annotations

from enum import IntEnum


class PermissionLevel(IntEnum):
    """Capability 权限级别（递增约束）。

    0 = 最安全, 3 = 最高风险。级别向上不兼容：
    一个标记为 WRITE 的 Capability 自动对 READ/OBSERVE 操作通过。
    """

    OBSERVE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3

    def satisfies(self, required: PermissionLevel) -> bool:
        """当前级别是否满足 required 要求。"""
        return self.value >= required.value

    @classmethod
    def from_string(cls, s: str) -> PermissionLevel:
        """从字符串解析（大小写不敏感）。"""
        mapping = {
            "observe": cls.OBSERVE,
            "read": cls.READ,
            "write": cls.WRITE,
            "execute": cls.EXECUTE,
        }
        return mapping[s.lower().strip()]


# ── 操作 → 权限级别映射 ──

OPERATION_LEVELS: dict[str, PermissionLevel] = {
    # L0: 内部查询
    "runtime.status": PermissionLevel.OBSERVE,
    "goal.list": PermissionLevel.OBSERVE,
    "memory.query": PermissionLevel.OBSERVE,
    "attention.snapshot": PermissionLevel.OBSERVE,
    # L1: 外部读取
    "file.read": PermissionLevel.READ,
    "web.get": PermissionLevel.READ,
    "api.get": PermissionLevel.READ,
    "database.query": PermissionLevel.READ,
    # L2: 外部写入
    "file.write": PermissionLevel.WRITE,
    "web.post": PermissionLevel.WRITE,
    "api.post": PermissionLevel.WRITE,
    "database.insert": PermissionLevel.WRITE,
    "database.update": PermissionLevel.WRITE,
    # L3: 执行动作
    "shell.execute": PermissionLevel.EXECUTE,
    "agent.invoke": PermissionLevel.EXECUTE,
    "tool.execute": PermissionLevel.EXECUTE,
    "process.start": PermissionLevel.EXECUTE,
}
