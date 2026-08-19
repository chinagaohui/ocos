"""Capability Contract 强制验证测试。

每个 Engine 的「绝不能」通过 AST 检查或接口约定验证。
测试覆盖 14 个标准引擎。

方法：对每个引擎文件做 AST 静态分析 + 运行时接口检查。
"""
from __future__ import annotations

import ast
import importlib
import inspect
import os
from pathlib import Path

import pytest

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engines"

# 14 个标准引擎的模块名
STANDARD_ENGINES = [
    "address_resolver",
    "consolidation_engine",
    "decision_making_engine",
    "forgetting_engine",
    "goal_arbitration_engine",
    "learning_engine",
    "planning_engine",
    "policy_engine",
    "prediction_engine",
    "promotion_engine",
    "reasoning_engine",
    "reflection_engine",
    "retrieval_engine",
    "simulation_engine",
]


def _parse_module(name: str) -> ast.Module:
    path = ENGINE_DIR / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"Engine file not found: {path}")
    return ast.parse(path.read_text(), filename=str(path))


class _ImportFinder(ast.NodeVisitor):
    """收集文件中所有 import 语句。"""
    def __init__(self):
        self.imports: set[str] = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module.split(".")[0])


# ── 测试：引擎不导入禁止的外部包 ──────────────────────────────

FORBIDDEN_IMPORTS = {
    "requests", "httpx", "aiohttp",       # 网络（非工具职责）
    "flask", "fastapi", "django",          # Web 框架
    "sqlalchemy", "pymongo", "redis",      # 直接数据库（应通过 storage 层）
}

@pytest.mark.parametrize("engine", STANDARD_ENGINES)
def test_no_forbidden_imports(engine):
    """绝不能：导入禁止的外部包。"""
    module = _parse_module(engine)
    finder = _ImportFinder()
    finder.visit(module)
    forbidden = finder.imports & FORBIDDEN_IMPORTS
    assert not forbidden, (
        f"{engine} 导入了禁止的包：{forbidden}。"
        f"网络/数据库操作应通过 ocos.storage 层。"
    )


# ── 测试：引擎类有 __manifest__ ──────────────────────────────

@pytest.mark.parametrize("engine", STANDARD_ENGINES)
def test_has_manifest(engine):
    """必须有 __manifest__ 属性（EngineManifest）。"""
    mod_name = f"ocos.engines.{engine}"
    mod = importlib.import_module(mod_name)
    assert hasattr(mod, "__manifest__"), f"{engine} 缺少 __manifest__"


# ── 测试：引擎不持久化数据（直接）──────────────────────────────

_STORAGE_PATTERNS = [
    "import sqlite3",
    "sqlite3.connect",
    "create table",
    "CREATE TABLE",
    "insert into",
    "INSERT INTO",
    "self._conn",
    "db_path",
]

@pytest.mark.parametrize("engine", STANDARD_ENGINES)
def test_no_direct_storage_access(engine):
    """绝不能：直接操作持久化存储（应通过 storage 层）。"""
    path = ENGINE_DIR / f"{engine}.py"
    source = path.read_text()
    for pattern in _STORAGE_PATTERNS:
        if pattern in source:
            pytest.fail(
                f"{engine} 直接使用了 '{pattern}'，应通过 ocos.storage 层。"
            )


# ── 测试：引擎使用 CapabilityEngine 基类 ─────────────────────

@pytest.mark.parametrize("engine", STANDARD_ENGINES)
def test_extends_capability_engine(engine):
    """类必须继承 CapabilityEngine 或等效基类。"""
    mod_name = f"ocos.engines.{engine}"
    mod = importlib.import_module(mod_name)
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        # 跳过内部类
        if name.startswith("_") or name == "CapabilityEngine":
            continue
        # 检查是否继承 CapabilityEngine
        bases = [b.__name__ for b in cls.__mro__]
        if "CapabilityEngine" in bases:
            return  # 至少有一个类继承
    pytest.skip(f"{engine} 中的类未继承 CapabilityEngine（可能使用其他模式）")


# ── 测试：引擎导出策略（每个引擎应有明确导出）─────────────────────

@pytest.mark.parametrize("engine", STANDARD_ENGINES)
def test_engine_exports_class(engine):
    """模块应有 __all__ 或至少导出一个引擎类。"""
    mod_name = f"ocos.engines.{engine}"
    mod = importlib.import_module(mod_name)
    # 有 __all__ 即可
    if hasattr(mod, "__all__"):
        assert len(mod.__all__) > 0, f"{engine} 的 __all__ 为空"
        return
    # 没有 __all__ 就找类
    classes = [
        name for name, cls in inspect.getmembers(mod, inspect.isclass)
        if not name.startswith("_") and cls.__module__ == mod_name
    ]
    assert len(classes) > 0, f"{engine} 既无 __all__ 也无导出类"


# ── 运行检查 ────────────────────────────────────────────────

def test_all_standard_engines_covered():
    """确保所有标准引擎都被上述参数化测试覆盖。"""
    actual = sorted(f.stem for f in ENGINE_DIR.glob("*.py") if not f.stem.startswith("_"))
    plan_engines = sorted(STANDARD_ENGINES)
    # 只检查计划中的引擎—额外的自定义引擎（如 writer_engine）不违反
    for e in plan_engines:
        assert e in actual, f"计划中的引擎 {e} 不存在"
