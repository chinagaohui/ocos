"""OCOS CLI — chat 命令（纯前端 TUI 交互客户端）。

架构：本命令只启动《纯前端》终端客户端，经 WebSocket 连后台常驻 Gateway，
仅收发/渲染 JSON 事件；所有业务（LLM/记忆/决策/目标）都在 Gateway 内核。

Usage:
    ocos chat                      — 启动纯前端 TUI（连 ws://<host>:<port>/ws）
    ocos chat --host H --port P    — 指定网关地址
"""

from __future__ import annotations

import sys


def cmd_chat(args, session=None) -> int:
    """ocos chat — 启动纯前端 TUI 客户端（连接后台 Gateway 事件网关）。"""
    # 仅启动交互客户端；内核（ocos-server + ocos-daemon）独立常驻，不受本进程开关影响。
    from ocos.tui.tui_client import OcosTuiFrontend

    host = getattr(args, "host", "127.0.0.1")
    port = int(getattr(args, "port", 8900) or 8900)
    OcosTuiFrontend(url=f"ws://{host}:{port}/ws").run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(0)