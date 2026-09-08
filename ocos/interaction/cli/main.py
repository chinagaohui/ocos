#!/usr/bin/env python3
"""OCOS CLI 入口 — `ocos` 命令。

用法:
    ocos goal create "帮我写一本科幻小说"
    ocos goal status GOAL-abc12345
    ocos goal list
    ocos plan "分析市场趋势" --domain analysis
    ocos memory query "科幻"
    ocos memory recent
    ocos belief list
    ocos belief summary
    ocos self status
    ocos self identity
    ocos trace show <id>

架构约束:
    CLI → InteractionContext → (EpisodeStore | BeliefStore | IdentityBoundary)
    入口不直接操作 Kernel Internal State。
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

from ocos.interaction.base import InteractionSession
from ocos.interaction.context import InteractionContext
from ocos.interaction.cli.commands.belief import cmd_belief_list, cmd_belief_summary
from ocos.interaction.cli.commands.decide import cmd_decide
from ocos.interaction.cli.commands.regulate import cmd_regulate
from ocos.interaction.cli.commands.feedback import cmd_feedback
from ocos.interaction.cli.commands.goal import cmd_goal_create, cmd_goal_list, cmd_goal_status
from ocos.interaction.cli.commands.memory import cmd_memory_query, cmd_memory_recent
from ocos.interaction.cli.commands.organ import (
    cmd_organ_accept,
    cmd_organ_generate,
    cmd_organ_projects,
    cmd_organ_reject,
    cmd_organ_resume,
    cmd_organ_rewrite,
    cmd_organ_status,
    cmd_organ_task,
    cmd_organ_verify,
)
from ocos.interaction.cli.commands.plan import cmd_plan
from ocos.interaction.cli.commands.run import cmd_run
from ocos.interaction.cli.commands.self import cmd_self
from ocos.interaction.cli.commands.trace import cmd_trace_show
from ocos.interaction.cli.parser import build_parser


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    session = InteractionSession(caller="cli")

    # CLI 每次调用创建新上下文，指向持久化 DB（P0：默认 ~/.ocos/ocos.db）
    db_path = os.environ.get("OCOS_DB_PATH", str(Path.home() / ".ocos" / "ocos.db"))
    ctx = InteractionContext(db_path=db_path)

    try:
        # ── Route to command ──────────────────────────────────────
        if args.command == "goal":
            if args.goal_action == "create":
                return cmd_goal_create(args, session)
            elif args.goal_action == "status":
                return cmd_goal_status(args, session)
            elif args.goal_action == "exec":
                from ocos.interaction.cli.commands.goal import cmd_goal_exec
                return cmd_goal_exec(args, session)
            elif args.goal_action == "list":
                return cmd_goal_list(args, session)
            else:
                parser.print_help()
                return 1

        elif args.command == "plan":
            return cmd_plan(args, session)

        elif args.command == "say":
            from ocos.interaction.cli.commands.say import cmd_say
            return cmd_say(args, session)

        elif args.command == "inbox":
            from ocos.interaction.cli.commands.say import cmd_inbox
            return cmd_inbox(args, session)

        elif args.command == "status":
            from ocos.interaction.cli.commands.status import cmd_status
            return cmd_status(args, session)

        elif args.command == "restart":
            from ocos.interaction.cli.commands.restart import cmd_restart
            return cmd_restart(args, session)

        elif args.command == "gateway":
            from ocos.interaction.cli.commands.restart import cmd_gateway
            return cmd_gateway(args, session)

        elif args.command == "approvals":
            from ocos.interaction.cli.commands.approvals import (
                cmd_approvals_list, cmd_approvals_approve, cmd_approvals_deny,
            )
            if args.approvals_action == "list":
                return cmd_approvals_list(args, session)
            elif args.approvals_action == "approve":
                return cmd_approvals_approve(args, session)
            elif args.approvals_action == "deny":
                return cmd_approvals_deny(args, session)
            else:
                parser.print_help()
                return 1

        elif args.command == "memory":
            if args.memory_action == "query":
                return cmd_memory_query(args, session, ctx)
            elif args.memory_action == "recent":
                return cmd_memory_recent(args, session, ctx)
            else:
                parser.print_help()
                return 1

        elif args.command == "belief":
            if args.belief_action == "list":
                return cmd_belief_list(args, session, ctx)
            elif args.belief_action == "summary":
                return cmd_belief_summary(args, session, ctx)
            else:
                parser.print_help()
                return 1

        elif args.command == "self":
            return cmd_self(args, session)

        elif args.command == "trace":
            if args.trace_action == "show":
                return cmd_trace_show(args, session)
            else:
                parser.print_help()
                return 1

        elif args.command == "organ":
            if args.organ_action == "generate":
                return cmd_organ_generate(args, session)
            elif args.organ_action == "resume":
                return cmd_organ_resume(args, session)
            elif args.organ_action == "rewrite":
                return cmd_organ_rewrite(args, session)
            elif args.organ_action == "verify":
                return cmd_organ_verify(args, session)
            elif args.organ_action == "status":
                return cmd_organ_status(args, session)
            elif args.organ_action == "projects":
                return cmd_organ_projects(args, session)
            elif args.organ_action == "task":
                return cmd_organ_task(args, session)
            elif args.organ_action == "accept":
                return cmd_organ_accept(args, session)
            elif args.organ_action == "reject":
                return cmd_organ_reject(args, session)
            else:
                parser.print_help()
                return 1

        elif args.command == "run":
            return cmd_run(args, session)

        elif args.command == "decide":
            return cmd_decide(args, session)

        elif args.command == "regulate":
            return cmd_regulate(args, session)

        elif args.command == "run":
            return cmd_run(args, session)

        elif args.command == "chat":
            from ocos.interaction.cli.commands.chat import cmd_chat
            return cmd_chat(args, session)

        elif args.command == "growth":
            from ocos.interaction.cli.commands.growth import cmd_growth
            return cmd_growth(args, session)

        elif args.command == "stop":
            from ocos.interaction.cli.commands.stop import cmd_stop
            return cmd_stop(args, session)

        elif args.command == "autonomy":
            from ocos.interaction.cli.commands.autonomy import cmd_autonomy
            return cmd_autonomy(args, session)

        elif args.command == "vitals":
            from ocos.interaction.cli.commands.vitals import cmd_vitals
            return cmd_vitals(args, session)

        else:
            parser.print_help()
            return 1

    finally:
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())
