"""OCOS CLI — plan 命令实现。"""

from __future__ import annotations

from ocos.goal.models import GoalDomain
from ocos.interaction.base import GoalRequest, InteractionSession, PermissionGuard


def cmd_plan(args, session: InteractionSession) -> int:
    """ocos plan "description" [--domain writing]

    Plan 是 Goal 的超集：先创建 Goal，再请求规划。
    """
    guard = PermissionGuard()
    result = guard.check("request_plan")
    if not result.allowed:
        print(f"Permission denied: {', '.join(result.violations)}")
        return 1

    domain = _detect_domain(args.description)
    try:
        req = GoalRequest.create(
            raw_input=args.description,
            objective=args.description,
            domain=domain,
            caller="cli",
        )
        goal = req.to_user_goal()
    except ValueError as e:
        print(f"Plan failed: {e}")
        return 1

    session.record_goal(goal.id)

    print(f"Goal created: {goal.id}")
    print(f"  Status:  {goal.status.value}")
    print(f"  Domain:  {goal.domain.value}")
    print()

    # Phase 29-F: TaskDecomposer real-time decomposition
    try:
        from ocos.planning.decomposer import TaskDecomposer
        from ocos.planning.strategy import StrategyEngine
        dag = TaskDecomposer.decompose(goal)
        strategy = StrategyEngine.select(dag)
        tasks = dag.topological_order()
        print(f"Plan: {len(tasks)} tasks, strategy={strategy.value}")
        print("-" * 50)
        for i, tid in enumerate(tasks, 1):
            task = dag.tasks[tid]
            print(f"  {i}. [{task.task_type}] {task.description} "
                  f"(agent={task.agent_type}, ~{task.estimated_duration}s)")
        print("-" * 50)

        # AUD-F8: DAG 落库（plan_dag 表, goal_id 关联）
        import json as _json
        from dataclasses import asdict
        from ocos.goal.store import GoalStore
        from ocos.interaction.cli.paths import resolve_db_path
        dag_snapshot = {
            tid: {
                "description": dag.tasks[tid].description,
                "task_type": dag.tasks[tid].task_type,
                "agent_type": dag.tasks[tid].agent_type,
                "inputs": list(dag.tasks[tid].inputs or ()),
                "estimated_duration": dag.tasks[tid].estimated_duration,
            }
            for tid in tasks
        }
        store = GoalStore(db_path=resolve_db_path())
        store.save_plan_dag(
            goal_id=goal.id,
            dag_json=_json.dumps(dag_snapshot, ensure_ascii=False),
            strategy=strategy.value,
            task_count=len(tasks),
        )
        print(f"Plan persisted: goal_id={goal.id}")
    except Exception as e:
        print(f"Planning:")
        print(f"  - Decomposer error: {e}")
        print(f"  - Goal {goal.id} is ready for planning.")
        print(f"  Next step: ocos goal status {goal.id}")

    return 0


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
