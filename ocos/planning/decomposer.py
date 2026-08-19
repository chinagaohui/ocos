"""Phase 27 — TaskDecomposer: Goal → TaskDAG。

纯规则分解，不依赖 LLM。分解策略:
  - writing goal → 大纲→人物→章节→修改链
  - analysis goal → 数据→分析→报告链
  - research goal → 文献→实验→结论链
  - development goal → 设计→实现→测试链

宪法约束:
  - MAX_DAG_DEPTH = 5
  - MAX_PARALLEL_WIDTH = 4
"""

from __future__ import annotations

from ocos.goal.models import GoalDomain, UserGoal
from ocos.planning.models import (
    MAX_DAG_DEPTH,
    MAX_PARALLEL_WIDTH,
    Task,
    TaskDAG,
)


class TaskDecomposer:
    """将 Goal 分解为 TaskDAG。"""

    # ── domain → template ──
    WRITING_TEMPLATE = [
        ("outline",  "写大纲",     "create", "writer", 120),
        ("characters", "人物设定",  "create", "writer", 90),
        ("chapter_1",  "写第1章",  "execute", "writer", 600),
        ("chapter_2",  "写第2章",  "execute", "writer", 600),
        ("revise",     "修改润色",  "modify", "reviewer", 300),
    ]

    ANALYSIS_TEMPLATE = [
        ("collect",   "收集数据",  "execute", "researcher", 120),
        ("analyze",   "分析数据",  "analyze", "researcher", 180),
        ("report",    "生成报告",  "create",  "writer", 120),
    ]

    RESEARCH_TEMPLATE = [
        ("literature", "文献调研", "execute", "researcher", 300),
        ("experiment", "实验/验证", "execute", "researcher", 600),
        ("conclusion", "结论撰写", "create",  "writer", 180),
    ]

    DEVELOPMENT_TEMPLATE = [
        ("design",    "设计架构",  "create",  "researcher", 180),
        ("implement", "实现代码",  "execute", "writer",  600),
        ("test",       "测试验证",  "verify",  "reviewer", 300),
    ]

    _TEMPLATES: dict[GoalDomain, list[tuple]] = {}

    @classmethod
    def _init_templates(cls) -> dict[GoalDomain, list[tuple]]:
        if not cls._TEMPLATES:
            cls._TEMPLATES = {
                GoalDomain.WRITING: cls.WRITING_TEMPLATE,
                GoalDomain.ANALYSIS: cls.ANALYSIS_TEMPLATE,
                GoalDomain.RESEARCH: cls.RESEARCH_TEMPLATE,
                GoalDomain.DEVELOPMENT: cls.DEVELOPMENT_TEMPLATE,
            }
        return cls._TEMPLATES

    @classmethod
    def decompose(cls, goal: UserGoal) -> TaskDAG:
        """将 UserGoal 分解为 TaskDAG。"""
        dag = TaskDAG()
        templates = cls._init_templates()
        template = templates.get(goal.domain, cls.DEVELOPMENT_TEMPLATE)

        prev_id: str | None = None
        task_ids: list[str] = []

        for suffix, desc, ttype, agent, duration in template:
            # 写入约束到描述
            full_desc = desc
            if goal.constraints:
                constraint_str = ", ".join(goal.constraints[:2])  # 最多2个
                full_desc = f"{desc} [{constraint_str}]"

            task = Task.create(
                goal_id=goal.id,
                description=full_desc,
                task_type=ttype,
                agent_type=agent,
                estimated_duration=duration,
                inputs=(prev_id,) if prev_id else (),
            )
            dag.add_task(task)
            task_ids.append(task.id)

            # 串行连接
            if prev_id:
                dag.add_edge(prev_id, task.id)
            prev_id = task.id

        # 验证拓扑预算
        cls._enforce_budgets(dag)

        return dag

    @classmethod
    def _enforce_budgets(cls, dag: TaskDAG) -> None:
        """强制拓扑预算: 深度 ≤ MAX_DAG_DEPTH, 宽度 ≤ MAX_PARALLEL_WIDTH。"""
        groups = dag.parallel_groups()
        if len(groups) > MAX_DAG_DEPTH:
            raise ValueError(
                f"DAG depth {len(groups)} exceeds MAX_DAG_DEPTH {MAX_DAG_DEPTH}"
            )
        for i, group in enumerate(groups):
            if len(group) > MAX_PARALLEL_WIDTH:
                raise ValueError(
                    f"DAG level {i} width {len(group)} exceeds MAX_PARALLEL_WIDTH {MAX_PARALLEL_WIDTH}"
                )
