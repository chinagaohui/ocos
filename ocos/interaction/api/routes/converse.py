"""UX-P2 Web: 对话/状态/审批路由 — Web UI 与外部前端的数据面。

与 CLI/REPL 共用同一命令核心（ChatResponder/PendingStore/GoalStore），
消除三入口实现漂移。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ocos.interaction.api.models import APIResponse
from ocos.interaction.cli.paths import resolve_db_path

router = APIRouter()



def _guard_or_403(action: str) -> None:
    """S1.3 (白皮书 P1-2b): API 写面端点统一过 PermissionGuard。

    与 S1.2 Bearer Token 认证叠加为两层；拒绝 → 403。
    """
    from ocos.interaction.base import PermissionGuard
    result = PermissionGuard().check(action)
    if not getattr(result, "allowed", False):
        violations = getattr(result, "violations", None) or [action]
        raise HTTPException(
            status_code=403,
            detail=f"permission guard denied: {'; '.join(str(v) for v in violations)[:200]}")


def _db() -> str:
    return resolve_db_path()


# ── 对话（R1: ChatResponder 直答） ──────────────────────────────────

@router.post("/ocos/converse", tags=["converse"])
async def converse(body: dict[str, Any]) -> APIResponse:
    """POST /ocos/converse — 与数字生命对话（同步回复）。

    请求: {"message": "..."}
    响应: {reply, provider, mock}
    """
    _guard_or_403("create_goal")
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    # FIX-8: 客户端会话 id 贯穿到对话记忆（无状态 ChatResponder 的会话归属）
    session_id = str(body.get("session_id", "") or "").strip()[:64] or "web"

    from ocos.interaction.converse import (ChatResponder,
                                           make_default_tool_executor)
    # FIX-T3: 注入只读动作执行器 — 对话层可通过 USE| 行取实时数据
    responder = ChatResponder(db_path=_db(),
                              tool_executor=make_default_tool_executor(_db()))
    out = await asyncio.to_thread(
        responder.respond_auto, message, session_id=session_id)
    return APIResponse(
        success=True,
        message="ok",
        data={"reply": out["reply"], "provider": out["provider"],
              "mock": out["mock"], "goal_id": out.get("goal_id"),
              "kind": out.get("kind")},
    )


# ── 对话（R1b: 流式 SSE — token 打字机） ─────────────────────────────

@router.post("/ocos/converse/stream", tags=["converse"])
async def converse_stream(body: dict[str, Any]) -> StreamingResponse:
    """POST /ocos/converse/stream — 与数字生命对话（流式 SSE）。

    请求: {"message": "...", "session_id": "..."}
    返回 text/event-stream：
      data: <delta text>                 # 逐段增量
      event: done / data: {…meta json}   # 结束，携带 provider/reply/goal_id/kind
      event: error / data: <message>     # 失败
    """
    _guard_or_403("create_goal")
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    session_id = str(body.get("session_id", "") or "").strip()[:64] or "web"

    from ocos.interaction.converse import (ChatResponder,
                                           make_default_tool_executor)
    responder = ChatResponder(db_path=_db(),
                              tool_executor=make_default_tool_executor(_db()))
    q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
    main_loop = asyncio.get_running_loop()

    def emit(text: str) -> None:
        main_loop.call_soon_threadsafe(q.put_nowait, ("text", text))

    def _worker() -> None:
        """在工作线程独立事件循环里跑 respond_stream，增量经 emit 回投主循环。"""
        try:
            out = responder.respond_auto(message, session_id=session_id,
                                         _emit=emit)
            main_loop.call_soon_threadsafe(
                q.put_nowait, ("done", json.dumps({
                    "reply": out["reply"], "provider": out.get("provider", ""),
                    "mock": out.get("mock", False),
                    "goal_id": out.get("goal_id"),
                    "kind": out.get("kind"),
                })))
        except asyncio.CancelledError:
            main_loop.call_soon_threadsafe(q.put_nowait, ("error", "cancelled"))
        except Exception as e:  # noqa: BLE001
            main_loop.call_soon_threadsafe(
                q.put_nowait, ("error", f"{type(e).__name__}: {e}"))

    worker = asyncio.create_task(asyncio.to_thread(_worker))

    async def _gen():
        try:
            while True:
                kind, payload = await q.get()
                if kind == "text":
                    # SSE 帧内不能含裸换行：按行拆成多条 data: 帧
                    for line in payload.split("\n"):
                        if line:
                            yield f"data: {line}\n\n"
                elif kind == "done":
                    yield f"event: done\ndata: {payload}\n\n"
                    break
                else:  # error
                    yield f"event: error\ndata: {payload}\n\n"
                    break
        finally:
            worker.cancel()

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── 目标执行结果回推（CHAT-ROUTE FIX 2026-09-07） ────────────────────

def _daemon_activity() -> dict[str, Any]:
    """daemon 心跳存活快照（feed/summary 共用）。

    OCOS_HEARTBEAT_PATH 环境变量优先（测试隔离），默认
    ~/.ocos/daemon_heartbeat.json；读不到 → alive=False（诚实报告）。
    """
    import os as _os
    from pathlib import Path as _Path
    env = _os.environ.get("OCOS_HEARTBEAT_PATH", "")
    hb_file = _Path(env) if env else _Path.home() / ".ocos" / "daemon_heartbeat.json"
    try:
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        age = time.time() - datetime.fromisoformat(hb["ts"]).timestamp()
        return {"alive": age < 30, "age_s": round(age, 1),
                "cycle": hb.get("cycle", 0)}
    except (OSError, ValueError, KeyError):
        return {"alive": False, "age_s": None, "cycle": 0}


def _goal_activity(conn: Any) -> dict[str, Any]:
    """在执行/排队目标快照 — 前端活动徽章数据源（执行可见性）。"""
    from datetime import datetime as _dt, timezone as _tz
    out: dict[str, Any] = {"active_goal": None, "pending_goals": 0}
    try:
        row = conn.execute(
            "SELECT id, description, origin_level, updated_at FROM goals "
            "WHERE status='ACTIVE' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            elapsed: Any = None
            try:
                t0 = _dt.fromisoformat(str(row[3]))
                if t0.tzinfo is None:
                    t0 = t0.replace(tzinfo=_tz.utc)
                elapsed = round(max(0.0, (_dt.now(_tz.utc) - t0)
                                    .total_seconds()), 1)
            except ValueError:
                pass
            out["active_goal"] = {"id": str(row[0]),
                                  "description": str(row[1] or "")[:120],
                                  "origin": str(row[2] or ""),
                                  "elapsed_s": elapsed}
        out["pending_goals"] = int(conn.execute(
            "SELECT COUNT(*) FROM goals WHERE status='PENDING'"
        ).fetchone()[0])
    except Exception:   # goals 表缺失/损坏 — 诚实降级为空快照
        pass
    return out


@router.get("/ocos/converse/feed", tags=["converse"])
async def converse_feed(since: str = "") -> APIResponse:
    """GET /ocos/converse/feed?since=<ISO> — 目标执行结果增量流。

    Web UI 对话流轮询此端点：返回 created_at > since 的 goal_result
    episodes（升序，最多 5 条）。个人单用户模式不按 session 过滤 —
    所有目标执行结果都推给主人对话流，兑现"结果自动出现在本对话"。
    空结果返回 items=[]（前端据此跳过渲染）。

    2026-09-08 执行可见性: 响应附 activity 快照（daemon 心跳存活、
    在执行目标及耗时、排队目标数）— 前端据此渲染常驻状态徽章，
    区分"空闲待命 / 执行中 / 后台离线"三态（用户此前无从分辨）。
    """
    import sqlite3 as _sq
    from datetime import datetime as _dt, timezone as _tz

    since_dt: Any = None
    if since:
        try:
            since_dt = _dt.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=_tz.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad since timestamp")

    conn = _sq.connect(f"file:{_db()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT id, created_at, decision, outcome "
            "FROM episodes WHERE action='goal_result' "
            "ORDER BY created_at DESC LIMIT 25").fetchall()
        activity = _goal_activity(conn)
    finally:
        conn.close()
    activity["daemon"] = _daemon_activity()

    items: list[dict[str, Any]] = []
    for rid, created, decision, outcome in rows:
        try:
            row_dt = _dt.fromisoformat(str(created))
            if row_dt.tzinfo is None:
                row_dt = row_dt.replace(tzinfo=_tz.utc)
        except ValueError:
            continue
        if since_dt is not None and row_dt <= since_dt:
            continue
        success = True
        try:
            success = bool(json.loads(outcome or "{}").get("success", True))
        except Exception:
            pass
        items.append({"id": rid, "created_at": str(created),
                      "decision": str(decision or "")[:1600],
                      "success": success})
        if len(items) >= 5:
            break
    items.reverse()   # 升序：前端按序追加
    return APIResponse(success=True, message="ok",
                       data={"items": items, "server_time":
                             _dt.now(_tz.utc).isoformat(),
                             "activity": activity})


# ── 状态总览（侧栏数据源） ──────────────────────────────────────────

@router.get("/ocos/summary", tags=["converse"])
async def summary() -> APIResponse:
    """GET /ocos/summary — goals/approvals/inbox/memory 计数。"""
    import sqlite3

    data: dict[str, Any] = {"db": _db()}
    conn = sqlite3.connect(_db())
    try:
        counts: dict[str, int] = {}
        try:
            for status, n in conn.execute(
                    "SELECT status, COUNT(*) FROM goals GROUP BY status"):
                counts[status] = n
        except sqlite3.OperationalError:
            pass
        data["goals"] = counts

        try:
            data["approvals_pending"] = conn.execute(
                "SELECT COUNT(*) FROM pending_actions WHERE status='pending'"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            data["approvals_pending"] = 0

        try:
            data["inbox_queued"] = conn.execute(
                "SELECT COUNT(*) FROM user_messages WHERE status='queued'"
            ).fetchone()[0]
        except sqlite3.OperationalError:
            data["inbox_queued"] = 0

        memory: dict[str, int] = {}
        for table, key in (("episodes", "episodes"), ("belief", "beliefs"),
                           ("pattern", "patterns")):
            try:
                memory[key] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                break
        data["memory"] = memory
    finally:
        conn.close()

    # UX-F3: daemon 心跳存活
    from pathlib import Path
    hb_file = Path.home() / ".ocos" / "daemon_heartbeat.json"
    daemon = {"alive": False}
    try:
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        age = time.time() - datetime.fromisoformat(hb["ts"]).timestamp()
        daemon = {"alive": age < 30, "age_s": round(age, 1),
                  "cycle": hb.get("cycle", 0), "pid": hb.get("pid")}
    except (OSError, ValueError, KeyError):
        pass
    data["daemon"] = daemon

    return APIResponse(success=True, message="ok", data=data)


# ── UX-J: 出站消息（目标结果自动回推） ──────────────────────────────

@router.get("/ocos/outbox", tags=["converse"])
async def outbox(after: int = 0) -> APIResponse:
    """GET /ocos/outbox?after=<rowid> — 增量拉取 agent 主动消息。

    after=-1 → 仅返回当前游标（max rowid），不取历史：UI 首刷据此
    跳过存量回放（与 converse/feed "首刷只校准不回放"语义对齐；
    此前 cursor=0 从最老 20 条开始爬，永远追不上新消息）。
    """
    from ocos.interaction.inbox import UserInbox
    inbox = UserInbox(db_path=_db())
    if after == -1:
        return APIResponse(success=True, message="ok",
                           data={"messages": [],
                                 "next_cursor": inbox.max_rowid()})
    rows = inbox.list_outbound_after(after)
    next_cursor = max((r["rid"] for r in rows), default=after)
    return APIResponse(success=True, message="ok",
                       data={"messages": rows, "next_cursor": next_cursor})


# ── E: 内视 ─────────────────────────────────────────────────────────

@router.get("/ocos/introspect", tags=["converse"])
async def introspect() -> APIResponse:
    """GET /ocos/introspect — agent 对自身内部状态的深度检视报告。"""
    from ocos.interaction.converse import ChatResponder
    out = ChatResponder(db_path=_db()).build_introspection()
    return APIResponse(success=True, message="ok", data=out)


# ── D: 自我迭代（自省 → 提案入待批） ────────────────────────────────

@router.post("/ocos/self-improve", tags=["converse"])
async def self_improve() -> APIResponse:
    """POST /ocos/self-improve — 分析近期对话，产出自我升级提案。

    提案入待批队列（action_type=self_upgrade），人工批准后应用到
    ~/.ocos/self_knowledge.md 并回注对话提示词。
    """
    _guard_or_403("self_improve")
    from ocos.interaction.converse import ChatResponder
    out = await asyncio.to_thread(ChatResponder(db_path=_db()).self_improve)
    return APIResponse(success=True, message="ok", data=out)


# ── C: 对话转目标（聊天 → daemon 认领执行） ─────────────────────────

@router.post("/ocos/goals-from-chat", tags=["converse"])
async def goals_from_chat(body: dict[str, Any]) -> APIResponse:
    """POST /ocos/goals-from-chat — 把一句话转为 PENDING 人类目标。

    daemon 认领后按 metadata.domain 分解执行；写文件/跑命令类子任务
    经 DecisionBridge 进待批队列。
    """
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    # UX-F4: 意图过滤 — 状态询问类消息不该变成目标（会永远空转）。
    # 放宽: 不要求句尾问号（"分析结果呢"这类陈述式追问同样拦截）
    QUESTION_MARKERS = ("结果", "怎么样了", "进度", "状态如何", "为什么",
                        "怎么没有", "了吗", "如何了", "是多少")
    if len(message) <= 20 and any(m in message for m in QUESTION_MARKERS)             and not any(k in message for k in ("跑", "执行", "生成", "写入", "创建文件")):
        raise HTTPException(
            status_code=422,
            detail="这更像状态询问而非任务 — 请直接在对话框问 OCOS，"
                   "它会从记忆里回答；确要执行请改写为具体任务描述")

    domain = str(body.get("domain", "development"))
    from ocos.goal.store import GoalStore
    store = GoalStore(db_path=_db())
    goal_id = f"GOAL-{uuid.uuid4().hex[:12]}"
    store.save(
        goal_id=goal_id, level="USER", status="PENDING",
        description=message[:200], priority=3.0, source="chat",
        origin_level="HUMAN", authority="FRAMEWORK",
        metadata={"domain": domain},
    )
    return APIResponse(success=True, message="goal created",
                       data={"goal_id": goal_id, "domain": domain})


# ── 待批动作（与 CLI approvals 同源） ────────────────────────────────

@router.get("/ocos/approvals", tags=["converse"])
async def list_approvals() -> APIResponse:
    from ocos.execution.pending import PendingStore, approval_disabled
    rows = PendingStore(db_path=_db()).list_by_status("pending")
    # P2-UX (2026-09-08): 前端需感知审批模式 — auto 模式下待批项秒级被
    # daemon 自动通过，用户点击时 404 属预期，面板应明示而非误导
    return APIResponse(success=True, message="ok",
                       data={"pending": rows,
                             "mode": "auto" if approval_disabled() else "ask"})


@router.post("/ocos/approvals/{pid}/approve", tags=["converse"])
async def approve(pid: str) -> APIResponse:
    return _decide(pid, approved=True)


@router.post("/ocos/approvals/{pid}/deny", tags=["converse"])
async def deny(pid: str) -> APIResponse:
    return _decide(pid, approved=False)


def _decide(pid: str, approved: bool) -> APIResponse:
    _guard_or_403("approve_action")
    from ocos.execution.pending import PendingStore
    from ocos.execution.bridge import DecisionBridge

    store = PendingStore(db_path=_db())
    row = store.get(pid)
    if row is None or row["status"] != "pending":
        raise HTTPException(status_code=404, detail="not found or already decided")
    store.decide(pid, approved=approved, decided_by="web")

    if not approved:
        return APIResponse(success=True, message="denied",
                           data={"id": pid, "status": "denied"})

    # 诚实执行：有 handler → dispatch；无 → blocked 可见
    import json
    payload = json.loads(row.get("payload_json") or "{}")
    bridge = DecisionBridge(pending_store=store, db_path=_db())
    bridge.attach_default_handlers()
    dispatched = bridge.execute_approved(row["action_type"], payload)
    if dispatched is not None and dispatched.status == "done":
        store.mark_executed(pid, result_summary=str(dispatched.result)[:500])
        return APIResponse(success=True, message="executed",
                           data={"id": pid, "status": "executed",
                                 "result": str(dispatched.result)[:300]})
    reason = (str(dispatched.result)[:200] if dispatched is not None
              else "no executor for this action type")
    store.mark_executed(pid, result_summary=reason, executed=False)
    return APIResponse(success=True, message="blocked",
                       data={"id": pid, "status": "blocked", "reason": reason})
