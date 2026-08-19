"""OCOS REPL Shell — 认知观察入口。"""

from __future__ import annotations

import cmd
import os
import sys

from ocos.interaction.base import InteractionSession
from ocos.interaction.context import InteractionContext


class OcosShell(cmd.Cmd):
    """OCOS 交互式认知观察壳。"""

    intro = """
╔══════════════════════════════════════════════════════════════╗
║                 OCOS Digital Brain v1.1                     ║
║              Cognitive Interface Layer — REPL                ║
║                                                            ║
║  Type /help for commands.                                   ║
║  Enter a goal directly to create one.                       ║
║  Type exit or Ctrl+D to quit.                               ║
╚══════════════════════════════════════════════════════════════╝
"""
    prompt = "\nOCOS > "

    def __init__(self):
        super().__init__()
        self.session = InteractionSession(caller="repl")

        # REPL 持有持久化上下文（长连接）
        db_path = os.environ.get("OCOS_DB_PATH", "ocos.db")
        self.ctx = InteractionContext(db_path=db_path)

        self._init_commands()

    def _init_commands(self):
        from ocos.interaction.repl.commands.plan import ReplPlanCommand
        from ocos.interaction.repl.commands.memory import ReplMemoryCommand
        from ocos.interaction.repl.commands.belief import ReplBeliefCommand
        from ocos.interaction.repl.commands.goal import ReplGoalCommand
        from ocos.interaction.repl.commands.self_cmd import ReplSelfCommand
        from ocos.interaction.repl.commands.trace import ReplTraceCommand
        from ocos.interaction.repl.commands.help import ReplHelpCommand

        self._plan_cmd = ReplPlanCommand(self.session)
        self._memory_cmd = ReplMemoryCommand(self.session, self.ctx)
        self._belief_cmd = ReplBeliefCommand(self.session, self.ctx)
        self._goal_cmd = ReplGoalCommand(self.session, self.ctx)
        self._self_cmd = ReplSelfCommand(self.session, self.ctx)
        self._trace_cmd = ReplTraceCommand(self.session)
        self._help_cmd = ReplHelpCommand(self.session)

    def do_plan(self, arg: str):
        self._plan_cmd.execute(arg)

    def do_memory(self, arg: str):
        self._memory_cmd.execute(arg)

    def do_belief(self, arg: str):
        self._belief_cmd.execute(arg)

    def do_goal(self, arg: str):
        self._goal_cmd.execute(arg)

    def do_self(self, arg: str):
        self._self_cmd.execute(arg)

    def do_trace(self, arg: str):
        self._trace_cmd.execute(arg)

    def do_help(self, arg: str):
        self._help_cmd.execute(arg)

    def precmd(self, line: str) -> str:
        """Strip leading / to support /command syntax."""
        if line.startswith("/"):
            line = line[1:]
        return line

    def default(self, line: str):
        if not line.strip():
            return
        self._plan_cmd.execute(line)

    def do_exit(self, arg: str):
        print(f"\nSession: {self.session.summary['goals_created']} goals, "
              f"{self.session.summary['queries_made']} queries.")
        self.ctx.close()
        print("Goodbye.")
        return True

    def do_quit(self, arg: str):
        return self.do_exit(arg)

    def do_EOF(self, arg: str):
        print()
        return self.do_exit(arg)

    def emptyline(self) -> bool:
        return False


def main():
    try:
        shell = OcosShell()
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\n\nGoodbye.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
