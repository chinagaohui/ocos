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
        # UX-P2: /goal 接 goal 域持久化（与 CLI goal status/list 同源，消除 TBD 漂移）
        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=self._ctx.db_path)
        if goal_id:
            row = store.load(goal_id)
            if row is None:
                print(f"Goal not found: {goal_id}")
            else:
                print(f"Goal: {row['id']}")
                print(f"  Status:   {row['status']}")
                print(f"  Progress: {row['progress']}")
                print(f"  Description: {row['description']}")
        else:
            rows = store.load_active()
            if rows:
                print(f"Active goals ({len(rows)}):")
                for r in rows:
                    print(f"  {r['id'][:16]}  [{r['status']:>8}]  {str(r['description'])[:44]}")
            else:
                print("No active goals. 直接输入一句话即可创建目标。")
        self._session.record_query()
