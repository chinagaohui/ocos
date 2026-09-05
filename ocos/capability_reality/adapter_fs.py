"""Phase 55: FilesystemAdapter — 真实文件系统适配器。

提供:
    fs_read  — 读取文件内容
    fs_write — 写入文件
    fs_list  — 列出目录
    fs_stat  — 文件信息
    fs_exists — 检查是否存在
"""

from __future__ import annotations

import os
import pathlib

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, AdapterHealth,
    ExecutionContext, CapabilityCategory, AdapterConfig,
)
from ocos.capability_reality.capability_adapter import CapabilityAdapter


class FilesystemAdapter(CapabilityAdapter):
    """真实文件系统适配器。

    注意: 沙盒模式下只能访问指定的 safe_roots。
    """

    safe_roots: list[str]

    def __init__(self, safe_roots: list[str] | None = None):
        roots = safe_roots or [str(pathlib.Path.home()), "/tmp", "/home/laogao/Documents"]
        self.safe_roots = [os.path.abspath(r) for r in roots]

        config = AdapterConfig(
            sandboxed=True,
            default_timeout=10,
            permissions=["fs_read", "fs_write", "fs_list"],
        )

        descriptor = CapabilityDescriptor(
            name="filesystem",
            category=CapabilityCategory.FILESYSTEM,
            description="Read/write/list files on local filesystem",
            required_params=["operation"],
            optional_params=["path", "content", "recursive"],
            permissions=config.permissions,
            risk_level=3,
            estimated_duration=0.5,
            reversible=False,  # fs_write is not reversible
        )

        super().__init__(descriptor=descriptor, config=config)

    def _do_execute(self, ctx: ExecutionContext) -> object:
        op = ctx.params.get("operation", "read")
        path = ctx.params.get("path", "")

        if op == "read":
            return self._read(path)
        elif op == "write":
            return self._write(path, ctx.params.get("content", ""))
        elif op == "list":
            return self._list_dir(path)
        elif op == "stat":
            return self._stat(path)
        elif op == "exists":
            return self._exists(path)
        else:
            raise ValueError(f"unknown fs operation: {op}")

    def _resolve(self, path: str) -> str:
        """将路径解析为绝对路径，验证在安全根内。

        S1.5 (白皮书 P1-3): realpath 归一（解 symlink）+
        ``Path.is_relative_to`` 严格判属 — 替换原先的 ``startswith``
        前缀检查（"/home/u/docs" 可被 "/home/u/docs-evil" 绕过）。
        """
        if not path:
            raise ValueError("empty path")
        resolved = os.path.realpath(os.path.expanduser(path))
        # 沙盒检查
        if self.config.sandboxed:
            for root in self.safe_roots:
                real_root = os.path.realpath(root)
                if pathlib.Path(resolved).is_relative_to(pathlib.Path(real_root)):
                    return resolved
            raise PermissionError(f"path outside safe roots: {resolved}")
        return resolved

    def _read(self, path: str) -> dict:
        resolved = self._resolve(path)
        if not os.path.exists(resolved):
            raise FileNotFoundError(resolved)
        size = os.path.getsize(resolved)
        if size > self.config.max_output_bytes:
            raise ValueError(f"file too large: {size} > {self.config.max_output_bytes}")
        with open(resolved, "r") as f:
            content = f.read()
        return {"path": resolved, "content": content, "size": size, "lines": content.count("\n") + 1}

    def _write(self, path: str, content: str) -> dict:
        resolved = self._resolve(path)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        with open(resolved, "w") as f:
            f.write(content)
        return {"path": resolved, "written": len(content), "ok": True}

    def _list_dir(self, path: str) -> dict:
        resolved = self._resolve(path)
        if not os.path.isdir(resolved):
            raise NotADirectoryError(resolved)
        entries = os.listdir(resolved)
        result = []
        for name in entries[:100]:  # limit
            p = os.path.join(resolved, name)
            result.append({
                "name": name,
                "type": "dir" if os.path.isdir(p) else "file",
                "size": os.path.getsize(p) if os.path.isfile(p) else 0,
            })
        return {"path": resolved, "entries": result, "total": len(entries)}

    def _stat(self, path: str) -> dict:
        resolved = self._resolve(path)
        st = os.stat(resolved)
        return {
            "path": resolved,
            "size": st.st_size,
            "mtime": st.st_mtime,
            "is_dir": os.path.isdir(resolved),
            "is_file": os.path.isfile(resolved),
        }

    def _exists(self, path: str) -> dict:
        resolved = self._resolve(path)
        return {"path": resolved, "exists": os.path.exists(resolved)}

    def _do_health_check(self) -> AdapterHealth:
        """检查 safe_roots 是否可访问。"""
        for root in self.safe_roots:
            if os.path.exists(root):
                return AdapterHealth.HEALTHY
        return AdapterHealth.DEGRADED


__all__ = ["FilesystemAdapter"]
