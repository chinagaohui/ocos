"""OCOS CLI — regulate 命令实现（S7：自调节闭环）。

ocos regulate <project>        分析项目跨章趋势 → 调整建议（受控开关）
  --apply [chapter]            确认后应用调整（Organ rewrite + 指令）——审批链：人工确认
  --yes                        跳过交互确认（审批链显式授权）
  --mode auto|manual|off       覆盖受控开关（默认读 OCOS_SELF_REGULATION=manual）
"""

from __future__ import annotations

from ocos.opentale_bridge.organ_client import OrganClientError
from ocos.opentale_bridge.self_regulation import SelfRegulationLoop


def cmd_regulate(args, session) -> int:
    loop = SelfRegulationLoop(
        organ_base=getattr(args, "base_url", "http://127.0.0.1:8000/api/organ"))
    try:
        trends, adjustment = loop.adjust(args.project, max_chapters=args.max_chapters)
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1

    print(f"项目《{args.project}》自调节分析：")
    print(loop.describe(trends, adjustment))

    if not args.apply:
        print("\n应用调整：ocos regulate <project> --apply [chapter]（需人工确认，审批链）")
        return 0

    chapter = args.apply if isinstance(args.apply, int) else None
    if chapter is None:
        # 未指定章节 → 应用到最后一章（当前进度点）
        try:
            report = loop.organ.project(args.project)
            chapter = int(report.get("chapters") or 0)
        except OrganClientError:
            chapter = 1
        if chapter < 1:
            chapter = 1

    # 审批链：人工确认
    if not args.yes:
        print(f"\n⚠️  将把调整应用到第 {chapter} 章（Organ rewrite）。")
        print("确认？[y/N] ", end="", flush=True)
        try:
            answer = input().strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("y", "yes"):
            print("已取消（未应用）。")
            return 0

    try:
        result = loop.apply(args.project, chapter, adjustment)
    except OrganClientError as e:
        print(f"应用失败: {e}")
        return 1

    if result.get("status") == "applied":
        print(f"✅ 已应用调整（{result['mode']} 模式）→ 任务 {result.get('task_id')}")
        print(f"   指令: {result.get('instruction', '')[:200]}")
        print("   轮询: /api/organ/tasks/" + str(result.get("task_id", "")))
        return 0
    print(f"⏭ 未应用: {result.get('reason', result.get('status'))}")
    return 0
