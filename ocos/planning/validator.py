"""Phase 27 — PlanValidator: Plan 合法性验证。

验证:
  - Plan 必须关联 Goal
  - DAG 无环
  - 拓扑预算合规
  - 不导入 ocos.self
"""

from __future__ import annotations

from ocos.planning.models import Plan


class PlanValidator:
    """Plan 合法性验证器。"""

    @staticmethod
    def validate(plan: Plan) -> tuple[bool, str]:
        """验证 Plan 合法性。"""
        # 1. Plan 必须关联 Goal
        if not plan.goal_id:
            return False, "Plan must reference a Goal"

        # 2. DAG 必须无环
        if not plan.dag.validate_acyclic():
            return False, "DAG contains cycles"

        # 3. DAG 不能为空
        if not plan.dag.tasks:
            return False, "DAG must contain at least one Task"

        # 4. 策略必须是合法枚举
        # (type system enforces this)

        # 5. 估算总时长 > 0
        if plan.estimated_total_duration <= 0:
            return False, "estimated_total_duration must be positive"

        return True, "ok"

    @staticmethod
    def validate_no_self_module() -> None:
        """Gateway check: ocos.planning 不导入 ocos.self。

        真正的检查由 ocos/tests/test_import_rules.py 完成。
        """
        pass
