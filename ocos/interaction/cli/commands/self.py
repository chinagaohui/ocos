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

    if subcommand == "status":
        return cmd_self_status(args, session)
    elif subcommand == "identity":
        return cmd_self_identity(args, session)
    elif subcommand == "review":
        return cmd_self_review(args, session)
    elif subcommand == "mod":
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


def cmd_self_status(args, session: InteractionSession) -> int:
    """显示自我状态。"""
    from ocos.capability.agents.self_modification_agent import SelfModificationAgent
    import sys

    project_root = _find_project_root()
    agent = SelfModificationAgent(project_root)

    print("=" * 60)
    print("OCOS Self-Modification Capability Status")
    print("=" * 60)
    print(f"Project Root: {project_root}")
    print(f"Python: {sys.version.split()[0]}")
    print()
    print("Safe Directories (can modify):")
    for d in ["ocos/", "tests/", "docs/"]:
        print(f"  ✓ {d}")
    print()
    print("Forbidden Directories (blocked):")
    for d in [".venv/", ".git/", "__pycache__/"]:
        print(f"  ✗ {d}")
    print()
    print("High-Risk Patterns (require approval):")
    for p in ["import os", "subprocess", "open(", "write_file", "system()"]:
        print(f"  ⚠ {p}")
    print()
    print("Status: ENABLED (dry-run mode active)")
    return 0


def cmd_self_review(args, session: InteractionSession) -> int:
    """ocos self review — 自省分析: 采集证据 → LLM 综合 → 报告落盘。

    纯只读 (mode=ro sqlite + LLM 文本分析), 零变异。
    """
    from ocos.reflection.self_review import (
        SelfReviewCollector, SelfReviewAnalyzer, render_markdown, write_report,
    )

    print("自省分析: 采集运行证据 (只读)...")
    collector = SelfReviewCollector()
    ev = collector.collect()
    print(f"  证据: {ev.episodes_total} episodes "
          f"(✓{ev.episodes_success}/✗{ev.episodes_failed}), "
          f"{ev.goals_by_status.get('COMPLETED', 0)} completed goals, "
          f"{ev.beliefs_total} beliefs, DLQ={ev.dlq_count}")
    print(f"  代码资产: {len(ev.capability_modules)} 模块, "
          f"学习引擎={ev.learning_engine_present}, 成长={ev.growth_module_present}, "
          f"HEAD {ev.git_head or '?'}")
    print(f"  证据自检: {'✅ ' + ev.evidence_note if ev.evidence_consistent else '⚠️ ' + ev.evidence_note}")
    print("\n  失败模式 (全量 / 近7天):")
    all_pat = {p["pattern"]: p["count"] for p in ev.failure_patterns}
    pat7 = {p["pattern"]: p["count"] for p in ev.failure_patterns_7d}
    for pat, cnt in all_pat.items():
        d7 = pat7.get(pat, 0)
        marker = " ← 现存" if d7 > 0 else ""
        print(f"    - {pat} ×{cnt} (7d: ×{d7}){marker}")

    print("\nLLM 综合分析中...")
    analyzer = SelfReviewAnalyzer()
    analysis = analyzer.analyze(ev)
    if "error" in analysis or "raw" in analysis:
        print(f"  LLM 分析失败: {analysis}")
        return 1

    print(f"\n== 总体健康: {analysis.get('overall_health', '(无)')} ==")
    print("\n不足:")
    for w in analysis.get("weaknesses", []):
        print(f"  - {w.get('issue', '')} [证据: {w.get('evidence', '')[:80]}]")
    print("\n升级方向:")
    for u in analysis.get("upgrades", []):
        print(f"  - [{u.get('priority', 'P2')}] {u.get('upgrade', '')}")
    print(f"\n最大瓶颈: {analysis.get('biggest_bottleneck', '(无)')}")

    md = render_markdown(ev, analysis)
    path = write_report(md)
    print(f"\n报告已生成: {path}")
    return 0


def cmd_self_identity(args, session: InteractionSession) -> int:
    """显示身份边界。"""
    from ocos.capability.agents.self_modification_agent import SelfModificationAgent

    project_root = _find_project_root()
    agent = SelfModificationAgent(project_root)

    print("=" * 60)
    print("OCOS Identity Boundary")
    print("=" * 60)
    print()
    print("Self-Modification Policy:")
    print("  - Can modify: source code in ocos/, tests/, docs/")
    print("  - Cannot modify: .venv/, .git/, config.json, .env")
    print("  - High-risk operations require human approval")
    print("  - All changes are logged with diff preview")
    print()
    print("ABI Signature:")
    print("  execute(task, file, content, dry_run=True) -> dict")
    print()
    print("Security Boundaries:")
    print(f"  Forbidden dirs: {', '.join(agent.FORBIDDEN_DIRS)}")
    print(f"  Forbidden files: {', '.join(agent.FORBIDDEN_FILES)}")
    print(f"  Allowed extensions: {', '.join(agent.ALLOWED_EXTENSIONS)}")
    print()
    return 0


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

    # dry_run 优先级: --live 覆盖 --dry-run
    use_live = getattr(args, "live", False)
    use_dry_run = not use_live and getattr(args, "dry_run", True)

    print(f"[SelfMod] Task: {task}")
    print(f"[SelfMod] File: {file_path}")
    print(f"[SelfMod] Mode: {'LIVE' if use_live else 'DRY RUN'}")
    print("-" * 60)

    result = agent.execute(
        task=task,
        file=file_path,
        content=content,
        delete=bool(getattr(args, "delete", False)),
        dry_run=use_dry_run,
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
