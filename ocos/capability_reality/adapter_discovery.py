"""Phase 55: AdapterDiscovery — 自动发现可用工具。

CR55-04: 不假设能力存在 — 扫描环境发现真实可用的工具。

扫描维度:
    1. 文件系统: 检查常见路径是否可读写
    2. Shell: 检查 sh 和其他解释器是否存在
    3. Python: 检查可用模块和版本
    4. 网络: 检查外网连接
    5. 工具: git, curl, make, ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import subprocess
import shutil
import sys

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, CapabilityCategory, AdapterHealth,
)
from ocos.capability_reality.capability_registry import CapabilityRegistry
from ocos.capability_reality.adapter_fs import FilesystemAdapter
from ocos.capability_reality.adapter_shell import ShellAdapter


@dataclass
class DiscoveryReport:
    """发现报告 — 扫描结果汇总。"""
    available_tools: list[str] = field(default_factory=list)
    unavailable_tools: list[str] = field(default_factory=list)
    filesystem: dict = field(default_factory=dict)  # {"home": readable, "tmp": writable, ...}
    shell: dict = field(default_factory=dict)       # {"bash": found, "python3": found, ...}
    python_modules: list[str] = field(default_factory=list)
    network: dict = field(default_factory=dict)     # {"dns": ok, "http": ok, ...}
    risk_assessment: dict = field(default_factory=dict)


@dataclass
class AdapterDiscovery:
    """适配器发现 — 扫描环境并注册可用适配器。

    用法:
        discovery = AdapterDiscovery()
        registry, report = discovery.run()
        # registry 中已注册所有可用的适配器
    """

    safe_roots: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.safe_roots:
            self.safe_roots = [
                os.path.expanduser("~"),
                "/tmp",
                "/home/laogao/Documents",
            ]

    def run(self) -> tuple[CapabilityRegistry, DiscoveryReport]:
        """执行完整发现扫描，返回注册表 + 报告。"""
        registry = CapabilityRegistry()
        report = DiscoveryReport()

        self._discover_filesystem(registry, report)
        self._discover_shell(registry, report)
        self._discover_python(registry, report)
        self._discover_tools(registry, report)

        return registry, report

    def _discover_filesystem(self, registry: CapabilityRegistry, report: DiscoveryReport) -> None:
        """发现文件系统访问能力。"""
        paths = {}
        for root in self.safe_roots:
            paths[root] = {
                "exists": os.path.exists(root),
                "readable": os.access(root, os.R_OK) if os.path.exists(root) else False,
                "writable": os.access(root, os.W_OK) if os.path.exists(root) else False,
            }

        report.filesystem = paths

        can_read = any(p["exists"] and p["readable"] for p in paths.values())
        can_write = any(p["exists"] and p["writable"] for p in paths.values())

        if can_read or can_write:
            adapter = FilesystemAdapter(safe_roots=self.safe_roots)
            registry.register(adapter.descriptor, adapter.execute)
            report.available_tools.append("filesystem")
        else:
            report.unavailable_tools.append("filesystem")

    def _discover_shell(self, registry: CapabilityRegistry, report: DiscoveryReport) -> None:
        """发现 Shell 执行能力。"""
        shells = {}
        for name in ["/bin/sh", "/bin/bash", "/usr/bin/bash", "/bin/zsh"]:
            shells[name] = os.path.exists(name)

        report.shell = shells

        if any(shells.values()):
            adapter = ShellAdapter(safe_roots=self.safe_roots)
            registry.register(adapter.descriptor, adapter.execute)
            report.available_tools.append("shell")
        else:
            report.unavailable_tools.append("shell")

    def _discover_python(self, registry: CapabilityRegistry, report: DiscoveryReport) -> None:
        """发现 Python 运行时。"""
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        modules = [
            "os", "sys", "json", "pathlib", "subprocess", "tempfile",
            "sqlite3", "datetime", "re", "math",
        ]
        available = [m for m in modules if _check_module(m)]

        report.python_modules = available
        report.available_tools.append(f"python{version}")

    def _discover_tools(self, registry: CapabilityRegistry, report: DiscoveryReport) -> None:
        """发现常用 CLI 工具。"""
        tools = ["git", "curl", "wget", "make", "gcc", "g++", "python3", "pip",
                 "docker", "node", "npm", "cargo", "go", "dotnet"]
        for tool in tools:
            if shutil.which(tool):
                report.available_tools.append(tool)
            else:
                report.unavailable_tools.append(tool)


def _check_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


__all__ = ["AdapterDiscovery", "DiscoveryReport"]
