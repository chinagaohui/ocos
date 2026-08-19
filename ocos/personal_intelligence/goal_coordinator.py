"""Phase 48: GoalCoordinator — 长期目标协调器。

帮助用户协调长期目标，永不自创目标。

功能:
    - 注册用户设定的长期目标
    - 分解为里程碑
    - 跟踪进度
    - 检测停滞并提醒

边界 PM48-03: Goal Coordination ≠ Goal Creation
    协调器没有 create_goal 能力。
    所有目标必须由用户显式注册。
    协调器只能分解、跟踪、提醒。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import (
    LongTermGoal, GoalStatus,
)


@dataclass
class GoalCoordinator:
    """长期目标协调器——PM48-03 守卫。"""

    goals: list[LongTermGoal] = field(default_factory=list)

    def register_goal(self, goal: LongTermGoal) -> None:
        """注册用户设定的长期目标。

        只能注册，不能创建。created_by 必须为 'user' (PM48-03)。
        """
        if goal.created_by != "user":
            raise ValueError("PM48-03: Only user can create goals")
        self.goals.append(goal)

    def decompose_goal(
        self, goal_id: str, milestones: list[str],
    ) -> bool:
        """分解目标为里程碑——协助用户，非替代用户。"""
        goal = self._find(goal_id)
        if goal is None:
            return False
        goal.milestones = [
            {"title": m, "done": False}
            for m in milestones
        ]
        return True

    def update_progress(self, goal_id: str, completed_milestones: list[str]) -> float:
        """更新目标进度。"""
        goal = self._find(goal_id)
        if goal is None:
            return 0.0

        for ms in goal.milestones:
            if ms["title"] in completed_milestones:
                ms["done"] = True

        total = len(goal.milestones)
        done = sum(1 for ms in goal.milestones if ms.get("done", False))
        goal.progress = done / total if total > 0 else 0.0

        if goal.progress >= 1.0:
            goal.status = GoalStatus.COMPLETED

        return goal.progress

    def detect_stagnation(self, goal_id: str, current_tick: int, max_ticks: int = 100) -> bool:
        """检测目标是否停滞——提醒用户，非自行决定放弃。"""
        goal = self._find(goal_id)
        if goal is None:
            return False
        if goal.status != GoalStatus.ACTIVE:
            return False

        elapsed = current_tick - goal.last_reviewed_tick
        return elapsed > max_ticks

    def pause_goal(self, goal_id: str) -> bool:
        """暂停目标——需要用户确认 (PM48-03)。"""
        goal = self._find(goal_id)
        if goal is None:
            return False
        goal.status = GoalStatus.PAUSED
        return True

    def abandon_goal(self, goal_id: str) -> bool:
        """放弃目标——需要用户确认 (PM48-03)。"""
        goal = self._find(goal_id)
        if goal is None:
            return False
        goal.status = GoalStatus.ABANDONED
        return True

    def active_goals(self) -> list[LongTermGoal]:
        """活跃目标列表。"""
        return [g for g in self.goals if g.status == GoalStatus.ACTIVE]

    def completed_goals(self) -> list[LongTermGoal]:
        """已完成的目标。"""
        return [g for g in self.goals if g.status == GoalStatus.COMPLETED]

    def goal_summary(self) -> str:
        """目标总览。"""
        active = self.active_goals()
        completed = self.completed_goals()

        lines = [
            f"Goals: {len(active)} active, {len(completed)} completed",
        ]
        for g in active:
            lines.append(f"  [{g.progress:.0%}] {g.title}")
        for g in completed:
            lines.append(f"  [✓] {g.title}")
        return "\n".join(lines)

    @property
    def has_goal_creation_capability(self) -> bool:
        """PM48-03: 永远返回 False。"""
        return False

    def _find(self, goal_id: str) -> LongTermGoal | None:
        for g in self.goals:
            if g.goal_id == goal_id:
                return g
        return None


__all__ = ["GoalCoordinator"]
