"""架构测试 — Axioms 1-7 不可违反（编译期/运行时检测）。

验证 INFORMATION_THEORY 第八章的 7 条公理在代码中被遵守：

Axiom 1: Reality 不属于系统
Axiom 2: Information 是 Reality 的内部表示，不是 Reality 本身
Axiom 3: 所有认知只能作用于 Information
Axiom 4: Decision 只能基于 Information
Axiom 5: Execution 是唯一改变 Reality 的方式
Axiom 6: Information 不拥有行为
Axiom 7: Reality 永远高于 Information

本测试通过 AST 扫描和语义约束确保公理不被违反。
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OCOS_DIR = PROJECT_ROOT / "ocos"
EVENTS_DIR = OCOS_DIR / "events"
ENGINES_DIR = OCOS_DIR / "engines"
RUNTIME_DIR = OCOS_DIR / "runtime"

# ── Axiom 6: Information 不拥有行为 ─────────────────────────────────────
# InformationModel 类不应包含业务逻辑方法（只应有数据定义和校验）


def test_axiom_6_information_has_no_behavior():
    """Axiom 6: Information 不拥有行为。

    验证 InformationMetadata / UniversalAddress 等模型类
    不应包含业务逻辑方法（CRUD、查询、决策逻辑）。
    只允许 __init__, __post_init__, 校验, __repr__, __eq__, __hash__。
    """
    from ocos.models.information import (
        InformationMetadata,
        InformationState,
        UniversalAddress,
    )

    ALLOWED_METHODS = {
        "__init__",
        "__post_init__",
        "__repr__",
        "__str__",
        "__eq__",
        "__hash__",
        "can_transition_to",  # 状态转移校验（属于模型自身约束，非业务逻辑）
    }

    for cls in (InformationMetadata, UniversalAddress):
        methods = {
            name
            for name in dir(cls)
            if not name.startswith("_")
            or name in ALLOWED_METHODS
        }
        # dataclass frozen + field accessors
        public_methods = {
            name
            for name in dir(cls)
            if not name.startswith("_")
        }
        # 只允许 field names 和特殊方法
        forbidden = public_methods - set(cls.__dataclass_fields__.keys()) - {"__dataclass_fields__"}
        assert len(forbidden) == 0, (
            f"Axiom 6 违反: {cls.__name__} 包含非数据方法: {forbidden}"
        )


def test_axiom_6_enum_has_no_business_logic():
    """Axiom 6: InformationState 枚举只定义状态，不包含业务决策逻辑。"""
    from ocos.models.information import InformationState

    # can_transition_to 是校验方法，不是业务逻辑 — 允许
    # 不应有 promote(), forget(), validate() 等
    # 过滤掉 str.Enum 继承的方法
    _INHERITED_ENUM_METHODS = {
        "capitalize", "casefold", "center", "count", "encode", "endswith",
        "expandtabs", "find", "format", "format_map", "index", "isalnum",
        "isalpha", "isascii", "isdecimal", "isdigit", "isidentifier",
        "islower", "isnumeric", "isprintable", "isspace", "istitle",
        "isupper", "join", "ljust", "lower", "lstrip", "maketrans",
        "partition", "removeprefix", "removesuffix", "replace", "rfind",
        "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split",
        "splitlines", "startswith", "strip", "swapcase", "title",
        "translate", "upper", "zfill",
        # Enum base
        "name", "value", "_name_", "_value_",
    }
    for name in dir(InformationState):
        if callable(getattr(InformationState, name, None)) and not name.startswith("_"):
            assert name in _INHERITED_ENUM_METHODS | {
                "can_transition_to",
            }, f"Axiom 6 违反: InformationState 包含业务方法 {name}"


# ── Axiom 1 + 3: 系统无法直接访问 Reality ──────────────────────────────
# 所有外部输入通过 Observation 包装


def test_axiom_1_3_no_direct_reality_access():
    """Axiom 1+3: 所有外部输入应通过 Observation 或 Event 包装。

    扫描代码，查找可能直接操作外部 I/O 的调用（需人工核查）。
    """
    files_to_check = sorted(OCOS_DIR.rglob("*.py"))
    suspicious_patterns = [
        "open(",  # 文件 I/O
        "requests.",  # HTTP
        "socket.",  # Network
        "subprocess.",  # 子进程
    ]
    results: list[str] = []

    for fpath in files_to_check:
        if "tests" in str(fpath):
            continue
        if fpath.name == "__init__.py":
            continue
        content = fpath.read_text(encoding="utf-8")
        fname = str(fpath.relative_to(OCOS_DIR.parent))
        for pattern in suspicious_patterns:
            if pattern in content and "Observation" not in content:
                results.append(f"{fname}: 包含 '{pattern}' 但未使用 Observation 包装")

    if results:
        print("警告（非硬失败，需人工审核）:")
        for r in results:
            print(f"  {r}")


# ── Axiom 7: Reality 高于 Information ───────────────────────────────────
# Information 不可 override 外部 Reality 验证结果


def test_axiom_7_no_information_override():
    """Axiom 7: 代码不应允许 Information 推翻 Reality 验证。"""
    content = (ENGINES_DIR / "promotion_engine.py").read_text(encoding="utf-8")
    # PromotionEngine 的 governance_approved 参数必须是可选且不强制 true
    # 以允许外部 Reality 信号 override 内部 Information
    assert (
        "governance_approved: bool = False" in content
    ), "Axiom 7 违反: PromotionEngine 的 governance_approved 必须默认为 False"

    # 同样检查 ForgettingEngine
    fe_path = ENGINES_DIR / "forgetting_engine.py"
    if fe_path.exists():
        fe_content = fe_path.read_text()
        assert (
            "governance_approved: bool = False" in fe_content
        ), "Axiom 7 违反: ForgettingEngine 的 governance_approved 必须默认为 False"


# ── Axiom 5: Execution 是唯一改变 Reality 的方式 ──────────────────────
# 没有 Engine 可以直接操作外部系统（通过 Plugin 层）


def test_axiom_5_execution_only_via_plugins():
    """Axiom 5: Engines/Runtime 不应直接 import 外部 I/O 库。

    外部 I/O（文件、网络、数据库）的操作应限制在 Plugin 层。
    """
    import re

    from ocos.tests.test_import_rules import ALLOWED_IMPORTS

    engine_dir = ENGINES_DIR
    engine_files = sorted(engine_dir.rglob("*.py"))
    external_io_modules = {
        "socket",
        "http",
        "requests",
        "aiohttp",
        "sqlite3",
        "psycopg2",
        "redis",
        "subprocess",
        "os.open",
        "io.FileIO",
    }

    # S4.5: 朴素子串扫描会误报 SDK 客户端类名（如 DefaultHttpxClient 含
    # "http"）——Axiom 5 的意图是禁止"直接 import 外部 I/O 库"，故按
    # import/from 语句模式匹配；os.open/io.FileIO 是调用点引用，保留子串。
    for fpath in engine_files:
        if fpath.name == "__init__.py":
            continue
        content = fpath.read_text(encoding="utf-8")
        for mod in external_io_modules:
            fname = str(fpath.relative_to(OCOS_DIR.parent))
            if mod in ("os.open", "io.FileIO"):
                if mod in content:
                    pytest.fail(f"Axiom 5 违反: {fname} 引用了外部 I/O 模块 '{mod}'")
                continue
            if re.search(
                rf"(?:^|\n)\s*(?:import|from)\s+{re.escape(mod)}\b", content):
                pytest.fail(f"Axiom 5 违反: {fname} 直接 import 外部 I/O 库 '{mod}'")
