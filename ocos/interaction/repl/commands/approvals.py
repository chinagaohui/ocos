"""OCOS REPL — approvals 命令（UX-P2: REPL 内处理 R4-B 待批动作）。"""

from __future__ import annotations

from ocos.interaction.base import InteractionSession


class ReplApprovalsCommand:
    """/approvals [list] | /approvals approve <id> | /approvals deny <id>"""

    def __init__(self, session: InteractionSession, ctx):
        self._session = session
        self._ctx = ctx

    def execute(self, arg: str):
        from ocos.execution.pending import PendingStore

        parts = arg.strip().split()
        store = PendingStore(db_path=self._ctx.db_path)
        sub = parts[0] if parts else "list"

        if sub == "list":
            rows = store.list_by_status("pending")
            print(f"Pending actions: {len(rows)}")
            for r in rows:
                print(f"  {r['id']}  {r['action_type']}  {str(r['text'])[:44]}")
            if not rows:
                print("  (none)")
        elif sub in ("approve", "deny"):
            if len(parts) < 2:
                print(f"Usage: /approvals {sub} <PEND-xxxxxxxx>")
                return
            pid = parts[1]
            if not store.decide(pid, approved=(sub == "approve"), decided_by="repl"):
                print(f"Not found or already decided: {pid}")
                return
            print(f"{'Approved' if sub == 'approve' else 'Denied'}: {pid}")
            if sub == "approve":
                row = store.get(pid)
                payload = __import__("json").loads(row["payload_json"] or "{}")
                from ocos.execution.bridge import DecisionBridge
                bridge = DecisionBridge(pending_store=store, db_path=self._ctx.db_path)
                bridge.attach_default_handlers()
                dispatched = bridge.execute_approved(
                    row["action_type"], payload)
                if dispatched is not None and dispatched.status == "done":
                    store.mark_executed(pid, result_summary=str(dispatched.result)[:500])
                    print(f"  executed: {str(dispatched.result)[:120]}")
                else:
                    reason = (str(dispatched.result)[:160]
                              if dispatched is not None
                              else "no executor for this action type")
                    store.mark_executed(pid, result_summary=reason, executed=False)
                    print(f"  blocked: {reason}（批准 ≠ 有执行器）")
        else:
            print("Usage: /approvals [list] | approve <id> | deny <id>")
        self._session.record_query()
