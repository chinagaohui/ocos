"""OCOS REPL — goal 命令。"""

from __future__ import annotations

from ocos.interaction.base import PermissionGuard, InteractionSession
from ocos.interaction.context import InteractionContext


class ReplGoalCommand:
    """REPL /goal 命令 — 查看目标状态。"""

    def __init__(self, session: InteractionSession, ctx: InteractionContext):
        self._session = session
        self._ctx = ctx
        self._guard = PermissionGuard()

    def execute(self, arg: str):
        # /goal 使用 create_goal 权限检查（只读查询不需新权限）
        result = self._guard.check("create_goal")
        if not result.allowed:
            print(f"Permission denied: {', '.join(result.violations)}")
            return

        goal_id = arg.strip()
        if goal_id:
            print(f"Goal: {goal_id}")
            print(f"  Note: Individual goal lookup TBD.")
        else:
            from ocos.storage.connection import get_connection
            import sqlite3
            try:
                conn = get_connection(self._ctx.db_path)
                rows = conn.execute(
                    "SELECT id, status, level, progress FROM goals ORDER BY rowid DESC LIMIT 10"
                ).fetchall()
                if rows:
                    print(f"Goals ({len(rows)} recent):")
                    for r in rows:
                        print(f"  {r[0][:16]}  [{r[1]:12s}]  level={r[2]:12s}  progress={r[3]:.0%}")
                else:
                    print("No goals yet. Type a goal directly to create one.")
            except Exception:
                print("No goals yet. Type a goal directly to create one.")
        self._session.record_query()
