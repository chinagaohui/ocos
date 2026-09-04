"""OCOS CLI — chat 命令（TUI交互界面）。

Usage:
    ocos chat                        — 启动TUI（Hermes Agent 风格）
    ocos chat -c                     — 恢复最近会话（--continue）
    ocos chat -r <id|title>          — 恢复指定会话（--resume）
    ocos chat --host H --port P      — 指定 API 地址
"""

from __future__ import annotations

import sys


def cmd_chat(args, session=None) -> int:
    """ocos chat — 启动TUI交互界面（复刻 Hermes Agent CLI）。"""
    from ocos.interaction.tui import run_tui

    resume = getattr(args, "resume", None) or (
        "continue" if getattr(args, "continue_", False) else None)
    run_tui(resume=resume, host=args.host, port=args.port,
            mouse=getattr(args, "mouse", False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)
