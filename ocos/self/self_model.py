"""Phase 40: SelfModel 组装器 + 更新约束。

SelfModel 不是 Identity.anchor，而是其运行时投影。
组装器负责:
    1. 从 Identity.anchor 创建初始 SelfModel
    2. 约束更新来源（合同校验）
    3. 提供统一的查询接口
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from ocos.self.self_types import (
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
    SelfBoundaryRules,
)

from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary
from ocos.self.experience_profile import ExperienceProfile
from ocos.self.preference_model import PreferenceModel
from ocos.self.cognitive_state import CognitiveState


# ── 组装器 ──


def create_self_model(identity_anchor: Any) -> SelfModel:
    """从 Identity.anchor 创建 SelfModel。

    identity_anchor 必须有 get_identity_id() 方法（IdentityAnchor 协议）。
    """
    if not hasattr(identity_anchor, "get_identity_id"):
        raise TypeError(
            "identity_anchor must implement get_identity_id() method. "
            f"Got: {type(identity_anchor).__name__}"
        )

    agent_id = identity_anchor.get_identity_id()
    timestamp = datetime.now(timezone.utc)

    return SelfModel(
        identity_ref=agent_id,
        version=1,
        created_at=timestamp,
        updated_at=timestamp,
        capability_awareness=None,
        knowledge_boundary=None,
        experience_profile=None,
        preference_model=None,
        cognitive_state=None,
        self_confidence=0.5,
        boundary_rules=SelfBoundaryRules(),
    )


# ── 初始化助手 ──


def initialize_empty_components(self_model: SelfModel) -> SelfModel:
    """用空组件初始化 SelfModel（如果尚未初始化）。"""
    if self_model.capability_awareness is None:
        self_model.capability_awareness = CapabilityAwareness()
    if self_model.knowledge_boundary is None:
        self_model.knowledge_boundary = KnowledgeBoundary()
    if self_model.experience_profile is None:
        self_model.experience_profile = ExperienceProfile()
    if self_model.preference_model is None:
        self_model.preference_model = PreferenceModel()
    if self_model.cognitive_state is None:
        self_model.cognitive_state = CognitiveState()
    self_model.updated_at = datetime.now(timezone.utc)
    return self_model


# ── 更新 API ──


def update_capability(
    self_model: SelfModel,
    capability: CapabilityAwareness,
    source: SelfUpdateSource,
    reason: str,
    tick_id: int,
) -> bool:
    """更新能力认知。"""
    contract = SelfUpdateContract(
        source=source,
        reason=reason,
        tick_id=tick_id,
        fields_changed=("capability_awareness",),
        confidence_impact=0.05,
    )
    return self_model.update(contract, "capability_awareness", capability)


def update_knowledge_boundary(
    self_model: SelfModel,
    knowledge: KnowledgeBoundary,
    source: SelfUpdateSource,
    reason: str,
    tick_id: int,
) -> bool:
    """更新知识边界。"""
    contract = SelfUpdateContract(
        source=source,
        reason=reason,
        tick_id=tick_id,
        fields_changed=("knowledge_boundary",),
        confidence_impact=0.05,
    )
    return self_model.update(contract, "knowledge_boundary", knowledge)


def update_experience(
    self_model: SelfModel,
    profile: ExperienceProfile,
    source: SelfUpdateSource,
    reason: str,
    tick_id: int,
) -> bool:
    """更新经验特征。"""
    contract = SelfUpdateContract(
        source=source,
        reason=reason,
        tick_id=tick_id,
        fields_changed=("experience_profile",),
        confidence_impact=0.10,
        evidence_count=profile.total_experiences,
    )
    return self_model.update(contract, "experience_profile", profile)


def update_preferences(
    self_model: SelfModel,
    prefs: PreferenceModel,
    source: SelfUpdateSource,
    reason: str,
    tick_id: int,
) -> bool:
    """更新偏好模型。"""
    contract = SelfUpdateContract(
        source=source,
        reason=reason,
        tick_id=tick_id,
        fields_changed=("preference_model",),
        confidence_impact=0.03,
    )
    return self_model.update(contract, "preference_model", prefs)


def update_cognitive_state(
    self_model: SelfModel,
    state: CognitiveState,
    source: SelfUpdateSource,
    reason: str,
    tick_id: int,
) -> bool:
    """更新认知状态。"""
    contract = SelfUpdateContract(
        source=source,
        reason=reason,
        tick_id=tick_id,
        fields_changed=("cognitive_state",),
        confidence_impact=0.0,  # 实时状态不影响整体置信度
    )
    return self_model.update(contract, "cognitive_state", state)


# ── 查询 ──


def self_summary(self_model: SelfModel) -> str:
    """生成 SelfModel 的文本摘要。"""
    parts = [f"Self v{self_model.version}, confidence={self_model.self_confidence:.2f}"]

    if self_model.capability_awareness:
        parts.append(f"  Capabilities: {self_model.capability_awareness.summary()}")
    if self_model.knowledge_boundary:
        parts.append(f"  Knowledge: {self_model.knowledge_boundary.summary()}")
    if self_model.experience_profile:
        parts.append(f"  Experience: {self_model.experience_profile.summary()}")
    if self_model.preference_model:
        parts.append(f"  Preferences: {self_model.preference_model.summary()}")
    if self_model.cognitive_state:
        parts.append(f"  Cognitive: {self_model.cognitive_state.summary()}")

    parts.append(f"  Updates: {len(self_model.update_history)}")
    return "\n".join(parts)


__all__ = [
    "create_self_model",
    "initialize_empty_components",
    "update_capability",
    "update_knowledge_boundary",
    "update_experience",
    "update_preferences",
    "update_cognitive_state",
    "self_summary",
]
