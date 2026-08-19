"""Phase 47: EvolutionMemory — 进化记忆。

记录每次进化的完整历史:
    - 触发信号
    - 提案
    - 影响分析
    - 沙箱结果
    - 审批
    - 迁移结果
    - 回滚记录 (如有)

为未来的进化提供决策参考。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
)


@dataclass
class EvolutionMemory:
    """进化记忆——记录完整进化历史。"""

    _history: list[dict] = field(default_factory=list)

    def record(self, proposal: EvolutionProposal, stage: str, detail: str = "") -> None:
        """记录进化的一个阶段。"""
        self._history.append({
            "proposal_id": proposal.proposal_id,
            "stage": stage,
            "state": proposal.state.value,
            "domain": proposal.domain.value,
            "trigger": proposal.trigger.value,
            "description": proposal.description[:100],
            "success": proposal.state in (EvolutionState.ACTIVE,),
            "detail": detail[:200],
        })

    def proposal_history(self, proposal_id: str) -> list[dict]:
        """查询特定提案的完整历史。"""
        return [h for h in self._history if h["proposal_id"] == proposal_id]

    def successful_evolutions(self) -> list[dict]:
        """所有成功的进化。"""
        return [h for h in self._history if h["success"]]

    def failed_evolutions(self) -> list[dict]:
        """所有失败的进化。"""
        return [h for h in self._history if not h["success"]]

    def evolution_domains(self) -> dict[str, int]:
        """统计各领域的进化次数。"""
        counts: dict[str, int] = {}
        for h in self._history:
            domain = h["domain"]
            counts[domain] = counts.get(domain, 0) + 1
        return counts

    @property
    def total_evolutions(self) -> int:
        return len(self._history)


__all__ = ["EvolutionMemory"]
