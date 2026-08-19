"""Phase 40: Self Model — Runtime Self Representation。

Self Model 不是 Identity.anchor（那个不可变），
而是建立在 Identity 之上的可运行、可观察、可更新的自我认知投影。

核心约束:
    S40-01: Identity.anchor 不可变 — identity_ref 只读引用
    S40-02: Self ≠ Goal — 不生成目标
    S40-03: Self ≠ Belief — 自身状态 ≠ 世界判断
    S40-04: 更新来源受限 — Experience/Registry/MemoryConsolidation/RuntimeObservation

五个组件:
    CapabilityAwareness  — "我能做什么"
    KnowledgeBoundary    — "我知道什么"
    ExperienceProfile    — "我经历过什么"
    PreferenceModel      — "我和用户偏好什么"
    CognitiveState       — "我当前认知状态怎样"
"""

from ocos.self.self_types import (
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
    SelfBoundaryRules,
    KnowledgeConfidence,
    CapabilityStatement,
    DomainStatement,
    ExperiencePattern,
    PreferenceType,
    PreferenceEntry,
)

from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary
from ocos.self.experience_profile import ExperienceProfile
from ocos.self.preference_model import PreferenceModel
from ocos.self.cognitive_state import CognitiveState, CognitiveLoad, AttentionHealth

from ocos.self.self_model import (
    create_self_model,
    initialize_empty_components,
    update_capability,
    update_knowledge_boundary,
    update_experience,
    update_preferences,
    update_cognitive_state,
    self_summary,
)

__all__ = [
    # Core types
    "SelfModel",
    "SelfUpdateContract",
    "SelfUpdateSource",
    "SelfBoundaryRules",
    "KnowledgeConfidence",
    "CapabilityStatement",
    "DomainStatement",
    "ExperiencePattern",
    "PreferenceType",
    "PreferenceEntry",
    # Components
    "CapabilityAwareness",
    "KnowledgeBoundary",
    "ExperienceProfile",
    "PreferenceModel",
    "CognitiveState",
    "CognitiveLoad",
    "AttentionHealth",
    # Assembler
    "create_self_model",
    "initialize_empty_components",
    "update_capability",
    "update_knowledge_boundary",
    "update_experience",
    "update_preferences",
    "update_cognitive_state",
    "self_summary",
]
