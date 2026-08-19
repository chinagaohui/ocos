"""OCOS REPL — Tab 自动补全。

支持命令和子参数的自动补全。
"""

from __future__ import annotations

import re

REPL_COMMANDS = [
    "plan",
    "memory",
    "belief",
    "goal",
    "self",
    "trace",
    "help",
    "exit",
    "quit",
]

COMMAND_DESCRIPTIONS = {
    "plan": "Create a goal and start planning",
    "memory": "View recent memory episodes",
    "belief": "View active beliefs",
    "goal": "View goal tree or goal detail",
    "self": "View SelfModel status",
    "trace": "View decision trace",
    "help": "Show help for commands",
    "exit": "Exit REPL",
    "quit": "Exit REPL",
}


def complete_command(text: str) -> list[str]:
    """返回匹配前缀的命令列表。"""
    if not text:
        return REPL_COMMANDS[:]
    return [c for c in REPL_COMMANDS if c.startswith(text)]


def complete_path(text: str) -> list[str]:
    """文件路径补全（预留，当前未使用）。"""
    return []


class ReplCompleter:
    """REPL 自动补全器。

    用于 readline 设置，提供 Tab 补全。
    """

    def __init__(self):
        self.commands = REPL_COMMANDS

    def complete(self, text: str, state: int) -> str | None:
        """readline completer 接口。

        返回第 state 个匹配项，或 None 表示结束。
        """
        line = self._get_line_buffer()
        stripped = line.lstrip()

        # 第一词：命令补全
        if not stripped or (stripped == "/" and not text):
            options = ["/" + c for c in self.commands]
        elif stripped == "/" and text:
            options = ["/" + c for c in self.commands if c.startswith(text)]
        elif stripped.startswith("/") and " " not in stripped:
            # /comm → 命令补全
            prefix = stripped[1:]  # 去掉 /
            options = ["/" + c for c in self.commands if c.startswith(prefix + text)]
        else:
            options = []

        if state < len(options):
            return options[state]
        return None

    def _get_line_buffer(self) -> str:
        """获取当前输入行的内容。"""
        try:
            import readline
            return readline.get_line_buffer()
        except (ImportError, AttributeError):
            return ""
