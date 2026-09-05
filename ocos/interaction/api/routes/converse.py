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
    """GET /ocos/outbox?after=<rowid> — 增量拉取 agent 主动消息。"""
    from ocos.interaction.inbox import UserInbox
    rows = UserInbox(db_path=_db()).list_outbound_after(after)
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
    from ocos.execution.pending import PendingStore
    rows = PendingStore(db_path=_db()).list_by_status("pending")
    return APIResponse(success=True, message="ok",
                       data={"pending": rows})


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
