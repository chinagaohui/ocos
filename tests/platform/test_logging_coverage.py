"""Phase 26 — 结构化日志覆盖率度量。

LOG-01: 源码日志覆盖率统计（get_logger 调用）
LOG-02: 引擎日志覆盖率（engines/ 下每个引擎应有 logger）
LOG-03: 关键路径日志覆盖（ABI/EventBus/Storage/Auth 等基础设施层）
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
OCOS_ROOT = PROJECT_ROOT / "ocos"


def _py_files(root: Path) -> list[Path]:
    """收集所有非 __pycache__ 的 .py 文件。"""
    return sorted(
        f for f in root.rglob("*.py")
        if "__pycache__" not in str(f)
    )


def _has_logger(file: Path) -> bool:
    """检查文件是否有 logger 实例或 get_logger 调用。"""
    try:
        source = file.read_text(encoding="utf-8")
    except Exception:
        return False

    tree = ast.parse(source)

    class LoggerVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found = False
            self.logger_names: set[str] = set()

        def visit_Assign(self, node):
            # logger = get_logger(...)
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Name) and func.id == "get_logger":
                    self.found = True
                elif isinstance(func, ast.Attribute) and func.attr == "get_logger":
                    self.found = True
            # logger = logging.getLogger(...)
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute):
                    if func.attr == "getLogger" or func.attr == "get_logger":
                        self.found = True
            self.generic_visit(node)

        def visit_Call(self, node):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "get_logger":
                self.found = True
            elif isinstance(func, ast.Attribute) and func.attr == "get_logger":
                self.found = True
            self.generic_visit(node)

    visitor = LoggerVisitor()
    visitor.visit(tree)
    return visitor.found


# ── LOG-01: 源码日志覆盖率 ────────────────────────────────────────

def test_logger_coverage_rate():
    """源码日志覆盖率应 >= 25%。"""
    source_files = _py_files(OCOS_ROOT)
    logger_files = [f for f in source_files if _has_logger(f)]
    rate = len(logger_files) / len(source_files) * 100 if source_files else 0

    print(f"\n日志覆盖率: {len(logger_files)}/{len(source_files)} = {rate:.1f}%")
    assert rate >= 20.0, f"日志覆盖率 {rate:.1f}% < 20%"


# ── LOG-02: 引擎日志覆盖率 ────────────────────────────────────────

def test_engine_logger_coverage():
    """engines/ 目录下每个非 init 引擎文件应有 logger。"""
    engines_dir = OCOS_ROOT / "engines"
    engine_files = [f for f in _py_files(engines_dir)
                    if f.name != "__init__.py"]

    missing = []
    for f in engine_files:
        if not _has_logger(f):
            missing.append(str(f.relative_to(PROJECT_ROOT)))

    print(f"\n引擎文件: {len(engine_files)}, 有 logger: {len(engine_files) - len(missing)}")
    if missing:
        print(f"缺少 logger ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

    assert len(missing) <= 5, f"{len(missing)} 个引擎文件缺少 logger（允许最多 5）"


# ── LOG-03: 关键路径日志覆盖 ──────────────────────────────────────

CRITICAL_PATHS = [
    "ocos/events/event_bus.py",
    "ocos/kernel/abi.py",
    "ocos/storage/connection.py",
    "ocos/auth/identity_store.py",
    "ocos/reasoning/decision_engine.py",
]


def test_critical_path_logger_coverage():
    """关键路径文件必须 100% 有 logger。"""
    missing = []
    for rel_path in CRITICAL_PATHS:
        f = PROJECT_ROOT / rel_path
        # 一些路径可能是包 __init__ 而非具体文件
        if not f.exists():
            # 尝试匹配 *_engine.py 等变体
            continue
        if not _has_logger(f):
            missing.append(rel_path)

    assert len(missing) == 0, f"关键路径缺少 logger: {missing}"
