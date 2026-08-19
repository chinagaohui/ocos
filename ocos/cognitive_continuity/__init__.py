"""Phase 49: Cognitive Continuity System — 认知连续性系统。

解决核心问题:
    一个 OCOS 使用 5 年、10 年后，如何保持连续人格和认知积累？

四大支柱:
    1. Life Memory Graph — 层次化长期记忆 (年→月→周→日→经验)
    2. Cognitive Timeline  — 过去的我→现在的我→未来规划
    3. Identity Continuity — 身份一致性检测 (不阻止演化)
    4. Knowledge Aging     — 知识时效性管理 (分级衰减)

核心边界:
    CC49-01: Continuity ≠ Archive   — 质量筛选，不保存一切
    CC49-02: Identity Continuity ≠ Freeze — 检测漂移，不阻止演化
    CC49-03: Knowledge Aging ≠ Amnesia — 分级老化，不丢失核心
    CC49-04: Timeline ≠ Prediction  — 记录过去与现在，不预测未来
"""

from ocos.cognitive_continuity.continuity_types import (
    TimeGranularity,
    TimeAnchor,
    ExperienceNode,
    TimeContainer,
    LifeMemoryGraph,
    TimelineEntry,
    CognitiveTimeline,
    IdentitySnapshot,
    KnowledgeAge,
    AgedKnowledge,
)
from ocos.cognitive_continuity.life_memory_graph import LifeMemoryEngine
from ocos.cognitive_continuity.cognitive_timeline import TimelineEngine
from ocos.cognitive_continuity.identity_continuity import (
    ContinuityCheck, IdentityContinuityEngine,
)
from ocos.cognitive_continuity.knowledge_aging import (
    KnowledgeAgingEngine, TICKS_PER_MONTH,
)
from ocos.cognitive_continuity.continuity_checkpoint import (
    CheckpointState, ContinuityCheckpoint,
)

__all__ = [
    # Types
    "TimeGranularity", "TimeAnchor",
    "ExperienceNode", "TimeContainer", "LifeMemoryGraph",
    "TimelineEntry", "CognitiveTimeline",
    "IdentitySnapshot", "KnowledgeAge", "AgedKnowledge",
    # Engines
    "LifeMemoryEngine", "TimelineEngine",
    "IdentityContinuityEngine", "ContinuityCheck",
    "KnowledgeAgingEngine", "TICKS_PER_MONTH",
    # Checkpoint
    "CheckpointState", "ContinuityCheckpoint",
]
