"""架构测试 — 所有 Information 访问必须通过 UniversalAddress。

验证 INFORMATION_THEORY 第七章硬约束：
- 调用方不关心底层数据来自哪个 Store
- 所有 Information 访问必须通过 AddressResolver 转换 UniversalAddress
- 禁止直接调用 WorkingMemory.get_goals() 等 Store 特定方法
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"


class _DirectStoreCallFinder(ast.NodeVisitor):
    """AST 扫描器：查找直接调用 Store 方法（非通过 AddressResolver）。"""

    SUSPICIOUS_PATTERNS = {
        "WorkingMemory.get_goals",
        "WorkingMemory.add_goal",
        "WorkingMemory.set_preference",
        "KnowledgeRegistry.query",
        "KnowledgeRegistry.register",
        "KnowledgeLifecycle.elevate",
        "InMemoryEventStore",
        "EventStore",
    }

    def __init__(self) -> None:
        self.violations: list[tuple[str, int]] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            call_str = self._call_to_string(node)
            for pattern in self.SUSPICIOUS_PATTERNS:
                if pattern in call_str:
                    self.violations.append((call_str, node.lineno or 0))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.generic_visit(node)

    @staticmethod
    def _call_to_string(node: ast.Call) -> str:
        parts: list[str] = []
        cur = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))


def test_information_access_via_universal_address():
    """架构约束：所有跨 Store 访问必须通过 UniversalAddress。

    扫描 engines/ 和 runtime/ 中的代码，标记直接调用 Store 方法的行为。
    """
    finder = _DirectStoreCallFinder()

    for directory in [OCOS_DIR / "engines", OCOS_DIR / "runtime"]:
        if not directory.exists():
            continue
        for fpath in sorted(directory.rglob("*.py")):
            if fpath.name == "__init__.py":
                continue
            source = fpath.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(fpath))
            except SyntaxError:
                continue
            finder.visit(tree)

    # 允许的例外：引擎自身的测试、__init__.py 中的导入
    ALLOWED_VIOLATIONS: list[str] = []

    violations = [
        (call, lineno)
        for call, lineno in finder.violations
        if call not in ALLOWED_VIOLATIONS
    ]

    if violations:
        msg_lines = ["违反: 直接调用 Store 方法（须使用 UniversalAddress）:"]
        for call, lineno in violations:
            msg_lines.append(f"  {call} (行 {lineno})")
        pytest.fail("\n".join(msg_lines))


def test_engines_import_address_resolver():
    """所有引擎必须 import AddressResolver（而不是直接 import Store）。"""
    resolver_imported = {"ocos.engines.address_resolver", "ocos.engines.address_resolver.AddressResolver"}
    store_imports = {
        "ocos.runtime.context_manager.WorkingMemory",
        "ocos.knowledge.knowledge_registry.KnowledgeRegistry",
        "ocos.events.event_store",
    }

    engine_dir = OCOS_DIR / "engines"
    if not engine_dir.exists():
        pytest.skip("engines 目录不存在")

    for fpath in sorted(engine_dir.rglob("*.py")):
        if fpath.name == "__init__.py":
            continue
        content = fpath.read_text(encoding="utf-8")
        fname = str(fpath.relative_to(OCOS_DIR))
        has_resolver = any(imp in content for imp in resolver_imported)
        has_store = any(imp in content for imp in store_imports)

        # RetrievalEngine 和 PromotionEngine 可能通过 AddressResolver 间接访问 Store
        # 直接 import store 的引擎需要硬约束
        if has_store and not has_resolver:
            pytest.fail(f"{fname}: 直接 import Store 但未 import AddressResolver")
