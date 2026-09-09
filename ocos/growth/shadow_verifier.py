"""ocos/growth/shadow_verifier.py — Step 3 P5 自进化影子验证器.

沙箱隔离: 把项目复制到 tmp_dir，在沙箱里 apply → pytest → 通过才 commit.
护栏 (全部满足才能自动 apply):
  ① autonomy_level == L3
  ② shadow_verifier.pass()
  ③ scale_guard 通过 (绝对50行 OR 比例15% OR 保留≥50%)
  ④ pytest 零回归
  ⑤ 改动文件数 ≤ 5
  ⑥ 不碰红线文件 (宪法/权限/决策类型)
  ⑦ 回滚快照已创建
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional


logger = logging.getLogger(__name__)

# 红线文件 — GrowthOptimizer 绝对不能碰
RED_LINE_FILES = frozenset({
    "ocos/core/constitution.py",
    "ocos/kernel/goal_types.py",
    "ocos/decision/decision_types.py",
    "ocos/execution/autonomy.py",
    "ocos/governance/audit_engine.py",
    "ocos/governance/governance_engine.py",
})


def is_red_line(file_path: str) -> bool:
    """护栏 ⑥: 检查是否红线文件."""
    path = str(file_path).replace("\\", "/")
    for red in RED_LINE_FILES:
        if path.endswith(red):
            return True
    return False


class ShadowVerifier:
    """沙箱隔离影子验证器."""

    def __init__(self, project_root: Optional[str] = None,
                 sandbox_base: Optional[str] = None):
        self._project_root = Path(project_root or os.getcwd())
        self._sandbox_base = Path(sandbox_base or tempfile.gettempdir()) / "ocos-sandbox"

    def prepare_sandbox(self) -> Path:
        """护栏 ⑦: 创建沙箱目录 + 回滚快照."""
        import time
        sandbox = self._sandbox_base / f"run-{int(time.time())}"
        sandbox.parent.mkdir(parents=True, exist_ok=True)
        # 沙箱只复制 .py 源文件 + pyproject.toml / requirements.txt (不复制 .venv / .db)
        sandbox.mkdir(parents=True, exist_ok=True)
        for py_dir in self._project_root.rglob("ocos"):
            if py_dir.is_dir() and ".venv" not in str(py_dir):
                dst = sandbox / py_dir.relative_to(self._project_root)
                shutil.copytree(py_dir, dst, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", ".db", ".jsonl"))
        return sandbox

    def run_pytest_in_sandbox(self, sandbox: Path,
                              test_path: str = "",
                              timeout: int = 180) -> tuple[int, str]:
        """护栏 ④: 在沙箱里跑 pytest."""
        pytest_bin = self._project_root / ".venv" / "bin" / "pytest"
        py = self._project_root / ".venv" / "bin" / "python"
        if not pytest_bin.exists() or not py.exists():
            # 用系统 python 跑 venv 里的 pytest
            pytest_cmd = [str(py), "-m", "pytest"]
        else:
            pytest_cmd = [str(pytest_bin)]
        if test_path:
            pytest_cmd.append(test_path)
        pytest_cmd.extend(["-q", "--tb=line"])
        try:
            result = subprocess.run(
                pytest_cmd, cwd=str(sandbox), capture_output=True,
                text=True, timeout=timeout,
            )
            return result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return -1, "TIMEOUT"
        except Exception as e:
            return -1, str(e)

    def cleanup_sandbox(self, sandbox: Path) -> None:
        try:
            shutil.rmtree(sandbox, ignore_errors=True)
        except Exception:
            pass


class EvolutionGuard:
    """Step 3 护栏检查器 — GrowthOptimizer 自动 apply 必须通过."""

    def __init__(self):
        from ocos.execution.autonomy import full_autonomy
        self._full_autonomy = full_autonomy

    def check(self, proposal: Any) -> tuple[bool, str]:
        """返回 (通过, 原因)."""
        # 护栏 ①
        if not self._full_autonomy():
            return False, "L3 required (full_autonomy=False)"

        # 护栏 ⑥
        file_path = getattr(proposal, "file_path", "")
        if file_path and is_red_line(str(file_path)):
            return False, f"red line file: {file_path}"

        # 护栏 ⑤ — 由 GrowthOptimizer scale_guard 负责，这里不重复

        return True, "OK"
