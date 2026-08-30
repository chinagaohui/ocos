"""OCOS CLI — say/inbox 命令（UX-P2: 对话通道）。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession
from ocos.interaction.cli.paths import resolve_db_path


def cmd_say(args, session: InteractionSession) -> int:
    """ocos say "message" — 给运行中的认知引擎投递一条用户消息。

    消息落 user_messages 表，daemon 每 tick 消费并注入感知管道
    （HIGH 严重性，下一 tick 被 Step 1 摄入 → 注意力 → 认知循环）。
    处理结果经 ocos status / ocos trace show 观察。
    """
    from ocos.interaction.inbox import UserInbox

    text = args.message.strip()
    if not text:
        print("Usage: ocos say \"你的消息\"")
        return 1

    db_path = resolve_db_path(getattr(args, "db", None) or None)
    inbox = UserInbox(db_path=db_path)
    mid = inbox.post(text, sender="cli")
    queued = inbox.count_queued()
    print(f"Message queued: {mid}")
    print(f"  content : {text[:60]}{'...' if len(text) > 60 else ''}")
    print(f"  inbox   : {queued} 条待处理")
    print("  Next: 运行中的 daemon 将在下一 tick 注入认知循环")
    print("        观察处理过程: ocos status | ocos trace show")
    session.record_query()
    return 0


def cmd_inbox(args, session: InteractionSession) -> int:
    """ocos inbox [list] — 查看收件箱消息。"""
    from ocos.interaction.inbox import UserInbox

    db_path = resolve_db_path(getattr(args, "db", None) or None)
    inbox = UserInbox(db_path=db_path)
    rows = inbox.list_recent(limit=10)
    print(f"Inbox (recent {len(rows)}):")
    for r in rows:
        marker = {"queued": "…", "consumed": "✓"}.get(r["status"], " ")
        print(f"  [{marker}] {r['id']}  ({r['status']:>8})  {r['content'][:50]}")
    if not rows:
        print("  (empty — ocos say \"message\" 投递第一条)")
    session.record_query()
    return 0
