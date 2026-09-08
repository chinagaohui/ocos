"""OCOS CLI — approvals 命令（AUD-F12: R4-B 待批队列的人工审批入口）。

审批即 authority（人工决策），不二次过 PermissionGuard 语义双检，
但决定与执行全部落 ExecutionAudit 审计。
"""

from __future__ import annotations

import json


def _store_and_bridge():
    """构造 PendingStore + DecisionBridge（只读审批视角，无需挂载 runtime）。"""
    from ocos.execution.bridge import DecisionBridge
    from ocos.execution.pending import PendingStore
    from ocos.interaction.cli.paths import resolve_db_path

    db_path = resolve_db_path()
    store = PendingStore(db_path=db_path)

    def _autonomous_goal_sink(payload: dict) -> None:
        """L3: 自主目标批准落地 — 写 goals 表 PENDING（daemon 自动认领）。"""
        from ocos.goal.store import GoalStore
        GoalStore(db_path=db_path).save(
            goal_id=payload.get("goal_id", ""),
            level="TASK", status="PENDING",
            description=payload.get("description", ""),
            source="autonomous",
            metadata={"autonomous": True, "kind": payload.get("kind", ""),
                      "score": payload.get("score", 0),
                      "evidence": payload.get("evidence", ""),
                      "approved": True},
            origin_level="SELF", authority="AUTONOMOUS")

    def _constitution_sink(payload: dict) -> dict:
        """L4-1: 宪法修改批准落地 — save_version 落新版本（只增不改）。"""
        from ocos.constitution.versioned import VersionedConstitution
        snap = VersionedConstitution(db_path=db_path).save_version(
            principles=payload.get("principles", []),
            reason=payload.get("reason", ""),
            approved_by="human")
        return {"version": snap.version}

    bridge = DecisionBridge(pending_store=store, db_path=db_path,
                            autonomous_goal_sink=_autonomous_goal_sink,
                            constitution_sink=_constitution_sink)
    bridge.attach_default_handlers()
    return store, bridge, db_path


def cmd_approvals_list(args, session) -> int:
    """ocos approvals list [--all]"""
    store, _bridge, _db_path = _store_and_bridge()
    status = None if args.all else "pending"
    if status:
        rows = store.list_by_status(status)
        label = "pending"
    else:
        rows = (store.list_by_status("pending") + store.list_by_status("approved")
                + store.list_by_status("denied") + store.list_by_status("executed")
                + store.list_by_status("blocked"))
        label = "all"
    print(f"Pending actions ({label}): {len(rows)}")
    for r in rows:
        print(f"  [{r['status']:>8}] {r['id']}  {r['action_type']}  "
              f"queued={r['queued_at'][:19]}")
        if r.get("text"):
            print(f"             text: {str(r['text'])[:80]}")
    return 0


def cmd_approvals_approve(args, session) -> int:
    """ocos approvals approve <id> — 人工批准并尝试真实执行"""
    store, bridge, _db_path = _store_and_bridge()
    row = store.get(args.pending_id)
    if row is None or row["status"] != "pending":
        print(f"Pending action not found or not pending: {args.pending_id}")
        return 1

    if not store.decide(args.pending_id, approved=True, decided_by="cli"):
        print(f"Decide failed: {args.pending_id}")
        return 1
    print(f"Approved: {args.pending_id} ({row['action_type']})")

    # 尝试真实执行 — 有 handler 的动作 dispatch；无 executor 的诚实 blocked
    action_type = row["action_type"]
    payload = json.loads(row["payload_json"] or "{}")
    # S1.1 (白皮书 P1-1): 注入本待批行 id 作为 approval_id，
    # 供 handler 侧溯源校验（必须对应 status='approved' 的行）
    payload.setdefault("approval_id", args.pending_id)
    dispatched = bridge.execute_approved(action_type, payload)
    if dispatched is not None and dispatched.status == "done":
        store.mark_executed(args.pending_id,
                            result_summary=str(dispatched.result)[:500], executed=True)
        print(f"  executed: {str(dispatched.result)[:120]}")
        return 0

    reason = (str(dispatched.result)[:200]
              if dispatched is not None else "no executor for this action type")
    store.mark_executed(args.pending_id, result_summary=reason, executed=False)
    print(f"  blocked: {reason}")
    print("  (approved 但无执行器 — 需注册对应 handler 后重新执行)")
    return 0


def cmd_approvals_deny(args, session) -> int:
    """ocos approvals deny <id>"""
    store, _bridge, _db_path = _store_and_bridge()
    if not store.decide(args.pending_id, approved=False, decided_by="cli"):
        print(f"Pending action not found or not pending: {args.pending_id}")
        return 1
    print(f"Denied: {args.pending_id}")
    return 0
