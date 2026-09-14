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
import re
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.self.capability_awareness import CapabilityAwareness
from ocos.self.knowledge_boundary import KnowledgeBoundary
from ocos.self.self_types import (
    CapabilityStatement,
    ContinuityKind,
    DomainStatement,
    KnowledgeConfidence,
    RecognitionType,
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
    StanceType,
    WorldViewJudgment,
)
from ocos.self.worldview import WorldView

logger = logging.getLogger(__name__)

# Recognition 准入线：S1 实测低于该次数的能力不产生 Claim（避免小样本自信）。
_MIN_CAPABILITY_ATTEMPTS = 3
# capability 判定可用/可信的实测成功率阈值（与 CapabilityAwareness.register 的 known 阈值一致）。
_CAP_KNOWN_SR = 0.6

# G3: worldview 凝结准入 — 真实经历串联观测数（derived，非 caller 输入）低于该阈值不凝结。
_MIN_WV_OCCURRENCES = 3

# G3: divergence_kind 分类家族（REFRAME 依赖类别改变，CONFLICT 依赖同维反方向）。
_DIV_FAMILY = {
    "none": "stable",
    "unexpected_value": "expectation",
    "type_mismatch": "type",
    "missing": "existence",
    "exceeds_bound": "rating",
    "falls_short": "rating",
}


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
    WORLDVIEW_JUDGMENT = "worldview_judgment"  # G3: 真实经历 → 结构化世界观判断


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
# G3: WorldViewExperienceGate — trigger_experience_id 的 provenance 门（C）
# ═══════════════════════════════════════════════════════════════════════════════


class WorldViewExperienceGate:
    """把 "Experience 字符串关联" 提升为 "真实 Experience 验证"（防伪造 trigger）。

    三步 provenance 校验（Plan §3.3 / C）：
      1. existence    — 在注入的 experience_resolver 中找到该 Episode
      2. ownership    — resolved.identity_ref == current_identity（属于本 OCOS）
      3. evidence_link — resolved.data_hash == 当前观测的 S1Evidence.data_hash
    任一步失败 → return None → 调用方 fail-closed（无 Claim / 无 Delta / 无 commit）。

    语义：断言 resolved 是"已有真实 Experience/Episode"，而非 caller 按 ID 构造的包装。

    注入协议（resolver 复用既有 Memory/Experience 层，不新建存储）：
      resolver.resolve(episode_id) -> resolved | None
      resolved 需暴露：identity_ref / data_hash / associated_observations(可数序列)
    """

    def __init__(self, experience_resolver: Any) -> None:
        self._resolver = experience_resolver

    def resolve(self, trigger_episode: str, current_identity: str,
                expected_data_hash: str):
        """解析并验证 trigger_episode 为真实、归属本 OCOS、证据关联的经历。"""
        resolved = self._resolver.resolve(trigger_episode)
        if resolved is None:
            return None
        if getattr(resolved, "identity_ref", None) != current_identity:
            return None
        if getattr(resolved, "data_hash", None) != expected_data_hash:
            return None
        return resolved

    def count(self, resolved_experience) -> int:
        """从解析后的真实经历推导 occurrences（B）—— 非 caller 可信输入。"""
        return len(getattr(resolved_experience, "associated_observations", []))


# ═══════════════════════════════════════════════════════════════════════════════
# G3: _classify_divergence — expected+actual → 结构化 divergence_kind（D）
# ═══════════════════════════════════════════════════════════════════════════════


def _classify_divergence(expected: Any, actual: Any) -> str:
    """确定性分类器：同输入同输出，产出结构化 divergence_kind（非 bool）。

    divergence_kind ∈ {"none","type_mismatch","missing","unexpected_value",
                       "exceeds_bound","falls_short"}（见 _DIV_FAMILY）。
    expected == actual → "none"（无差异 → 不触发 conflict/reframe 类）。
    """
    if expected == actual:
        return "none"

    # 数值型偏离：方向由 magnitude 侧决定（exceeds_bound / falls_short）
    ne, na = _as_number(expected), _as_number(actual)
    if ne is not None and na is not None and ne != na:
        return "exceeds_bound" if na > ne else "falls_short"

    es = str(expected).strip()
    as_ = str(actual).strip()
    el, al = es.lower(), as_.lower()

    # 缺失类（expected 是"存在"预期而 actual 缺失）
    if al == "missing" or (el in ("file exists", "exists") and al != "exists"):
        return "missing"
    # 退出状态类
    if "exit" in el:
        return "unexpected_value"
    # 其余按类型错配处理
    return "type_mismatch"


def _as_number(x: Any):
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().lstrip("+-")
        if s and (s.isdigit() or s.replace(".", "", 1).isdigit()):
            try:
                return float(x)
            except ValueError:
                return None
    return None


def _div_family(kind: str) -> str:
    return _DIV_FAMILY.get(kind, "unknown")


_DIVERGENCE_NOTE_RE = re.compile(r"divergence:([a-z_]+)")


def _note_divergence_kind(note: str) -> str | None:
    """从既有 judgment.note 提取上次 divergence_kind（用于类别改变检测）。"""
    if not note:
        return None
    m = _DIVERGENCE_NOTE_RE.search(note)
    return m.group(1) if m else None


# ═══════════════════════════════════════════════════════════════════════════════
# G3: WorldViewRecognitionRule — 从真实经历信号推导一切（judgment/frame/stance/recognition）
# ═══════════════════════════════════════════════════════════════════════════════


class WorldViewRecognitionRule:
    """从验证过的真实经历 + 当前 worldview 推导结构化解（B+C+D+R 全推导）。

    调用方对 recognize --(gate)--> 这里，只给候选事实观测；所有语义字段
    （judgment / frame / stance_type / recognition_type / divergence_kind /
    occurrences）都由本规则对事实 + 当前 worldview 确定性推导，禁预制。
    """

    def __init__(self, gate: WorldViewExperienceGate,
                 current_worldview: WorldView | None = None) -> None:
        self._gate = gate
        self._current = current_worldview if current_worldview is not None else WorldView()

    def claim_from(self, obs: EvidenceObservation, current_identity: str,
                   evidence: S1Evidence) -> SelfClaim | None:
        meta = _meta_to_dict(obs.meta)
        domain = meta.get("domain")
        expected = meta.get("expected")
        actual = meta.get("actual")
        trigger_episode = meta.get("trigger_episode")
        # 候选事实必须齐全，否则 fail-closed。
        if not domain or expected is None or actual is None or not trigger_episode:
            return None
        # ── C: provenance 门 — 失败 fail-closed ──
        resolved = self._gate.resolve(trigger_episode, current_identity, evidence.data_hash)
        if resolved is None:
            return None
        # ── B: occurrences 由真实经历推导（忽略 caller 的 occurrences_candidate）──
        occurrences = self._gate.count(resolved)
        if occurrences < _MIN_WV_OCCURRENCES:
            return None
        # ── D: divergence_kind 确定性分类 ──
        divergence_kind = _classify_divergence(expected, actual)
        # ── R: recognition_type / stance_type / frame / judgment / confidence ──
        prior = self._current.get(domain)
        if divergence_kind == "none" and prior is None:
            return None  # 无既有判断且无差异 → 无 distinguishable pattern
        recognition_type = self._derive_recognition_type(prior, divergence_kind)
        stance_type = self._derive_stance_type(prior, divergence_kind)
        frame = self._derive_frame(domain, divergence_kind)
        judgment = _derive_judgment(domain, divergence_kind)
        confidence = self._derive_confidence(occurrences, recognition_type)
        return SelfClaim(
            claim_id=f"{evidence.evidence_id}-WV",
            kind=ClaimKind.WORLDVIEW_JUDGMENT,
            statement=judgment,
            target_component="worldview",
            key=domain,
            meta={
                "domain": domain,
                "divergence_kind": divergence_kind,
                "recognition_type": recognition_type,      # RecognitionType 实例（内部）
                "trigger_episode": trigger_episode,        # 已过 provenance 门（C）
                "occurrences": occurrences,                # derived（B）
                "frame": frame,                            # 规则生成，非输入
                "stance_type": stance_type.value,          # 规则生成，非输入
                "count": occurrences,                      # 兼容 evidence_count 映射
            },
            evidence=evidence,
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            confidence=confidence,
        )

    def _derive_recognition_type(self, prior, divergence_kind) -> RecognitionType:
        if prior is None:
            return RecognitionType.NOVEL_PATTERN
        if divergence_kind == "none":
            return RecognitionType.CONFIRM
        prior_div = _note_divergence_kind(getattr(prior, "note", ""))
        if prior_div is None:
            # 旧判断无 divergence 标注（遗留）：视为稳定理解被打破 → 冲突
            return RecognitionType.CONFLICT
        if _div_family(divergence_kind) != _div_family(prior_div):
            return RecognitionType.REFRAME          # 类别改变 → 新组织框架
        if _is_opposite(divergence_kind, prior_div):
            return RecognitionType.CONFLICT          # 同维反方向 → 修订
        return RecognitionType.CONFIRM               # 同类别重复 → 一致/强化

    def _derive_stance_type(self, prior, divergence_kind) -> StanceType:
        if prior is None:
            return StanceType.INTERPRETIVE
        if divergence_kind == "none":
            return StanceType.INTERPRETIVE
        # 出现冲突/重构 → 认识到自身理解边界
        return StanceType.EPISTEMIC if prior is not None else StanceType.NORMATIVE

    def _derive_frame(self, domain: str, divergence_kind: str) -> str:
        return f"在这类 {domain} 场景，观测可能出现 {divergence_kind} 差异"

    def _derive_confidence(self, occurrences: int, recog: RecognitionType) -> float:
        base = 0.5 + 0.06 * occurrences
        if recog in (RecognitionType.CONFLICT, RecognitionType.REFRAME):
            base -= 0.15
        if recog is RecognitionType.CONFIRM:
            base += 0.05
        return round(min(0.9, max(0.3, base)), 3)


def _is_opposite(kind: str, other: str) -> bool:
    return {kind, other} == {"exceeds_bound", "falls_short"}


def _derive_judgment(domain: str, divergence_kind: str) -> str:
    return f"对于 {domain}，同类情形可能出现 {divergence_kind} 偏离"


# ═══════════════════════════════════════════════════════════════════════════════
# Recognition — Evidence → Claim（最小接线，规则化，不发散）(Step 2b)
# ═══════════════════════════════════════════════════════════════════════════════


def recognize(evidence: S1Evidence, current: SelfModel | None = None,
              experience_resolver: Any = None, tick_id: int = 0) -> list[SelfClaim]:
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
        elif obs.key == "wv.experience":
            # G3：反预制守护 — 输入禁携 judgment/frame/stance_type/recognition_type/divergence
            forbidden = {"judgment", "frame", "stance_type", "recognition_type", "divergence"}
            if any(k in meta for k in forbidden):
                raise SelfEvidenceError(
                    "prohibited pre-fabricated judgment fields in wv.experience meta"
                )
            if current is None or experience_resolver is None:
                continue  # 无真实解析上下文 → fail-closed
            gate = WorldViewExperienceGate(experience_resolver)
            rule = WorldViewRecognitionRule(gate, current.worldview)
            wv_claim = rule.claim_from(obs, current.identity_ref, evidence)
            if wv_claim is None:
                continue  # 未过 provenance 门 / 凝结准入 → fail-closed
            claims.append(wv_claim)
            continue
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
    elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
        # G3：W1≠W0 语义结构门（A）—— 必须先构好 candidate new 再判结构变化。
        wv = current.worldview
        old = wv.get(claim.key) if wv is not None else None
        meta = claim.meta
        recog = meta.get("recognition_type")
        if not isinstance(recog, RecognitionType):
            raise SelfEvidenceError("worldview claim missing derived recognition_type")
        new = _build_worldview_judgment(old, claim, meta, current)
        if not _worldview_semantic_change(old, new):
            # 仅 confidence/evidence/tick/continuity 变化，无结构变化 → 不产 W1 delta
            raise SelfEvidenceError(
                f"worldview semantic gate: no structural W1 for domain '{claim.key}' "
                f"({recog.value} changed only confidence/evidence/tick)"
            )
        impact = _worldview_impact(recog)
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


def _build_worldview_judgment(old, claim: SelfClaim, meta: dict,
                              current: SelfModel) -> WorldViewJudgment:
    """构造 candidate new judgment；CONFIRM（强化）复制旧结构，仅证据/置信/时间变化。"""
    recog = meta["recognition_type"]
    tick = current.version  # 以 committed version 作 tick 代理（pipeline 内部表示）
    domain = claim.key
    evidence_id = claim.evidence.evidence_id
    expanded_ids = ((old.evidence_ids if old is not None else ()) + (evidence_id,))
    if recog is RecognitionType.CONFIRM and old is not None:
        # 一致/强化：结构沿用旧判断，仅证据/置信/时间变化 → 结构门必拒（不产 W1）
        return WorldViewJudgment(
            domain=domain,
            judgment=old.judgment,
            stance_type=old.stance_type,
            frame=old.frame,
            confidence=claim.confidence,
            evidence_ids=expanded_ids,
            source=claim.source.value,
            claim_id=claim.claim_id,
            created_tick=old.created_tick,
            last_updated_tick=tick,
            continuity=ContinuityKind.DERIVED,
            note=f"confirm: divergence:{meta['divergence_kind']}, ev:{evidence_id}",
        )
    return WorldViewJudgment(
        domain=domain,
        judgment=claim.statement,
        stance_type=StanceType(meta["stance_type"]),
        frame=meta["frame"],
        confidence=claim.confidence,
        evidence_ids=expanded_ids,
        source=claim.source.value,
        claim_id=claim.claim_id,
        created_tick=old.created_tick if old is not None else tick,
        last_updated_tick=tick,
        continuity=_continuity_for(old, recog),
        note=f"divergence:{meta['divergence_kind']} [recognition:{recog.value}, ev:{evidence_id}]",
    )


def _worldview_semantic_change(old, new) -> bool:
    """W1≠W0 = 语义结构变化：judgment/frame/stance_type 至少一者变化。"""
    if old is None:
        return True  # FIRST 形成
    return not (
        new.judgment == old.judgment
        and new.frame == old.frame
        and new.stance_type == old.stance_type
    )


def _continuity_for(old, recog: RecognitionType) -> ContinuityKind:
    if old is None or recog is RecognitionType.NOVEL_PATTERN:
        return ContinuityKind.FIRST
    if recog is RecognitionType.REFRAME:
        return ContinuityKind.REPLACED
    if recog is RecognitionType.CONFLICT:
        return ContinuityKind.REVISED
    return ContinuityKind.DERIVED


def _worldview_impact(recog: RecognitionType) -> float:
    if recog in (RecognitionType.CONFLICT, RecognitionType.REFRAME):
        return 0.05
    if recog is RecognitionType.NOVEL_PATTERN:
        return 0.03
    return 0.01


def _delta_is_semantic_noop(delta: SelfDelta) -> bool:
    """claim 相对 committed S2 无语义变化 → 不应产生新版本（生产 feeder 幂等门）。

    仅 evidence 指针/claim_id（每次随机）变化、主体声明内容不变时判 noop：
      - 能力：name / available / confidence 全等（source/notes 是溯源指针，非自我内容）
      - 失败模式：domain / confidence / evidence_count 全等
    这样同一 S1 实测快照重复喂（重启后补偿、S1 内容未变的闭合 tick）不会
    bump version / 灌 update_history；而成功率跨越 0.6 翻转可用性、attempts
    改变置信刻度、失败计数增长等真实变化照常提交。worldview 已由
    _worldview_semantic_change 结构门守门，此处不重复判定。
    """
    old, new = delta.old_value, delta.new_value
    if old is None or new is None:
        return False
    if delta.kind in (ClaimKind.CAPABILITY_KNOWN, ClaimKind.CAPABILITY_UNCERTAIN):
        return (
            getattr(old, "name", None) == getattr(new, "name", None)
            and bool(getattr(old, "available", None))
            == bool(getattr(new, "available", None))
            and float(getattr(old, "confidence", 0.0))
            == float(getattr(new, "confidence", 0.0))
        )
    if delta.kind is ClaimKind.FAILURE_PATTERN:
        return (
            getattr(old, "domain", None) == getattr(new, "domain", None)
            and getattr(old, "confidence", None)
            == getattr(new, "confidence", None)
            and int(getattr(old, "evidence_count", -1))
            == int(getattr(new, "evidence_count", -1))
        )
    return False


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
    elif kind is ClaimKind.WORLDVIEW_JUDGMENT:
        # G3：apply 到 worldview 容器（增量）
        wv = candidate.worldview
        if wv is None:
            wv = WorldView()
            candidate.worldview = wv
        wv.declare(delta.new_value)
    else:
        raise SelfEvidenceError(f"unknown delta kind: {kind}")


# ═══════════════════════════════════════════════════════════════════════════════
# SelfEvidencePipeline — 唯一接线：Evidence→Claim→Delta→governed commit→S2 (Step 2d)
# ═══════════════════════════════════════════════════════════════════════════════


class SelfEvidencePipeline:
    """把 S1 Evidence 走完整治理路径送入 S2。

    - 每个 Claim 一次的独立 governed commit（version+1），provenance 并入 update_history。
    - 任何写入库动作都由 SelfStateManager.commit_change 执行（经 SelfBoundaryRules 治理门）。
    - G3：experience_resolver 注入真实 Experience/Episode 解析，worldview 因果链
      （trigger_experience_id + recognition_type）只在 gate 验证通过后写入 contract。
    """

    def __init__(self, manager, experience_resolver: Any = None) -> None:
        self._manager = manager
        self._experience_resolver = experience_resolver

    @property
    def manager(self):
        return self._manager

    @property
    def experience_resolver(self):
        return self._experience_resolver

    def ingest(self, evidence: S1Evidence, tick_id: int = 1) -> list[SelfModel]:
        """Recognition → per-claim governed commit。返回每个成功提交的 committed 态。"""
        if evidence.is_empty:
            raise UnrecognizableEvidence("evidence has no observations")
        claims = recognize(
            evidence,
            current=self._manager.current,
            experience_resolver=self._experience_resolver,
            tick_id=tick_id,
        )
        if not claims:
            raise UnrecognizableEvidence(
                "evidence did not cross recognition gate (insufficient/unknown)"
            )
        committed: list[SelfModel] = []
        for claim in claims:
            try:
                delta = delta_from_claim(self._manager.current, claim)
            except Exception as e:  # noqa: BLE001 — 语义结构门/未知 kind 等按 claim 隔离
                logger.info("claim %s produced no delta: %s", claim.claim_id, e)
                continue
            # 生产 feeder 幂等：claim 与 committed S2 语义相同（仅溯源指针刷新）
            # → 不产新版本，防重复喂灌爆 version/update_history。
            if _delta_is_semantic_noop(delta):
                logger.info(
                    "claim %s semantically identical to committed S2 — skipped",
                    claim.claim_id,
                )
                continue
            candidate = self._manager.build_candidate()
            apply_delta(candidate, delta)

            count = claim.meta.get("count") or claim.meta.get("attempts") or 1
            contract = SelfUpdateContract(
                source=delta.source,
                reason=claim.statement,
                tick_id=tick_id,
                fields_changed=(delta.target_component,),
                evidence_count=max(1, int(count)),
                confidence_impact=delta.confidence_impact,
                evidence_ids=(evidence.evidence_id,),
                claim_id=claim.claim_id,
            )
            # G3：worldview 因果链持久锚（C）— 仅当 gate 验证通过后写入（fail-closed）
            if claim.kind is ClaimKind.WORLDVIEW_JUDGMENT:
                recog = claim.meta.get("recognition_type")
                if isinstance(recog, RecognitionType):
                    contract = replace(
                        contract,
                        recognition_type=recog.value,
                        trigger_experience_id=str(claim.meta.get("trigger_episode") or ""),
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
    "WorldViewExperienceGate",
    "WorldViewRecognitionRule",
    "capture_s1_snapshot",
    "recognize",
    "delta_from_claim",
    "apply_delta",
    "SelfEvidencePipeline",
]
