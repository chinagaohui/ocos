"""OCOS CLI — chat 命令（TUI交互界面）。

Usage:
    ocos chat              — 启动TUI交互界面
    ocos chat --help       — 查看帮助
"""

from __future__ import annotations


def cmd_chat(args, session=None) -> int:
    """ocos chat — 启动TUI交互界面。"""
    from ocos.interaction.tui import OCOSTUI
    
    app = OCOSTUI()
    app.run()
    return 0
