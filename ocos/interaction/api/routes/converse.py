"""UX-P2 Web: 对话/状态/审批路由 — Web UI 与外部前端的数据面。

与 CLI/REPL 共用同一命令核心（ChatResponder/PendingStore/GoalStore），
消除三入口实现漂移。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse
from ocos.interaction.cli.paths import resolve_db_path

router = APIRouter()


def _db() -> str:
    return resolve_db_path()


# ── 对话（R1: ChatResponder 直答） ──────────────────────────────────

@router.post("/ocos/converse", tags=["converse"])
async def converse(body: dict[str, Any]) -> APIResponse:
    """POST /ocos/converse — 与数字生命对话（同步回复）。

    请求: {"message": "..."}
    响应: {reply, provider, mock}
    """
    message = str(body.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    from ocos.interaction.converse import ChatResponder
    responder = ChatResponder(db_path=_db())
    out = await responder.respond_async(message)
    return APIResponse(
        success=True,
        message="ok",
        data={"reply": out["reply"], "provider": out["provider"],
              "mock": out["mock"]},
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
    return APIResponse(success=True, message="ok", data=data)


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
    bridge = DecisionBridge(pending_store=store)
    bridge.attach_default_handlers()
    dispatched = bridge.dispatcher.dispatch_by_name(row["action_type"], payload)
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
