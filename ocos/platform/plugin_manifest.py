"""
D2 Plugin Manifest — 插件声明数据结构。

职责：
- 定义 Permission 枚举（FILE_READ / FILE_WRITE / NETWORK / SYSTEM）
- 定义 PluginManifest frozen dataclass（插件声明自身权限、超时、入口点）
- 提供 validate_manifest() 静态校验函数

架构定位：
  Manifest 是 Plugin Sandbox (D2) 的输入契约。
  Plugin Loader (D3) 从插件目录读取 manifest 后，由 Sandbox 验证并通过。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── 权限枚举 ─────────────────────────────────────────────────────────────────

class Permission(str, Enum):
    """插件可声明的权限类型。"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NETWORK = "network"
    SYSTEM = "system"

    @classmethod
    def all_values(cls) -> set[str]:
        return {m.value for m in cls}


# ── Manifest 数据模型 ────────────────────────────────────────────────────────

# entry_point 格式：module.path:ClassName
_ENTRY_POINT_PATTERN = re.compile(r"^[a-zA-Z_][\w.]*:[A-Za-z_]\w*$")


@dataclass(frozen=True)
class PluginManifest:
    """插件声明清单——插件安装前必须提供的元信息。

    所有字段均为不可变。Manifest 由插件作者在插件包内声明，
    Plugin Sandbox (D2) 在 load() 时验证。
    """

    name: str = ""
    """插件名称。必填字段，空名称在 validate 时被拒绝。"""

    version: str = "0.1.0"
    """插件版本号。"""

    entry_point: str = ""
    """入口类路径，格式为 'module.path:ClassName'（如 'ocos.plugins.foo:Plugin'）。
    validate_manifest() 会校验格式。"""

    required_permissions: tuple[Permission, ...] = field(default_factory=tuple)
    """插件执行所需权限列表。超出 SandboxConfig.allowed_permissions 则拒绝加载。"""

    timeout_seconds: int = 30
    """单次 execute() 最大执行秒数。最小 1，最大 300。"""

    allowed_imports: tuple[str, ...] = field(default_factory=tuple)
    """额外允许的 import 模块前缀（叠加在 SandboxConfig.allowed_imports_global 之上）。"""

    capability_id: str = ""
    """关联的 D1 CapabilityDescriptor.capability_id（可选）。
    配置后 Sandbox 会在 load() 时查验 D1 Registry 中的实际注册信息。"""

    description: str = ""
    """插件描述（仅供文档/展示使用）。"""

    metadata: dict[str, object] = field(default_factory=dict)
    """额外元信息（作者、许可证等），Sandbox 不验证。"""


# ── 校验函数 ──────────────────────────────────────────────────────────────────


def validate_manifest(manifest: PluginManifest) -> Optional[str]:
    """验证 PluginManifest 是否合法。

    Returns:
        None → 验证通过
        str  → 拒绝理由（错误消息），调用方可直接用作拒绝原因
    """
    # 1. 名称必填
    if not manifest.name:
        return "插件名称不能为空"

    # 2. entry_point 格式校验：module.path:ClassName
    if not manifest.entry_point:
        return "entry_point 不能为空"
    if not _ENTRY_POINT_PATTERN.match(manifest.entry_point):
        return (
            f"entry_point 格式无效: '{manifest.entry_point}'。"
            " 必须为 'module.path:ClassName' 格式（如 'ocos.plugins.foo:Plugin'）"
        )

    # 3. 冒号两侧非空
    module_part, _, class_part = manifest.entry_point.rpartition(":")
    if not module_part or not class_part:
        return f"entry_point 冒号两侧不能为空: '{manifest.entry_point}'"

    # 4. 权限值合法性
    valid_permissions = Permission.all_values()
    for perm in manifest.required_permissions:
        if isinstance(perm, Permission):
            continue
        perm_str = str(perm.value) if isinstance(perm, Permission) else str(perm)
        if perm_str not in valid_permissions:
            return f"未知权限: '{perm_str}'。有效值: {sorted(valid_permissions)}"

    # 5. 超时范围
    if manifest.timeout_seconds < 1:
        return f"timeout_seconds 不能小于 1，当前值: {manifest.timeout_seconds}"
    if manifest.timeout_seconds > 300:
        return f"timeout_seconds 不能超过 300，当前值: {manifest.timeout_seconds}"

    return None  # 通过
