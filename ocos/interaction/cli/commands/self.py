"""OCOS CLI — self 命令（自我修改能力）。

Usage:
    ocos self mod --file "path" --content "..." --task "description" [--dry-run]
    ocos self preview --file "path" --content "..." --task "description"
    ocos self validate --file "path"
"""

from __future__ import annotations

import sys
from pathlib import Path

from ocos.interaction.base import InteractionSession
from ocos.interaction.cli.paths import resolve_db_path
from ocos.capability.agents.self_modification_agent import SelfModificationAgent


def cmd_self(args, session: InteractionSession) -> int:
    """OCOS 自我修改入口。"""
    subcommand = getattr(args, "self_action", None)

    if subcommand == "mod":
        return cmd_self_mod(args, session)
    elif subcommand == "preview":
        return cmd_self_preview(args, session)
    elif subcommand == "validate":
        return cmd_self_validate(args, session)
    else:
        print("Usage:")
        print('  ocos self mod --file "path" --content "..." --task "description"')
        print('  ocos self preview --file "path" --content "..." --task "description"')
        print('  ocos self validate --file "path"')
        return 1


def cmd_self_mod(args, session: InteractionSession) -> int:
    """执行实际修改（测试模式，dry_run=True）。"""
    file_path = getattr(args, "file", "")
    content = getattr(args, "content", "")
    task = getattr(args, "task", "")

    if not file_path:
        print("Error: --file is required")
        return 1
    if not content and not getattr(args, "delete", False):
        print("Error: --content is required (or --delete)")
        return 1
    if not task:
        print("Error: --task is required")
        return 1

    # 自动找到项目根目录
    project_root = _find_project_root()

    agent = SelfModificationAgent(project_root)

    print(f"[SelfMod] Task: {task}")
    print(f"[SelfMod] File: {file_path}")
    print(f"[SelfMod] Mode: {'DRY RUN' if getattr(args, 'dry_run', True) else 'LIVE'}")
    print("-" * 60)

    result = agent.execute(
        task=task,
        file=file_path,
        content=content,
        delete=bool(getattr(args, "delete", False)),
        dry_run=bool(getattr(args, "dry_run", True)),
        test=False,  # 安全模式，不自动运行测试
        commit=False,
    )

    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_self_preview(args, session: InteractionSession) -> int:
    """预览修改（等价于 dry_run=True）。"""
    return cmd_self_mod(args, session)


def cmd_self_validate(args, session: InteractionSession) -> int:
    """验证文件路径是否可修改。"""
    file_path = getattr(args, "file", "")
    if not file_path:
        print("Error: --file is required")
        return 1

    project_root = _find_project_root()
    agent = SelfModificationAgent(project_root)

    valid, resolved = agent._validate_path(file_path)
    print(f"Path: {file_path}")
    print(f"Valid: {valid}")
    if valid:
        print(f"Resolved: {resolved}")
        # 检查风险
        target = Path(resolved)
        if target.exists():
            content = target.read_text(encoding="utf-8")
            risks = agent._analyze_risks(str(target.relative_to(project_root)), content)
            if risks:
                print("\nRisks:")
                for r in risks:
                    print(f"  - {r}")
            else:
                print("\nNo high-risk patterns detected.")
        else:
            print("\nFile does not exist yet (will be created).")
    else:
        print(f"Error: {resolved}")
    return 0 if valid else 1


def _print_result(result: dict) -> None:
    """打印结果。"""
    if result.get("success"):
        if result.get("dry_run"):
            print("[Dry Run] Preview complete:")
            plan = result.get("plan", {})
            if plan:
                print(f"  Operation: {plan.get('operation')}")
                print(f"  File: {plan.get('file')}")
                print(f"  Approval required: {plan.get('approval_required')}")
                if plan.get("diff"):
                    print("\n  Diff:")
                    print("  " + "\n  ".join(plan["diff"][:500].split("\n")))
                if plan.get("risks"):
                    print("\n  Risks:")
                    for r in plan["risks"]:
                        print(f"    - {r}")
        else:
            print("[Live] Modification complete!")
            print(f"  Operation: {result.get('plan', {}).get('operation')}")
            print(f"  File: {result.get('plan', {}).get('file')}")
            if result.get("tests_passed"):
                print(f"  Tests passed: {result['tests_passed']}")
            if result.get("commit"):
                print(f"  Commit: {result['commit'].get('message', '')[:80]}")
    else:
        print(f"[Error] {result.get('error', 'Unknown error')}")
        if result.get("approval_required"):
            print("  Action required: This modification needs human approval.")
            print("  Re-run with approval confirmed.")


def _find_project_root() -> str:
    """查找项目根目录。"""
    # 从当前目录向上查找 pyproject.toml
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents)[:5]:
        if (parent / "pyproject.toml").exists():
            return str(parent)
    # 默认使用 ocos 目录
    default = Path("/home/laogao/Documents/trae_projects/ocos")
    if default.exists():
        return str(default)
    return str(cwd)
