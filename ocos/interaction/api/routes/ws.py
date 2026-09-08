"""OCOS Gateway 事件网关 — WebSocket 端点，纯前端 TUI 的唯一入口。

TUI 经 ws://127.0.0.1:<port>/ws 连接，只收发 JSON 事件；
全部业务（LLM/记忆/决策/工具）在 gateway 后台执行，TUI 无任何业务代码。

事件协议（TUI 仅格式化渲染，不解析业务含义）:
  TUI → Gateway  {type, text, session_id, ...}
  Gateway → TUI {kind: user_message | agent_delta | agent_done | status | error | goal_result | system}
"""

from __future__ import annotations

import asyncio
import logging
import queue
import uuid
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ocos.interaction.api.auth import get_api_token
from ocos.interaction.cli.paths import resolve_db_path

logger = logging.getLogger("ocos.ws_gateway")

router = APIRouter()


def _db() -> str:
    return resolve_db_path()


def _auth_ok(token: str) -> bool:
    try:
        return bool(token) and token == get_api_token()
    except Exception:
        return False


# ── 会话分配：Gateway 持久化默认会话，TUI 关闭/重连仍回到同一会话 ──

_SESSION_FILE = Path.home() / ".ocos" / "gateway_session"


def _resolve_session() -> tuple[str, bool]:
    """返回 (session_id, is_new)。首次生成并持久化，之后保持不变。"""
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _SESSION_FILE.exists():
            sid = _SESSION_FILE.read_text(encoding="utf-8").strip()
            if sid:
                return sid, False
        sid = f"S-{uuid.uuid4().hex[:12]}"
        _SESSION_FILE.write_text(sid, encoding="utf-8")
        return sid, True
    except Exception:
        return "default", False


def _history_messages(session_id: str, limit: int = 30) -> list[dict]:
    """读取某会话最近对话，构造成 {role, content} 序列（DateTime 升序）。"""
    try:
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(_db())
        store.initialize()
        eps = store.query_by_session(session_id, limit=limit)
    except Exception as e:  # noqa: BLE001
        logger.warning("history load failed: %s", e)
        return []
    msgs: list[dict] = []
    for ep in eps:
        ctx = getattr(ep, "context", None) or {}
        user = ctx.get("content", "") if isinstance(ctx, dict) else ""
        reply = str(getattr(ep, "decision", "") or "")
        if user:
            msgs.append({"role": "user", "content": user})
        if reply:
            msgs.append({"role": "assistant", "content": reply})
    return msgs


class WsHub:
    """维护所有已连接 TUI：广播 daemon 目标结果事件到各客户端。"""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._cursor = 0
        self._task: asyncio.Task | None = None

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_outbox())

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: dict) -> None:
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_json(event)
            except Exception:
                await self.unregister(ws)

    async def _poll_outbox(self) -> None:
        """daemon 主动消息（目标结果）推给所有连接的 TUI。"""
        while True:
            try:
                await asyncio.sleep(2)
                from ocos.interaction.inbox import UserInbox
                rows = UserInbox(db_path=_db()).list_outbound_after(self._cursor)
                for row in rows:
                    self._cursor = max(self._cursor, row.get("rid", 0))
                    if row.get("sender") == "ocos":
                        await self.broadcast({
                            "kind": "goal_result",
                            "text": str(row.get("content", "")),
                            "ts": row.get("ts", ""),
                        })
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                logger.warning("outbox poll failed: %s", e)


hub = WsHub()


def _run_respond(responder, text: str, session_id: str, emit, q):
    """在工作线程里跑 respond（emit 桥回事件循环；q 为线程安全 queue.Queue）。"""
    try:
        out = responder.respond_auto(text, session_id=session_id, _emit=emit)
        q.put(("done", out))
    except asyncio.CancelledError:
        q.put(("error", "cancelled"))
    except Exception as e:  # noqa: BLE001
        q.put(("error", f"{type(e).__name__}: {e}"))
    q.put(("quit-token", None))


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    token = ws.query_params.get("token", "")
    if not _auth_ok(token):
        await ws.close(code=4401)
        return
    await ws.accept()
    await hub.register(ws)
    sid, is_new = _resolve_session()
    await ws.send_json({"kind": "session", "session_id": sid, "is_new": is_new})
    await ws.send_json({"kind": "status", "state": "connected"})
    try:
        while True:
            raw = await ws.receive_json()
            req_type = raw.get("type")
            session_id = str(raw.get("session_id", "") or sid or "")[:64]
            if req_type == "chat":
                asyncio.create_task(_handle_chat(ws, raw, session_id))
            elif req_type == "ping":
                await ws.send_json({"kind": "pong"})
            elif req_type == "abort":
                await ws.send_json({"kind": "system", "text": "abort 请求已转发（当前为前端占位）"})
            elif req_type == "history":
                msgs = _history_messages(session_id)
                await ws.send_json({"kind": "history", "session_id": session_id,
                                    "messages": msgs})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await hub.unregister(ws)


async def _handle_chat(ws: WebSocket, raw: dict, session_id: str) -> None:
    text = str(raw.get("text", "")).strip()
    if not text:
        return
    session_id = session_id or "default"

    from ocos.interaction.converse import (ChatResponder,
                                           make_default_tool_executor)
    responder = ChatResponder(db_path=_db(),
                              tool_executor=make_default_tool_executor(_db()))

    await ws.send_json({"kind": "user_message", "text": text})
    await ws.send_json({"kind": "status", "state": "running"})

    q: queue.Queue = queue.Queue()
    loop = asyncio.get_running_loop()

    def emit(chunk: str) -> None:
        loop.call_soon_threadsafe(q.put, ("delta", chunk))

    worker = asyncio.create_task(asyncio.to_thread(
        _run_respond, responder, text, session_id, emit, q))

    try:
        while True:
            kind, payload = await asyncio.to_thread(q.get)
            if kind == "quit-token":
                break
            if kind == "delta":
                await ws.send_json({"kind": "agent_delta", "chunk": str(payload)})
            elif kind == "done":
                out = payload if isinstance(payload, dict) else {}
                await ws.send_json({
                    "kind": "agent_done",
                    "reply": str(out.get("reply", "")),
                    "provider": out.get("provider"),
                    "model": out.get("model"),
                    "usage": out.get("usage"),
                    "goal_id": out.get("goal_id"),
                })
                break
            else:  # error
                await ws.send_json({"kind": "error", "msg": str(payload)})
                break
    finally:
        worker.cancel()
        await ws.send_json({"kind": "status", "state": "idle"})