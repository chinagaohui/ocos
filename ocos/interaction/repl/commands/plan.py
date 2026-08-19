"""OCOS REPL — plan 命令。"""

from __future__ import annotations

from ocos.goal.models import GoalDomain
from ocos.interaction.base import GoalRequest, PermissionGuard, InteractionSession


class ReplPlanCommand:
    """REPL /plan 命令 — 创建 Goal 并触发规划。"""

    def __init__(self, session: InteractionSession):
        self.session = session
        self.guard = PermissionGuard()

    def execute(self, arg: str) -> None:
        result = self.guard.check("create_goal")
        if not result.allowed:
            print(f"  Permission denied: {', '.join(result.violations)}")
            return

        description = arg.strip()
        if not description:
            print("  Usage: /plan <description>")
            return

        domain = _detect_domain(description)
        try:
            req = GoalRequest.create(
                raw_input=description,
                objective=description,
                domain=domain,
                caller="repl",
            )
            goal = req.to_user_goal()
            self.session.record_goal(goal.id)
        except ValueError as e:
            print(f"  Plan failed: {e}")
            return

        print(f"\n  Goal created: {goal.id}")
        print(f"    Status:   {goal.status.value}")
        print(f"    Domain:   {goal.domain.value}")
        print(f"    Priority: {goal.priority}")
        print()

        # Phase 29-F: TaskDecomposer 实时分解
        try:
            from ocos.planning.decomposer import TaskDecomposer
            from ocos.planning.strategy import StrategyEngine
            dag = TaskDecomposer.decompose(goal)
            strategy = StrategyEngine.select(dag)
            tasks = dag.topological_order()
            print(f"  Plan: {len(tasks)} tasks, strategy={strategy.value}")
            print(f"  " + "─" * 50)
            for i, tid in enumerate(tasks, 1):
                task = dag.tasks[tid]
                print(f"  {i}. [{task.task_type}] {task.description} "
                      f"(agent={task.agent_type}, ~{task.estimated_duration}s)")
            print(f"  " + "─" * 50)
        except Exception as e:
            print(f"  Planning:")
            print(f"    ─ Decomposer error: {e}")
            print(f"    ─ Goal {goal.id} is ready for planning.")


def _detect_domain(text: str) -> GoalDomain:
    """基于关键词自动检测目标领域。"""
    t = text.lower()
    # 写作关键词优先（"写"+"系统" → writing，非 development）
    if any(w in t for w in ("写", "文章", "博客", "小说", "故事", "诗歌", "散文", "剧本")):
        return GoalDomain.WRITING
    if any(w in t for w in ("设计", "开发", "架构", "实现", "代码", "api", "接口", "搭建", "部署")):
        return GoalDomain.DEVELOPMENT
    if any(w in t for w in ("分析", "数据", "报告", "调研", "统计", "指标", "趋势")):
        return GoalDomain.ANALYSIS
    if any(w in t for w in ("研究", "论文", "实验", "文献", "结论")):
        return GoalDomain.RESEARCH
    return GoalDomain.WRITING
