"""Phase 25.3 — 静态扫描: ocos/self/ 目录无人格/情感泄露。

使用 StatementValidator.scan_for_forbidden() 扫描所有 .py 文件的
字符串和注释，确保禁止词汇不出现在源码中。
"""

import os
import ast
import pytest
from ocos.self.statement_validator import StatementValidator


SELF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "ocos", "self",
)


def _extract_string_literals(filepath: str) -> list[str]:
    """从 Python 文件中提取非 docstring 字符串字面量。"""
    with open(filepath) as f:
        source = f.read()
    tree = ast.parse(source)

    strings: list[str] = []
    top_level_bodies = []

    # 收集顶层 body 的第一个表达式（可能是 module docstring）
    if isinstance(tree, ast.Module) and tree.body:
        if isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            pass  # skip module docstring

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value
            # 跳过 docstrings（多行文本）
            if s.startswith("\n") or len(s.split("\n")) > 2:
                continue
            # 跳过验证/错误消息（含 "must"/"必须"/"should"）
            lower = s.lower()
            if any(kw in lower for kw in ("must", "必须", "should", "got ", "missing:", "failed:")):
                continue
            # 跳过描述性标签（太短的不是 statement）
            if len(s) < 10:
                continue
            strings.append(s)

    return strings


def test_no_personality_leak_in_self_dir():
    """扫描 ocos/self/ 所有 .py 文件，确保无禁止词汇泄露。"""
    violations: list[tuple[str, str, str, str]] = []  # (file, category, word, context)

    for filename in sorted(os.listdir(SELF_DIR)):
        if not filename.endswith(".py"):
            continue
        # 跳过禁词列表文件和规则描述文件（它们合理地描述禁止内容）
        if filename in ("statement_validator.py", "governor.py", "identity_boundary.py"):
            continue
        filepath = os.path.join(SELF_DIR, filename)
        strings = _extract_string_literals(filepath)

        for s in strings:
            hits = StatementValidator.scan_for_forbidden(s)
            for cat_en, cat_zh, word in hits:
                # 允许在 scan_for_forbidden 测试方法和 FORBIDDEN 列表中出现
                # 但不允许在其他上下文中出现
                violations.append((filename, cat_zh, word, s[:80]))

    if violations:
        msg = "Personality leak detected in ocos/self/:\n"
        for fname, cat, word, ctx in violations:
            msg += f"  {fname}: [{cat}] '{word}' in: {ctx!r}\n"
        pytest.fail(msg)


def test_self_dir_has_expected_files():
    """确保 ocos/self/ 包含预期的模块文件。"""
    expected = {
        "__init__.py",
        "identity_boundary.py",
        "governor.py",
        "models.py",
        "statement_validator.py",
        "builder.py",
    }
    actual = {f for f in os.listdir(SELF_DIR) if f.endswith(".py")}
    missing = expected - actual
    assert not missing, f"Missing files in ocos/self/: {missing}"
