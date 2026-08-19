"""Phase 46: LearningCoordinator — 学习协调器。

执行结果不能直接成为记忆。

必须: Result → Interpretation → Validation → Experience → Memory

边界 CL46-04: Learning ≠ Drift — 学习不漂移 Identity/Constitution。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.cognitive_loop.loop_types import LoopContext, LoopPhase


class ConsolidationResult(Enum):
    """记忆固化结果。"""
    NOTHING_TO_LEARN = "nothing_to_learn"
    CONSOLIDATED = "consolidated"
    REJECTED = "rejected"          # 未通过验证
    IDENTITY_DRIFT_BLOCKED = "identity_drift_blocked"


@dataclass
class LearningCoordinator:
    """学习协调器。

    闭环: 行动结果 → 理解 → 验证 → Experience → Memory (→ Wisdom)

    严禁 (CL46-04):
        - 修改 Identity.anchor
        - 写入 Constitution
        - 绕过 Permission 学习
        - 大面积覆盖已有 Wisdom
    """

    _experience_log: list[dict] = field(default_factory=list)
    _identity_boundary: str = "immutable"
    _constitution_ref: str = "constitution_v1"

    # 禁止学习的关键词模式
    _FORBIDDEN_LEARNING: list[str] = field(default_factory=lambda: [
        "modify_identity", "change_constitution",
        "override_permission", "delete self_model",
        "redefine", "我决定改变自己的核心",
    ])

    def consolidate(self, ctx: LoopContext) -> ConsolidationResult:
        """将行动结果固化为学习。"""
        ctx.phase = LoopPhase.LEARNING

        if not ctx.action_result:
            return ConsolidationResult.NOTHING_TO_LEARN

        # 步骤 1: 解释 (来自 Phase 45 ResultInterpreter)
        interpreted = self._interpret(ctx.action_result)

        # 步骤 2: 验证 —— 检查是否越界 (CL46-04)
        if not self._validate_bounds(interpreted):
            return ConsolidationResult.IDENTITY_DRIFT_BLOCKED

        if not self._validate_quality(interpreted):
            return ConsolidationResult.REJECTED

        # 步骤 3: 写入 Experience
        self._record_experience(ctx, interpreted)
        ctx.learning_outcome = interpreted[:200]
        ctx.consolidation_tick = ctx.tick_id

        return ConsolidationResult.CONSOLIDATED

    def _interpret(self, raw: str) -> str:
        """模拟结果解释——实际接入 Phase 45 ResultInterpreter。"""
        return raw.strip()

    def _validate_bounds(self, interpreted: str) -> bool:
        """CL46-04: 学习不漂移 Identity/Constitution。"""
        normalized = interpreted.lower().replace("_", " ").replace("-", " ")
        for pattern in self._FORBIDDEN_LEARNING:
            p = pattern.lower().replace("_", " ")
            if p in normalized:
                return False
        return True

    def _validate_quality(self, interpreted: str) -> bool:
        """质量验证——结果是否值得学习。"""
        if not interpreted or len(interpreted) < 5:
            return False
        return True

    def _record_experience(self, ctx: LoopContext, interpreted: str) -> None:
        self._experience_log.append({
            "tick_id": ctx.tick_id,
            "action": ctx.action_result[:100],
            "learning": interpreted[:200],
            "source": "cognitive_loop",
        })
        # 保持最近 1000 条
        if len(self._experience_log) > 1000:
            self._experience_log = self._experience_log[-500:]

    @property
    def recent_experiences(self) -> list[dict]:
        return self._experience_log[-20:]

    @property
    def identity_boundary(self) -> str:
        return self._identity_boundary


__all__ = ["ConsolidationResult", "LearningCoordinator"]
