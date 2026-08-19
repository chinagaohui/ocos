"""OCOS REPL — trace 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession


class ReplTraceCommand:
    """REPL /trace 命令 — 查看决策追踪。"""

    def __init__(self, session: InteractionSession):
        self.session = session
        self.guard = PermissionGuard()

    def execute(self, arg: str) -> None:
        result = self.guard.check("view_trace")
        if not result.allowed:
            print(f"  Permission denied: {', '.join(result.violations)}")
            return

        trace_id = arg.strip()
        self.session.record_query()

        print(f"\n  Decision Trace: {trace_id if trace_id else '(latest)'}")
        print(f"  ─────────────────────────────────────")
        print(f"  Note: DecisionTrace store integration TBD.")
        print(f"  When wired, will show:")
        print(f"    • reasoning chain from goal to decision")
        print(f"    • evidence references and belief anchors")
        print(f"    • constitution validation results")
