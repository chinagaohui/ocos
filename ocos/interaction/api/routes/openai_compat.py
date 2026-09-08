"""OpenAI 兼容 chat/completions 端点 — 将第三方 TUI(如 gptme/llm)直接接入 OCOS。

复用 ChatResponder 的回复逻辑（respond_auto / respond_stream），把
OpenAI 请求格式翻译成 OCOS 对话能力，从而"套现成前端"作为 ocos chat 外壳。

- POST /v1/chat/completions（兼容 OpenAI/DeepSeek 格式）
  - stream=false: 一次性 JSON（choices[0].message.content）
  - stream=true:  SSE 增量（data: chunk → data: [DONE]）

设计要点：
- 对话历史由 OCOS 自建（build_context + 记忆），并不把 messages 数组整段
  喂给底层 LLM；仅取最后一个 user 消息发起一轮对话。
- 会话 id：请求可带自定义字段 session_id，缺省 "openai"（OCOS 记忆/状态归属）。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ocos.interaction.cli.paths import resolve_db_path

router = APIRouter()


def _db() -> str:
    return resolve_db_path()


def _chat_completion_object(model: str, content: str) -> dict[str, Any]:
    """非流式响应的 OpenAI 结构。"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
    }


def _stream_chunk(model: str, delta: str, finish: bool = False) -> str:
    """单块流式帧（OpenAI chunk 结构）。"""
    data = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {"content": delta} if delta else {},
            "finish_reason": "stop" if finish else None,
        }],
    }
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/v1/chat/completions", tags=["openai"])
async def chat_completions(body: dict[str, Any]):
    """OpenAI 兼容对话端点（含流式 SSE）。"""
    stream = bool(body.get("stream", False))
    messages = body.get("messages", [])
    user_msgs = [m for m in messages if m.get("role") == "user" and str(m.get("content", "")).strip()]
    if not user_msgs:
        raise HTTPException(status_code=400, detail="no user message provided")
    message = str(user_msgs[-1]["content"]).strip()
    model = str(body.get("model", "") or "ocos")
    # OpenAI 协议无 session_id 概念 → 允许自定义字段；缺省归并到 "openai"
    session_id = str(body.get("session_id", "") or "").strip()[:64] or "openai"
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")

    from ocos.interaction.converse import (ChatResponder,
                                           make_default_tool_executor)
    responder = ChatResponder(db_path=_db(),
                              tool_executor=make_default_tool_executor(_db()))

    if not stream:
        out = await asyncio.to_thread(
            responder.respond_auto, message, session_id=session_id)
        return _chat_completion_object(model, out["reply"])

    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    main_loop = asyncio.get_running_loop()

    def emit(text: str) -> None:
        main_loop.call_soon_threadsafe(q.put_nowait, ("text", text))

    def _worker() -> None:
        try:
            responder.respond_auto(message, session_id=session_id, _emit=emit)
            main_loop.call_soon_threadsafe(q.put_nowait, ("done", ""))
        except Exception as e:  # noqa: BLE001
            main_loop.call_soon_threadsafe(
                q.put_nowait, ("error", f"{type(e).__name__}: {e}"))

    worker = asyncio.create_task(asyncio.to_thread(_worker))

    async def _gen():
        try:
            while True:
                kind, payload = await q.get()
                if kind == "text":
                    yield _stream_chunk(model, payload)
                elif kind == "done":
                    yield _stream_chunk(model, "", finish=True)
                    yield "data: [DONE]\n\n"
                    break
                else:  # error
                    yield _stream_chunk(model, "（错误） " + payload)
                    yield "data: [DONE]\n\n"
                    break
        finally:
            worker.cancel()

    return StreamingResponse(_gen(), media_type="text/event-stream")