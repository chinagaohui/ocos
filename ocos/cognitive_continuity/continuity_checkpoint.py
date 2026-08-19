"""Phase 49: ContinuityCheckpoint — 连续性检查点。

定期快照 OCOS 完整状态，用于长期恢复和连续性验证。

快照内容:
    - IdentitySnapshot (Phase 49)
    - CognitiveSignature (Phase 48)
    - LifeMemoryGraph 摘要
    - Timeline 最后N条
    - KnowledgeAging 统计

不阻止演化，不强制恢复——只是提供检查点能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_continuity.continuity_types import (
    IdentitySnapshot,
    KnowledgeAge,
)
from ocos.cognitive_continuity.life_memory_graph import LifeMemoryEngine
from ocos.cognitive_continuity.cognitive_timeline import TimelineEngine
from ocos.cognitive_continuity.identity_continuity import (
    IdentityContinuityEngine, ContinuityCheck,
)
from ocos.cognitive_continuity.knowledge_aging import KnowledgeAgingEngine


@dataclass
class CheckpointState:
    """检查点状态——一次完整快照。"""
    checkpoint_id: str = ""
    tick_id: int = 0
    label: str = ""
    identity_snapshot: IdentitySnapshot | None = None
    experience_count: int = 0
    timeline_past_count: int = 0
    timeline_intent_count: int = 0
    knowledge_fresh: int = 0
    knowledge_aging: int = 0
    knowledge_legacy: int = 0
    knowledge_archived: int = 0


@dataclass
class ContinuityCheckpoint:
    """连续性检查点管理器。

    定期创建完整状态快照。
    """

    _checkpoints: list[CheckpointState] = field(default_factory=list)

    def create_checkpoint(
        self,
        tick_id: int,
        label: str,
        identity: IdentityContinuityEngine,
        memory: LifeMemoryEngine,
        timeline: TimelineEngine,
        knowledge: KnowledgeAgingEngine,
    ) -> CheckpointState:
        """创建检查点——捕获全部子系统状态。"""
        # 提取各子系统摘要
        age_summary = knowledge.weight_summary()

        state = CheckpointState(
            checkpoint_id=f"cp:{tick_id}",
            tick_id=tick_id,
            label=label,
            identity_snapshot=identity.snapshots[-1] if identity.snapshots else None,
            experience_count=memory.graph.total_experiences,
            timeline_past_count=timeline.timeline.past_count,
            timeline_intent_count=timeline.timeline.intent_count,
            knowledge_fresh=age_summary.get(KnowledgeAge.FRESH, 0),
            knowledge_aging=age_summary.get(KnowledgeAge.AGING, 0),
            knowledge_legacy=age_summary.get(KnowledgeAge.LEGACY, 0),
            knowledge_archived=age_summary.get(KnowledgeAge.ARCHIVED, 0),
        )

        self._checkpoints.append(state)
        if len(self._checkpoints) > 52:  # 保留一年
            self._checkpoints = self._checkpoints[-52:]
        return state

    @property
    def latest(self) -> CheckpointState | None:
        return self._checkpoints[-1] if self._checkpoints else None

    @property
    def count(self) -> int:
        return len(self._checkpoints)


__all__ = ["CheckpointState", "ContinuityCheckpoint"]
