"""OCOS REPL — help 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession


class ReplHelpCommand:
    """REPL /help 命令 — 显示帮助。"""

    def __init__(self, session: InteractionSession):
        self.session = session
        self.guard = PermissionGuard()

    def execute(self, arg: str) -> None:
        topic = arg.strip().lower()

        help_text = {
            "plan": "/plan <description> — 创建 Goal 并启动规划\n  Example: /plan 帮我分析科幻小说市场趋势",
            "memory": "/memory [query] — 查看近期记忆\n  Examples:\n    /memory          → 最近 10 条 Episode\n    /memory 科幻     → 搜索关键词",
            "belief": "/belief [filter] — 查看活跃信念\n  Examples:\n    /belief            → 全列表（按置信度排序）\n    /belief self       → 只显示 self 域",
            "goal": "/goal [id] — 目标状态或目标树\n  Examples:\n    /goal              → 当前会话目标树\n    /goal GOAL-abc12345 → 单个目标详情",
            "self": "/self — 查看 SelfModel 状态\n  包括：capability_states, maturity, boundary principles",
            "trace": "/trace <id> — 查看决策追踪\n  Example: /trace TRACE-001",
            "exit": "exit 或 quit 或 Ctrl+D — 退出 REPL",
        }

        if topic and topic in help_text:
            print(f"\n  {help_text[topic]}")
            return

        print(f"""
  OCOS REPL Commands
  ══════════════════════════════════════════════════
  /plan <desc>   — Create a goal and start planning
  /memory [q]    — View recent memory episodes
  /belief [f]    — View active beliefs
  /goal [id]     — View goal tree or goal detail
  /self          — View SelfModel status
  /trace <id>    — View decision trace
  /help [cmd]    — Show this help
  exit/quit/Ctrl+D — Exit REPL

  You can also type a goal description directly:
     帮我写一本科幻小说     →  creates a goal and plans

  Type /help <command> for detailed help.
""")
