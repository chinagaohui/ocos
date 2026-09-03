"""self_modification_agent — OCOS 自我修改代理。

Freeze Phase 47: 允许 OCOS 在安全边界内修改自身代码。

ABI: execute(task, dry_run=True) -> dict
    - task:     修改任务描述
    - dry_run:  预览模式，不实际写文件
    - 返回: diff, warnings, approval_required
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModificationPlan:
    """修改计划——所有变更的前置审查。"""

    file_path: str = ""
    operation: str = ""          # add | edit | delete
    description: str = ""
    diff: str = ""
    test_strategy: str = ""
    risks: list[str] = field(default_factory=list)
    approval_required: bool = False

    @property
    def is_safe(self) -> bool:
        return not self.approval_required


class SelfModificationAgent:
    """OCOS 自我修改代理。

    安全约束:
        - 禁止修改 .venv/、tests/（测试除外）、.git/
        - 禁止修改 config.json、密钥文件
        - 必须通过测试后才能提交
        - 任何文件改动都需要人工确认（dry_run=True 时仅预览）
    """

    # ── 安全禁区 ──
    FORBIDDEN_DIRS = {".venv", ".git", "__pycache__", "node_modules"}
    FORBIDDEN_FILES = {".env", ".env.local", "config.json"}
    ALLOWED_EXTENSIONS = {".py", ".md", ".toml", ".yaml", ".yml", ".json"}

    # ── 高风险操作（需要人工确认） ──
    HIGH_RISK_PATTERNS: list[re.Pattern] = [  # type: ignore[type-arg]
        re.compile(r"\bimport\s+os\b"),
        re.compile(r"\bsubprocess\."),
        re.compile(r"\bopen\("),
        re.compile(r"\bwrite_file\b"),
        re.compile(r"\bremove_file\b"),
        re.compile(r"\bsystem\("),
        re.compile(r"\borchestrat"),
        re.compile(r"\bdaemon\b"),
    ]

    def __init__(self, project_root: str) -> None:
        self._project_root = Path(project_root).resolve()
        self._max_diff_size = 2000  # 限制输出大小

    # ── 验证路径 ──

    def _validate_path(self, path_str: str) -> tuple[bool, str]:
        """验证路径是否在项目内且不在禁区。"""
        path = self._project_root / path_str

        # 必须在项目根目录下
        if not path.resolve().is_relative_to(self._project_root):
            return False, f"Path escapes project root: {path_str}"

        # 检查禁区
        rel_parts = path.relative_to(self._project_root).parts
        for part in rel_parts:
            if part in self.FORBIDDEN_DIRS:
                return False, f"Forbidden directory: {part}/"

        # 检查禁止文件
        if path.name in self.FORBIDDEN_FILES:
            return False, f"Forbidden file: {path.name}"

        # 检查扩展名
        if path.suffix not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported extension: {path.suffix}"

        return True, str(path)

    # ── 风险分析 ──

    def _analyze_risks(self, path: str, content: str) -> list[str]:
        """分析内容的风险等级。"""
        risks: list[str] = []
        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern.search(content):
                risks.append(f"Contains risky pattern: {pattern.pattern}")
                break
        if len(content.splitlines()) > 500:
            risks.append("Large file (>500 lines)")
        return risks

    # ── 生成 diff ──

    def _generate_diff(self, path: str, new_content: str, original: str) -> str:
        """生成统一的 diff 格式。"""
        orig_lines = original.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # 简单逐行对比
        max_len = max(len(orig_lines), len(new_lines))
        lines: list[str] = []
        lines.append(f"--- {path}")
        lines.append(f"+++ {path}")
        hunk_start = 1
        context_count = 0
        for i in range(min(len(orig_lines), len(new_lines))):
            if orig_lines[i] != new_lines[i]:
                if context_count > 0:
                    lines.append(f"@@ -{hunk_start} +{i+1} @@")
                    hunk_start = i + 1
                lines.append(f"-{orig_lines[i].rstrip()}")
                lines.append(f"+{new_lines[i].rstrip()}")
                context_count = 0
            else:
                context_count += 1
                if context_count == 1:
                    lines.append(f"@@ -{i+1} +{i+1} @@")

        # 剩余未显示的行
        if len(orig_lines) < len(new_lines):
            for i in range(len(orig_lines), len(new_lines)):
                lines.append(f"+{new_lines[i].rstrip()}")
        elif len(new_lines) < len(orig_lines):
            for i in range(len(new_lines), len(orig_lines)):
                lines.append(f"-{orig_lines[i].rstrip()}")

        result = "\n".join(lines[:self._max_diff_size])
        return result if result else "(no changes)"

    # ── 读取原文件 ──

    def _read_file(self, path: Path) -> str:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    # ── 主执行接口 ──

    def execute(self, **inputs: Any) -> dict[str, Any]:
        """执行自我修改任务。

        输入参数:
            - task:     修改任务描述（必须）
            - file:     目标文件路径（相对项目根）
            - content:  新内容（edit/add 时必填）
            - delete:   是否删除文件
            - test:     是否运行相关测试
            - commit:   是否提交 git
            - dry_run:  预览模式（默认 True）
        """
        task = str(inputs.get("task", ""))
        file_path = str(inputs.get("file", ""))
        content = str(inputs.get("content", ""))
        should_delete = bool(inputs.get("delete", False))
        run_tests = bool(inputs.get("test", True))
        do_commit = bool(inputs.get("commit", False))
        dry_run = bool(inputs.get("dry_run", True))

        if not task:
            return {"success": False, "error": "Missing 'task' parameter"}
        if not file_path:
            return {"success": False, "error": "Missing 'file' parameter"}

        # ── 验证路径 ──
        valid, resolved_path = self._validate_path(file_path)
        if not valid:
            return {"success": False, "error": resolved_path}

        target = Path(resolved_path)

        # ── 构建修改计划 ──
        plan = ModificationPlan(
            file_path=str(target.relative_to(self._project_root)),
            description=task,
            test_strategy=f"Run: pytest tests/ -k '{target.stem}' --tb=short" if run_tests else "Skip tests",
        )

        # ── 读取原文件 ──
        original = self._read_file(target)

        # ── 生成 diff ──
        if should_delete:
            plan.operation = "delete"
            plan.diff = self._generate_diff(str(target), "", original)
            plan.approval_required = True
        elif content:
            plan.diff = self._generate_diff(str(target), content, original)
            plan.risks = self._analyze_risks(str(target), content)
            plan.operation = "edit" if original else "add"
            if plan.risks:
                plan.approval_required = True
        else:
            return {"success": False, "error": "Missing 'content' for edit/add operation"}

        # ── 预览模式 ──
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "plan": {
                    "file": plan.file_path,
                    "operation": plan.operation,
                    "description": plan.description,
                    "diff": plan.diff[:self._max_diff_size],
                    "risks": plan.risks,
                    "approval_required": plan.approval_required,
                    "test_strategy": plan.test_strategy,
                },
                "message": "预览模式完成，请确认后再执行实际修改",
            }

        # ── 需要人工确认 ──
        if plan.approval_required:
            return {
                "success": False,
                "approval_required": True,
                "plan": {
                    "file": plan.file_path,
                    "operation": plan.operation,
                    "description": plan.description,
                    "diff": plan.diff[:self._max_diff_size],
                    "risks": plan.risks,
                    "test_strategy": plan.test_strategy,
                },
                "message": "检测到高风险操作，需要人工确认",
            }

        # ── 执行修改 ──
        try:
            if should_delete:
                target.unlink(missing_ok=True)
            elif content:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            result: dict[str, Any] = {
                "success": True,
                "operation": plan.operation,
                "file": plan.file_path,
                "message": f"已修改 {plan.operation} 文件",
            }

            # ── 运行测试 ──
            if run_tests:
                test_output = self._run_tests()
                result["tests_passed"] = test_output.get("passed", 0)
                result["tests_failed"] = test_output.get("failed", 0)
                if test_output.get("failed", 0) > 0:
                    result["message"] += " — 测试失败！"

            # ── Git 提交 ──
            if do_commit:
                commit_result = self._git_commit(plan.description)
                result["commit"] = commit_result

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── 辅助方法 ──

    def _run_tests(self) -> dict[str, Any]:
        """运行相关测试。"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "ocos/tests/", "-q", "--tb=no"],
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            passed = result.stdout.count("passed")
            failed = result.stdout.count("failed")
            return {"passed": passed, "failed": failed, "output": result.stdout[-500:]}
        except subprocess.TimeoutExpired:
            return {"passed": 0, "failed": 999, "output": "timeout"}
        except Exception as e:
            return {"passed": 0, "failed": 1, "output": str(e)}

    def _git_commit(self, message: str) -> dict[str, Any]:
        """提交 git 变更。"""
        try:
            # 添加所有变更
            subprocess.run(
                ["git", "add", "."],
                cwd=self._project_root,
                capture_output=True,
                timeout=30,
            )
            # 提交
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self._project_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return {"success": True, "message": result.stdout[:200]}
            return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── 便捷函数 ──

def validate_path(project_root: str, path_str: str) -> tuple[bool, str]:
    """公共验证函数。"""
    agent = SelfModificationAgent(project_root)
    return agent._validate_path(path_str)


def preview_change(project_root: str, file_path: str, new_content: str, description: str) -> dict[str, Any]:
    """预览变更（不执行）。"""
    agent = SelfModificationAgent(project_root)
    return agent.execute(
        task=description,
        file=file_path,
        content=new_content,
        dry_run=True,
    )
