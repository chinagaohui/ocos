"""Phase 26 — GoalValidator: 来源检查 + 合法性验证。

宪法约束:
  - Goal 唯一合法来源: human, decomposed
  - 拒绝 self-generated goal
  - 拒绝循环 parent 引用
  - 拒绝非 human 来源的 root goal
"""

from __future__ import annotations

from ocos.goal.models import GoalSource, UserGoal


class GoalValidator:
    """Goal 合法性验证器。"""

    @staticmethod
    def validate_source(goal: UserGoal) -> tuple[bool, str]:
        """验证 Goal 来源合法。

        Returns:
            (is_valid, reason)
        """
        if goal.source == GoalSource.HUMAN:
            return True, "ok"
        if goal.source == GoalSource.DECOMPOSED:
            if goal.parent_id is None:
                return False, "decomposed goal must have parent_id"
            return True, "ok"
        return False, f"illegal source: {goal.source}"

    @staticmethod
    def validate_tree(
        root: UserGoal,
        children: list[UserGoal],
    ) -> tuple[bool, str]:
        """验证 Goal 树合法性。

        检查:
          1. root 来源必须是 human
          2. 所有 children 来源必须是 decomposed
          3. 无循环引用
        """
        # root 必须是 human
        if root.source != GoalSource.HUMAN:
            return False, f"root goal must be human-sourced, got {root.source}"

        visited_ids = {root.id}

        for child in children:
            # child 必须是 decomposed
            if child.source != GoalSource.DECOMPOSED:
                return False, (
                    f"child goal {child.id} must be decomposed, "
                    f"got {child.source}"
                )
            # child 必须有 parent_id
            if child.parent_id is None:
                return False, f"child goal {child.id} missing parent_id"
            # 循环检测
            if child.id in visited_ids:
                return False, f"circular reference: {child.id}"
            # parent 必须存在（在 root 或已注册 children 中）
            if child.parent_id != root.id and child.parent_id not in visited_ids:
                return False, (
                    f"parent {child.parent_id} not found for child {child.id}"
                )
            visited_ids.add(child.id)

        return True, "ok"

    @staticmethod
    def reject_self_module() -> None:
        """Gateway check: 确保 ocos.goal 不导入 ocos.self。

        此方法本身不做任何检查 — 真正的检查由
        ocos/tests/test_import_rules.py 完成。
        """
        pass  # enforced at import-rule level
