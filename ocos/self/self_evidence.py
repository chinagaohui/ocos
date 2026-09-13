"""P0-1 Step 2 — S1 Evidence → Self Claim → Self Delta → governed S2 commit。

边界内只做一件事：把 S1 从 "Thinking 的 Self 来源" 转化为 "主体经验 Evidence 来源"，
并走上唯一致力路径：Evidence → Recognize → Self Claim → Self Delta(A→B)
→ SelfUpdateContract(带 provenance) → SelfBoundaryRules 治理门 → S2 commit。

关键语义（FROZEN，延续 Step0/Step1）：
  - S1 产生的东西首先是 Evidence，不是 SelfState。
  - Evidence 只有经 Recognition → Claim/Delta → governed commit 才成为 Self 变化。
  - 无 S2 commit 时，S1 的变化不改变 Thinking 消费的 Self（延续 Step1 T8）。
  - 所有写 S2 的动作都必经 SelfStateManager.commit_change（治理门），无旁路。

明确 NOT（Step 2 边界，禁止）：
  - ✗ 直接 S1→S2：本模块只消费调用方传入的 S1Evidence 快照，不复读 live S1。
  - ✗ 让 S1.render()/load() 重新进入 Thinking：本模块绝不调用 render 作 Self 输入。
  - ✗ 用 Prompt 拼接制造"Self Growth"：Claim 是结构化主体声明，非 prompt 文本。
  - ✗ 新建第二套 SelfState / 让 SelfMonitor、SelfModelBuilder 重新成为 S2。
  - ✗ 做 Worldview / WorldModel 持久化 / 修改 P0-4 实验 / 扩大 S1 审计。
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.self.self_types import (
    CapabilityStatement,
    DomainStatement,
    ExperiencePattern,
    KnowledgeConfidence,
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
)
from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary

logger = logging.getLogger(__name__)

# Recognition 准入线：S1 实测低于该次数的能力不产生 Claim（避免小样本自信）。
_MIN_CAPABILITY_ATTEMPTS = 3
# capability 判定可用/可信的实测成功率阈值（与 CapabilityAwareness.register 的 known 阈值一致）。
_CAP_KNOWN_SR = 0.6


class SelfEvidenceError(Exception):
    """S1 Evidence 管线基类异常。"""


class UnrecognizableEvidence(SelfEvidenceError):
    """Evidence 无法被识别为任何 Claim（无有效观测）。"""


# ═══════════════════════════════════════════════════════════════════════════════
# S1 Evidence — 规范输入结构（Step 2a）
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EvidenceObservation:
    """Evidence 中的单条观测。key/value/meta 均为 primitive，可追溯可哈希。"""

    key: str             # 例如 "s1.capability" | "s1.failure_mode"
    value: str
    meta: tuple[tuple[str, Any], ...] = ()  # 关键值对（有序，保证 canonical）


@dataclass(frozen=True)
class S1Evidence:
    """S1 产出的经验性 Evidence 规范输入（不是 SelfState）。

    携带 provenance 锚点：s1_version / s1_content_hash / observed_at / data_hash，
    使 evidence anchor 可追溯（P0-4 因果链证据）。
    """

    evidence_id: str
    source: str
    observed_at: datetime
    s1_version: int
    s1_content_hash: str
    data_hash: str
    observations: tuple[EvidenceObservation, ...]

    @property
    def is_empty(self) -> bool:
        return not self.observations


class ClaimKind(Enum):
    """Recognition 产出的 Claim 类别（最小规则集）。"""

    CAPABILITY_KNOWN = "capability_known"
    CAPABILITY_UNCERTAIN = "capability_uncertain"
    FAILURE_PATTERN = "failure_pattern"


@dataclass(frozen=True)
class SelfClaim:
    """S1 证据提炼出的结构化主体自述（非 prompt）。"""

    claim_id: str
    kind: ClaimKind
    statement: str           # 结构化主体声明（可审计，非 prompt）
    target_component: str    # S2 受影响组件
    key: str                 # 目标键：能力名 / failure cause / 知识域
    meta: dict               # 原始证据 meta（attempts/count/success_rate）
    evidence: S1Evidence     # 直接证据锚
    source: SelfUpdateSource
    confidence: float


@dataclass(frozen=True)
class SelfDelta:
    """一个 A→B 的自我变化提案（作用于 S2 candidate 单个组件）。"""

    claim_id: str
    evidence_id: str
    kind: ClaimKind
    target_component: str
    key: str
    old_value: Any           # A
    new_value: Any           # B
    source: SelfUpdateSource
    confidence_impact: float = 0.0


def _obs_meta(d: dict) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted((k, v) for k, v in d.items() if v is not None))


def _meta_to_dict(meta: tuple[tuple[str, Any], ...]) -> dict:
    return dict(meta)


def _data_hash(obs: tuple[EvidenceObservation, ...], s1_version: int) -> str:
    payload = json.dumps(
        {
            "v": s1_version,
            "obs": [{"key": o.key, "value": o.value, "meta": list(o.meta)}
                    for o in obs],
        },
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def capture_s1_snapshot(snapshot: dict) -> S1Evidence | None:
    """把一次已捕获的 S1 画像快照规范认定为 Evidence（不复读 live S1）。

    snapshot 由调用方单独取（如 AgentSelfModel.load() 一次）；本函数只做
    结构化装箱 + provenance 锚点计算。无可识别观测 → 返回 None。
    """
    if not snapshot:
        return None
    obs: list[EvidenceObservation] = []
    for cap in snapshot.get("capabilities") or []:
        name = cap.get("name")
        if name:
            obs.append(EvidenceObservation(
                key="s1.capability",
                value=str(name),
                meta=_obs_meta({
                    "attempts": int(cap.get("attempts") or 0),
                    "success_rate": cap.get("success_rate"),
                }),
            ))
    for fm in snapshot.get("failure_modes") or []:
        cause = fm.get("cause")
        if cause:
            obs.append(EvidenceObservation(
                key="s1.failure_mode",
                value=str(cause),
                meta=_obs_meta({"count": int(fm.get("count") or 1)}),
            ))
    if not obs:
        return None
    s1_version = int(snapshot.get("version") or 0)
    s1_hash = str(snapshot.get("content_hash") or "")
    return S1Evidence(
        evidence_id=f"S1E-{uuid.uuid4().hex[:12].upper()}",
        source="agent_self_model.snapshot",
        observed_at=datetime.now(timezone.utc),
        s1_version=s1_version,
        s1_content_hash=s1_hash,
        data_hash=_data_hash(tuple(obs), s1_version),
        observations=tuple(obs),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Recognition — Evidence → Claim（最小接线，规则化，不发散）(Step 2b)
# ═══════════════════════════════════════════════════════════════════════════════


def recognize(evidence: S1Evidence) -> list[SelfClaim]:
    """把 S1 Evidence 转换为候选 Self Claim（仅规则偿付，禁止凭空生成收益）。

    有明确准入门槛：能力实测次数 < _MIN_CAPABILITY_ATTEMPTS 时不产 Claim，
    体现 "S1 Evidence ≠ 自动 Self Growth"。
    """
    claims: list[SelfClaim] = []
    for i, obs in enumerate(evidence.observations):
        meta = _meta_to_dict(obs.meta)
        if obs.key == "s1.capability":
            attempts = int(meta.get("attempts") or 0)
            if attempts < _MIN_CAPABILITY_ATTEMPTS:
                continue  # 小样本 → 不形成 Claim
            sr = meta.get("success_rate")
            if sr is not None and sr >= _CAP_KNOWN_SR:
                kind, component = ClaimKind.CAPABILITY_KNOWN, "capability_awareness"
            else:
                kind, component = ClaimKind.CAPABILITY_UNCERTAIN, "capability_awareness"
        elif obs.key == "s1.failure_mode":
            kind, component = ClaimKind.FAILURE_PATTERN, "knowledge_boundary"
        else:
            continue
        claims.append(SelfClaim(
            claim_id=f"{evidence.evidence_id}-C{i:02d}",
            kind=kind,
            statement=_statement_for(kind, obs.value, meta),
            target_component=component,
            key=obs.value,
            meta=meta,
            evidence=evidence,
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            confidence=_confidence_for(kind, attempts=meta.get("attempts"),
                                       count=meta.get("count")),
        ))
    return claims


def _statement_for(kind: ClaimKind, key: str, meta: dict) -> str:
    if kind is ClaimKind.CAPABILITY_KNOWN:
        return f"measured capability '{key}' is reliably available"
    if kind is ClaimKind.CAPABILITY_UNCERTAIN:
        return f"measured capability '{key}' has low reliability (needs verification)"
    return f"repeated failure pattern on '{key}' observed from self experience"


def _confidence_for(kind: ClaimKind, attempts=None, count=None) -> float:
    if kind is ClaimKind.CAPABILITY_KNOWN:
        return min(0.9, 0.5 + 0.08 * int(attempts or 3))
    return 0.4


# ═══════════════════════════════════════════════════════════════════════════════
# Claim → Delta（显式 A→B） 与 apply（Step 2c）
# ═══════════════════════════════════════════════════════════════════════════════


def delta_from_claim(current: SelfModel, claim: SelfClaim) -> SelfDelta:
    """把 Claim 相对 current(committed) 计算为显式 A→B Delta。"""
    kind = claim.kind
    if kind in (ClaimKind.CAPABILITY_KNOWN, ClaimKind.CAPABILITY_UNCERTAIN):
        ca = current.capability_awareness
        old = ca.get(claim.key) if ca is not None else None
        if kind is ClaimKind.CAPABILITY_KNOWN:
            new = CapabilityStatement(
                name=claim.key, available=True, confidence=round(claim.confidence, 3),
                source=f"s1_evidence:{claim.evidence.evidence_id}",
                notes=f"claims:{claim.claim_id}",
            )
            impact = 0.03
        else:
            new = CapabilityStatement(
                name=claim.key, available=False, confidence=0.4,
                source=f"s1_evidence:{claim.evidence.evidence_id}",
                notes=f"claims:{claim.claim_id} (low reliability)",
            )
            impact = 0.0
    elif kind is ClaimKind.FAILURE_PATTERN:
        kb = current.knowledge_boundary
        old = kb.get(claim.key) if kb is not None else None
        new = DomainStatement(
            domain=claim.key,
            confidence=KnowledgeConfidence.NEEDS_VERIFICATION,
            evidence_count=int(claim.meta.get("count") or 1),
            note=f"empirical failure; claims:{claim.claim_id}; ev:{claim.evidence.evidence_id}",
        )
        impact = -0.01
    else:
        raise SelfEvidenceError(f"unknown claim kind: {kind}")
    return SelfDelta(
        claim_id=claim.claim_id,
        evidence_id=claim.evidence.evidence_id,
        kind=kind,
        target_component=claim.target_component,
        key=claim.key,
        old_value=old,
        new_value=new,
        source=claim.source,
        confidence_impact=impact,
    )


def apply_delta(candidate: SelfModel, delta: SelfDelta) -> None:
    """把一个 Delta B 应用到 S2 candidate（进入候选态，尚未提交）。"""
    kind = delta.kind
    if kind in (ClaimKind.CAPABILITY_KNOWN, ClaimKind.CAPABILITY_UNCERTAIN):
        ca = candidate.capability_awareness
        if ca is None:
            ca = CapabilityAwareness()
            candidate.capability_awareness = ca
        # move 语义：先清除旧位再注册（known/uncertain 互斥）
        ca.known.pop(delta.key, None)
        ca.uncertain.pop(delta.key, None)
        ca.register(delta.new_value)
    elif kind is ClaimKind.FAILURE_PATTERN:
        kb = candidate.knowledge_boundary
        if kb is None:
            kb = KnowledgeBoundary()
            candidate.knowledge_boundary = kb
        kb.declare(delta.new_value)
    else:
        raise SelfEvidenceError(f"unknown delta kind: {kind}")


# ═══════════════════════════════════════════════════════════════════════════════
# SelfEvidencePipeline — 唯一接线：Evidence→Claim→Delta→governed commit→S2 (Step 2d)
# ═══════════════════════════════════════════════════════════════════════════════


class SelfEvidencePipeline:
    """把 S1 Evidence 走完整治理路径送入 S2。

    - 每个 Claim 一次的独立 governed commit（version+1），provenance 并入 update_history。
    - 任何写入库动作都由 SelfStateManager.commit_change 执行（经 SelfBoundaryRules 治理门）。
    """

    def __init__(self, manager) -> None:
        self._manager = manager

    @property
    def manager(self):
        return self._manager

    def ingest(self, evidence: S1Evidence, tick_id: int = 1) -> list[SelfModel]:
        """Recognition → per-claim governed commit。返回每个成功提交的 committed 态。"""
        if evidence.is_empty:
            raise UnrecognizableEvidence("evidence has no observations")
        claims = recognize(evidence)
        if not claims:
            raise UnrecognizableEvidence(
                "evidence did not cross recognition gate (insufficient/unknown)"
            )
        committed: list[SelfModel] = []
        for claim in claims:
            delta = delta_from_claim(self._manager.current, claim)
            candidate = self._manager.build_candidate()
            apply_delta(candidate, delta)

            contract = SelfUpdateContract(
                source=delta.source,
                reason=claim.statement,
                tick_id=tick_id,
                fields_changed=(delta.target_component,),
                evidence_count=max(1, int(claim.meta.get("count") or claim.meta.get("attempts") or 1)),
                confidence_impact=delta.confidence_impact,
                evidence_ids=(evidence.evidence_id,),
                claim_id=claim.claim_id,
            )
            try:
                committed.append(self._manager.commit_change(candidate, contract))
            except Exception as e:  # noqa: BLE001 — 治理拒绝等按单个 claim 隔离，不中断批次
                logger.info("claim %s rejected by governance: %s", claim.claim_id, e)
                continue
        return committed


__all__ = [
    "SelfEvidenceError",
    "UnrecognizableEvidence",
    "EvidenceObservation",
    "S1Evidence",
    "ClaimKind",
    "SelfClaim",
    "SelfDelta",
    "capture_s1_snapshot",
    "recognize",
    "delta_from_claim",
    "apply_delta",
    "SelfEvidencePipeline",
]