"""ocos.tui.ws_client — Gateway WebSocket 桥接层（无业务逻辑）。

只做：连接 / 断线自动重连 / 收发 JSON。TUI 借此与后台内核通信，
不涉及任何 OCOS 内核业务知识。
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import websockets


def default_token() -> str:
    """读取网关访问 token（纯配置读取，非业务逻辑）。"""
    tok = os.environ.get("OCOS_API_TOKEN", "")
    if tok:
        return tok
    try:
        cfg = json.loads((Path.home() / ".ocos" / "config.json").read_text("utf-8"))
        return str(cfg.get("api", {}).get("token", ""))
    except Exception:
        return ""


class OcosWsClient:
    """面向 Gateway 事件流的纯客户端：自动重连、发送消息、迭代事件。"""

    def __init__(self, url: str = "ws://127.0.0.1:8900/ws", token: str = "") -> None:
        self._base = url
        self._token = token or default_token()
        self._ws: Any | None = None
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def _url(self) -> str:
        if self._token and "?" not in self._base:
            return f"{self._base}?token={quote(self._token)}"
        return self._base

    async def _open(self) -> None:
        self._ws = await websockets.connect(
            self._url(), ping_interval=20, ping_timeout=20,
            max_queue=None, close_timeout=2, open_timeout=15)

    async def _close(self) -> None:
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def send(self, obj: dict) -> None:
        ws = self._ws
        if ws is not None:
            try:
                await ws.send(json.dumps(obj, ensure_ascii=False))
            except Exception:
                raise

    async def run(self, on_event, on_status) -> None:
        """事件循环：连接 → 迭代事件 → 断线重连。on_event 为 async 回调。"""
        while not self._stop:
            try:
                await self._open()
                on_status("connected")
                async for raw in self._ws:
                    if self._stop:
                        break
                    try:
                        ev = json.loads(raw)
                    except (TypeError, ValueError):
                        continue
                    await on_event(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                on_status(f"disconnected({type(e).__name__})")
            finally:
                await self._close()
            if self._stop:
                break
            on_status("connecting…")
            await asyncio.sleep(2.0)