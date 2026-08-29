"""Phase 24.1 — Import Isolation Test。

验证:
  - Memory 不导入 Phase 25 Self 相关模块
  - Memory 不导入任何超前层
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

MEMORY_PATH = PROJECT / "ocos" / "memory"


def _collect_imports(path: Path) -> set[str]:
    """收集文件中所有模块导入。"""
    imports: set[str] = set()
    if not path.is_file() or path.suffix != ".py":
        return imports
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


# ── Phase 25 Self 禁入 ───────────────────────────────────────────────────────


def test_memory_does_not_import_self_model() -> None:
    """Memory 层不得导入 Phase 25 Self 相关模块。"""
    forbidden_modules = {"ocos.self", "self_model", "identity_model"}
    all_imports: set[str] = set()

    for py_file in MEMORY_PATH.rglob("*.py"):
        all_imports.update(_collect_imports(py_file))

    violations = all_imports & forbidden_modules
    assert len(violations) == 0, (
        f"Memory imports Phase 25 modules: {violations}"
    )


# ── Phase 25 ValueLayer 禁入 ─────────────────────────────────────────────────


def test_memory_does_not_import_value_layer() -> None:
    """Memory 层不得导入 ValueLayer（属于 Self 的价值观层）。"""
    forbidden = {"value_layer", "ValueLayer", "ocos.self.value_layer"}
    all_imports: set[str] = set()

    for py_file in MEMORY_PATH.rglob("*.py"):
        all_imports.update(_collect_imports(py_file))

    violations = all_imports & forbidden
    assert len(violations) == 0, (
        f"Memory imports ValueLayer (Phase 25 territory): {violations}"
    )


# ── 只消费 Trace，不导入生产模块 ─────────────────────────────────────────────


def test_memory_imports_self_contained() -> None:
    """Memory imports should be limited to stdlib + ocos.memory.* internal.

    Exception: ocos.memory.belief may import ocos.constitution (per Freeze §2 L6).
    """
    all_imports: set[str] = set()

    for py_file in MEMORY_PATH.rglob("*.py"):
        all_imports.update(_collect_imports(py_file))

    # Freeze §2 L6: Belief 需要 Constitution StatementValidator
    # P1-A store 下沉: memory store 共享 ocos.storage.connection（2026-08-29 P1-C 回归发现，
    # baseline 无此 import；P1-A 引入，例外表同步）
    _FREEZE_ALLOWED = {
        "ocos.constitution",
        "ocos.constitution.statement_validator",
        "ocos.storage.connection",
    }

    for imp in all_imports:
        if "." not in imp:
            continue
        if imp.startswith("ocos.memory"):
            continue
        if imp in _FREEZE_ALLOWED:
            continue
        assert False, (
            f"Memory imports external production module: '{imp}'"
        )
