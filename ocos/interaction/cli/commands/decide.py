"""OCOS CLI — decide 命令实现（S5：MasterAgent 真实写作决策）。

从 ocos 入口：写作意图 → 真实决策（focus/tone/pacing/chapter_goal）→
可选执行：决策 → Organ generate（设定契约随请求绑定）。
"""

from __future__ import annotations

from ocos.opentale_bridge.master_agent import MasterAgent, WritingIntent
from ocos.opentale_bridge.organ_client import OrganClient, OrganClientError


def cmd_decide(args, session) -> int:
    """ocos decide "大纲" [--title 书名] [--genre 题材] [--character 角色] ..."""
    roles: dict[str, str] = {}
    for r in args.role:
        if "=" in r:
            name, role = r.split("=", 1)
            roles[name.strip()] = role.strip()

    intent = WritingIntent(
        premise=args.input,
        title=args.title,
        genre=args.genre,
        characters=list(args.character),
        roles=roles,
        world=list(args.world),
        focus_hint=args.focus,
        tone_hint=args.tone,
        pacing_hint=args.pacing,
        total_chapters=args.chapters,
    )

    ma = MasterAgent()
    decision = ma.decide(intent, chapter=1)
    print("OCOS MasterAgent 写作决策:")
    print(ma.summary(decision))

    if args.exec:
        return _exec_generate(args, intent)
    if not args.exec and args.preview:
        print("\n[--preview] 决策 → Organ 设定契约:")
        contract = ma.to_organ_contract(intent)
        print(f"  title={contract['title']} genre={contract['genre']} chapters={contract['chapters']}")
        print(f"  characters={contract['characters']} roles={contract['roles']}")
        print(f"  world={contract['world']}")
        print(f"  focus/tone/pacing → {decision.primary_focus}/{decision.emotional_tone}/{decision.pacing_directive}")
    return 0


def _exec_generate(args, intent: WritingIntent) -> int:
    """决策 → Organ generate（真实写作）。"""
    client = OrganClient(base_url=args.base_url)
    ma = MasterAgent()
    contract = ma.to_organ_contract(intent)
    try:
        resp = client.generate(
            title=contract["title"], content=contract["content"],
            genre=contract["genre"], chapters=contract["chapters"],
            target_words=contract["target_words"],
            characters=contract["characters"], roles=contract["roles"],
            world=contract["world"],
        )
    except OrganClientError as e:
        print(f"Organ 调用失败: {e}")
        return 1
    print(f"\n已提交生成任务: {resp['task_id']}")
    print(f"轮询: {resp['poll']}")
    if args.wait:
        from ocos.opentale_bridge.organ_client import OrganTaskTimeout

        print(f"轮询任务 {resp['task_id']}（间隔 {client.poll_interval_seconds}s）...")
        try:
            t = client.wait(resp["task_id"])
        except OrganTaskTimeout as e:
            print(f"⏳ {e}")
            return 1
        except OrganClientError as e:
            print(f"轮询失败: {e}")
            return 1
        if t.get("status") == "completed":
            print(f"✅ 完成: {t.get('result', '')[:200]}")
            return 0
        print(f"任务终态: {t.get('status')} — {t.get('error', '')[:200]}")
        return 1
    return 0
