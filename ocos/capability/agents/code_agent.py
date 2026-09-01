"""code_agent — 代码代理（本地执行沙箱）。

Freeze Phase 46: 使用 subprocess 执行 Python 代码，不 import OCOS 内部模块。
"""

from __future__ import annotations
import ast
import subprocess
import sys
import tempfile
from typing import Any


class CodeAgent:
    """本地代码代理——执行和分析 Python 代码片段。

    ABI: execute(code, action="execute", language="python") -> dict
    """

    def __init__(self, prefix: str = "Code") -> None:
        self._prefix = prefix
        self._timeout = 10  # seconds
        self._max_output = 4000

    def _lint_syntax(self, code: str) -> tuple[bool, str]:
        """检查 Python 语法合法性（静态，不执行）."""
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError: {e.msg} at line {e.lineno}"

    def _run_code(self, code: str) -> tuple[bool, str, str]:
        """在临时文件中运行 Python 代码."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, path],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            output = (result.stdout or "") + (result.stderr or "")
            output = output[:self._max_output]
            if result.returncode != 0:
                return False, output, f"exit={result.returncode}"
            return True, output, ""
        except subprocess.TimeoutExpired:
            return False, f"Timeout after {self._timeout}s", "timeout"
        except Exception as e:
            return False, str(e), "error"

    def _suggest_fixes(self, code: str, error: str) -> list[str]:
        if "SyntaxError" in error:
            return ["Check indentation and colons", "Ensure string quotes are balanced"]
        if "NameError" in error:
            return ["Check variable names and imports", "Verify function definitions exist"]
        if "TypeError" in error:
            return ["Check argument types and counts", "Look for None type issues"]
        if "ImportError" in error:
            return ["Install missing packages: pip install <package>", "Check module spelling"]
        return ["Review the full error message above", "Consider adding debug prints"]

    def execute(self, **inputs: Any) -> dict[str, Any]:
        code = ""
        for key in ("code", "prompt", "script", "input", "text"):
            if key in inputs and inputs[key]:
                code = str(inputs[key])
                break
        if not code:
            return {"output": f"{self._prefix}: no code provided", "success": False}

        action = str(inputs.get("action", "execute")).lower()
        analyze_only = action in ("analyze", "lint", "review")
        language = str(inputs.get("language", "python")).lower()

        if language != "python":
            return {
                "output": f"{self._prefix}: only 'python' is supported in local sandbox. "
                          f"Got language='{language}'.",
                "success": False,
            }

        valid, syntax_err = self._lint_syntax(code)
        if not valid:
            suggestions = self._suggest_fixes(code, syntax_err)
            return {
                "output": f"{self._prefix} Syntax Check FAILED:\n{syntax_err}\n\nSuggestions:\n"
                          + "\n".join(f"- {s}" for s in suggestions),
                "syntax_valid": False,
                "error": syntax_err,
                "success": False,
            }

        if analyze_only:
            return {
                "output": (
                    f"{self._prefix} Analysis (syntax OK):\n\n"
                    f"Lines of code: {len([l for l in code.splitlines() if l.strip()])}\n"
                    f"Top-level definitions: "
                    f"{len(ast.parse(code).body)}\n"
                    f"Functions/Classes: {sum(1 for n in ast.walk(ast.parse(code)) if isinstance(n, (ast.FunctionDef, ast.ClassDef)))}\n"
                    f"Imports: {sum(1 for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Import))}"
                ),
                "syntax_valid": True,
                "success": True,
            }

        ok, output, extra = self._run_code(code)
        return {
            "output": output if output else "(no stdout/stderr)",
            "success": ok,
            "extra": extra,
            "syntax_valid": True,
        }
