"""架构测试 — 无代码绕过 AddressResolver 直接调用 Store。

验证 INFORMATION_THEORY 硬约束：
- 所有 Information 访问必须通过 Address Resolver
- 禁止绕过 Resolver 直接调用 Store
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"

# 定义 Store 层文件的路径
STORE_FILES = {
    "ocos.runtime.context_manager",
    "ocos.knowledge.knowledge_registry",
    "ocos.events.event_store",
}

# 被授权通过直接 import 访问 Store 的模块白名单
DIRECT_ACCESS_WHITELIST = {
    "ocos.engines.address_resolver",  # AddressResolver 本身是 Store 的路由层
    "ocos.knowledge.knowledge_abi",   # 知识平面 ABI（标准化接口）
    "ocos.knowledge.knowledge_evolution",  # 知识演化层（内部引擎）
    "ocos.knowledge.knowledge_lifecycle",  # 知识生命周期管理（内部引擎）
    "ocos.runtime.attention_engine",  # Runtime 注意引擎（经认可的跨层调用）
    "ocos.runtime.goal_runtime",      # Phase 18 Goal Runtime Engine（需访问 WorkingMemory）
    "ocos.runtime.decision_runtime",  # Phase 18 Decision Runtime Engine（需访问 WorkingMemory）
    "ocos.runtime.execution_runtime", # Phase 18 Execution Runtime Engine（需访问 WorkingMemory）
    "ocos.runtime.process_runtime",   # Phase 18 Process Runtime Engine（需访问 WorkingMemory）
    "ocos.engines.reasoning_engine",   # Phase 19 Reasoning Engine（需访问 WorkingMemory）
    "ocos.engines.planning_engine",    # Phase 19 Planning Engine（需访问 WorkingMemory）
    "ocos.engines.decision_making_engine",  # Phase 19 DecisionMaking Engine（需访问 WorkingMemory）
    "ocos.engines.policy_engine",           # Phase 19 Policy Engine（需访问 WorkingMemory）
    "ocos.engines.goal_arbitration_engine",   # Phase 19 GoalArbitration Engine（需访问 WorkingMemory）
    "ocos.engines.simulation_engine",           # Phase 19 Simulation Engine（需访问 WorkingMemory）
    "ocos.engines.learning_engine",              # Phase 19 Learning Engine（需访问 WorkingMemory）
    "ocos.engines.reflection_engine",             # Phase 19 Reflection Engine（需访问 WorkingMemory）
    "ocos.engines.prediction_engine",              # Phase 19 Prediction Engine（需访问 WorkingMemory）
    "ocos.agent.engine_bridge",                     # Phase 26 Agent-Engine Bridge（需访问 WorkingMemory）
    "ocos.engines.writer_engine",                   # Phase 27 Writer Engine（需访问 WorkingMemory）
}


def _get_module_name(filepath: Path) -> str:
    """将文件路径映射到模块名。"""
    rel = filepath.relative_to(OCOS_DIR.parent)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].replace(".py", "")
    return ".".join(parts)


def _get_package(module: str) -> str:
    """取模块的包路径（前 3 段）。"""
    parts = module.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])
    return module


class _DirectStoreAccessChecker(ast.NodeVisitor):
    """AST 扫描：检查是否直接 import 了 Store 模块。"""

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.violations: list[tuple[str, int, str]] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_import(alias.name, node.lineno or 0)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            for alias in node.names:
                full_module = f"{node.module}.{alias.name}"
                self._check_import(full_module, node.lineno or 0)
        self.generic_visit(node)

    def _check_import(self, imported_module: str, lineno: int) -> None:
        """检查是否直接 import 了 Store。"""
        if not imported_module.startswith("ocos"):
            return
        # 跳过白名单
        for white in DIRECT_ACCESS_WHITELIST:
            if imported_module.startswith(white):
                return
        # 检查是否 import 了 Store 模块
        module_pkg = _get_package(imported_module)
        for store_module in STORE_FILES:
            if imported_module.startswith(store_module):
                # 允许白名单模块直接访问 Store
                source_pkg = _get_package(self.module_name)
                if self.module_name not in DIRECT_ACCESS_WHITELIST:
                    self.violations.append(
                        (self.module_name, lineno, imported_module)
                    )


def test_no_direct_store_access():
    """无代码绕过 AddressResolver 直接调用 Store。"""
    all_violations: list[tuple[str, int, str]] = []

    py_files = sorted(OCOS_DIR.rglob("*.py"))
    for fpath in py_files:
        if "tests" in str(fpath):
            continue
        if fpath.name == "__init__.py":
            continue
        module_name = _get_module_name(fpath)
        source = fpath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(fpath))
        except SyntaxError:
            continue
        checker = _DirectStoreAccessChecker(module_name)
        checker.visit(tree)
        all_violations.extend(checker.violations)

    if all_violations:
        msg_lines = [
            "以下模块绕过 AddressResolver 直接 import Store（违法）:"
        ]
        for module, lineno, target in all_violations:
            msg_lines.append(f"  {module}:{lineno} → {target}")
        msg_lines.append("")
        msg_lines.append("应通过 AddressResolver 间接访问这些 Store。")
        pytest.fail("\n".join(msg_lines))
