"""BELIEF_MODEL v1.0 — Belief 是 OCOS 的认知地图。

Memory = "发生过什么" (事实记录)
Belief = "我认为什么是真的" (概率判断 + 预测基础)

核心组件:
    BeliefManager
        ├── add_belief()        创建新信念
        ├── update_with_evidence() 证据驱动的概率更新
        ├── decay_check()        时间衰减
        ├── query()             按维度/象限检索
        ├── merge_beliefs()     合并重复信念
        └── get_strongest()     获取最强信念 TOP-N

四象限: Assumption / Conviction / Speculation / Suspicion
更新: 证据加权 + 时间衰减 + 反确认偏误防御
持久化: SQLite (TBD — 当前内存模式)
"""

from __future__ import annotations

import uuid
import time
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ────────────────────────────────────────────────────────────────────


class BeliefDimension(str, Enum):
    """信念所属认知维度。"""
    WORLD_KNOWLEDGE = "WORLD_KNOWLEDGE"   # 关于外部世界的知识
    USER_MODEL = "USER_MODEL"             # 关于用户的知识
    TOOL_MODEL = "TOOL_MODEL"             # 关于工具/系统的知识
    SELF_MODEL = "SELF_MODEL"             # 关于自身的知识


class BeliefQuadrant(str, Enum):
    """四象限分类 (Probability × Evidence Strength)。"""
    ASSUMPTION = "ASSUMPTION"     # 高概率 + 弱证据 → 默认假设
    CONVICTION = "CONVICTION"     # 高概率 + 强证据 → 确信
    SPECULATION = "SPECULATION"   # 低概率 + 弱证据 → 推测
    SUSPICION = "SUSPICION"       # 低概率 + 强证据 → 怀疑


class EvidenceSource(str, Enum):
    """证据来源（权重不同）。"""
    USER_STATED = "USER_STATED"           # w=0.9
    DIRECT_OBSERVATION = "DIRECT_OBSERVATION"  # w=0.7
    INFERRED = "INFERRED"                 # w=0.4
    SECOND_HAND = "SECOND_HAND"           # w=0.3
    DEFAULT_ASSUMPTION = "DEFAULT_ASSUMPTION"  # w=0.1


# 证据来源权重映射
SOURCE_WEIGHTS: dict[EvidenceSource, float] = {
    EvidenceSource.USER_STATED: 0.9,
    EvidenceSource.DIRECT_OBSERVATION: 0.7,
    EvidenceSource.INFERRED: 0.4,
    EvidenceSource.SECOND_HAND: 0.3,
    EvidenceSource.DEFAULT_ASSUMPTION: 0.1,
}


# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class Evidence:
    """信念证据 — 单条支撑或反对信息。"""
    evidence_id: str = field(default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}")
    belief_id: str = ""
    polarity: str = "positive"        # positive / negative / neutral
    source: EvidenceSource = EvidenceSource.DIRECT_OBSERVATION
    description: str = ""
    timestamp: float = field(default_factory=time.time)
    recency_weight: float = 1.0       # 自动衰减

    def get_weight(self) -> float:
        return SOURCE_WEIGHTS.get(self.source, 0.3) * self.recency_weight


@dataclass
class Belief:
    """信念 — OCOS 对世界的一项概率判断。"""
    belief_id: str = field(default_factory=lambda: f"bel-{uuid.uuid4().hex[:8]}")
    statement: str = ""
    dimension: BeliefDimension = BeliefDimension.WORLD_KNOWLEDGE
    probability: float = 0.5          # 0.0 ~ 1.0
    evidence_chain: list[Evidence] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    source: EvidenceSource = EvidenceSource.DEFAULT_ASSUMPTION
    decay_rate: float = 0.02          # 每天衰减量
    positive_count: int = 0           # 正面证据计数（防确认偏误）
    strength: float = 0.5             # prob × (1 + evidence_count × 0.1)

    @property
    def quadrant(self) -> BeliefQuadrant:
        """动态计算四象限分类。"""
        evidence_strength = len(self.evidence_chain)
        if self.probability >= 0.5:
            if evidence_strength >= 3:
                return BeliefQuadrant.CONVICTION
            return BeliefQuadrant.ASSUMPTION
        else:
            if evidence_strength >= 3:
                return BeliefQuadrant.SUSPICION
            return BeliefQuadrant.SPECULATION

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_chain)

    def to_dict(self) -> dict:
        return {
            "belief_id": self.belief_id,
            "statement": self.statement,
            "dimension": self.dimension.value,
            "probability": round(self.probability, 4),
            "quadrant": self.quadrant.value,
            "evidence_count": self.evidence_count,
            "strength": round(self.strength, 4),
            "source": self.source.value,
            "decay_rate": self.decay_rate,
            "last_updated": self.last_updated,
        }


# ── BeliefManager ────────────────────────────────────────────────────────────


class BeliefManager:
    """信念引擎 — 管理 OCOS 的全部认知信念。

    职责:
        - 创建/更新/删除信念
        - 证据驱动的概率更新
        - 时间衰减 + 防确认偏误
        - 按维度/象限检索
        - 合并重复信念

    CONSTRAINTS:
        - max_beliefs = 1000
        - max_probability = 0.99 (保留可修正性)
        - min_probability = 0.01 (低于此清理)
        - decay_floor = 0.05 (标记 DORMANT)
    """

    MAX_BELIEFS = 1000
    MAX_PROBABILITY = 0.99
    MIN_PROBABILITY = 0.01
    DECAY_FLOOR = 0.05
    CONFIRMATION_BIAS_THRESHOLD = 3  # 每 N 条正面证据后主动搜寻反面

    def __init__(self):
        self._beliefs: dict[str, Belief] = {}
        self._event_log: list[dict] = []

    # ── CRUD ──────────────────────────────────────────────────────────────

    def add_belief(
        self,
        statement: str,
        dimension: BeliefDimension = BeliefDimension.WORLD_KNOWLEDGE,
        probability: float = 0.5,
        source: EvidenceSource = EvidenceSource.DEFAULT_ASSUMPTION,
        evidence_description: str = "",
        decay_rate: float = 0.02,
    ) -> Belief:
        """创建新信念。必须有至少一条证据。"""
        belief = Belief(
            statement=statement,
            dimension=dimension,
            probability=max(self.MIN_PROBABILITY, min(self.MAX_PROBABILITY, probability)),
            source=source,
            decay_rate=decay_rate,
        )
        # 必须有 evidence
        if evidence_description:
            self.add_evidence(belief, evidence_description, "positive", source)
        else:
            self.add_evidence(belief, f"Initial assumption: {statement}", "neutral", source)

        self._garbage_collect()
        self._beliefs[belief.belief_id] = belief
        self._compute_strength(belief)
        self._log("belief_added", {"belief_id": belief.belief_id, "statement": statement})
        return belief

    def get(self, belief_id: str) -> Optional[Belief]:
        return self._beliefs.get(belief_id)

    def remove(self, belief_id: str) -> bool:
        if belief_id in self._beliefs:
            del self._beliefs[belief_id]
            self._log("belief_removed", {"belief_id": belief_id})
            return True
        return False

    # ── Evidence Update ───────────────────────────────────────────────────

    def add_evidence(
        self,
        belief: Belief,
        description: str,
        polarity: str = "neutral",
        source: EvidenceSource = EvidenceSource.DIRECT_OBSERVATION,
    ) -> Evidence:
        """向信念添加一条证据。"""
        evidence = Evidence(
            belief_id=belief.belief_id,
            polarity=polarity,
            source=source,
            description=description,
        )
        belief.evidence_chain.append(evidence)

        if polarity == "positive":
            belief.positive_count += 1
        elif polarity == "negative":
            belief.positive_count = max(0, belief.positive_count - 1)

        self._log("evidence_added", {
            "belief_id": belief.belief_id,
            "polarity": polarity,
            "source": source.value,
        })
        return evidence

    def update_with_evidence(
        self,
        belief_id: str,
        description: str,
        polarity: str = "neutral",
        source: EvidenceSource = EvidenceSource.DIRECT_OBSERVATION,
    ) -> Optional[Belief]:
        """核心更新：证据驱动的概率更新 (Bayesian 加权)。

        new_prob = (old_prob × P_weight + evidence_impact × E_weight)
                   ─────────────────────────────────────────────────
                              P_weight + E_weight
        """
        belief = self._beliefs.get(belief_id)
        if not belief:
            return None

        # 添加证据
        self.add_evidence(belief, description, polarity, source)

        # 计算证据影响力
        e_impact = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}[polarity]
        e_weight = SOURCE_WEIGHTS.get(source, 0.3)

        # 先验权重基于证据总量
        p_weight = 1.0 + len(belief.evidence_chain) * 0.5

        # Bayesian 更新
        old_prob = belief.probability
        new_prob = (old_prob * p_weight + e_impact * e_weight) / (p_weight + e_weight)

        # 钳制
        belief.probability = max(self.MIN_PROBABILITY, min(self.MAX_PROBABILITY, new_prob))
        belief.last_updated = time.time()

        # 防御确认偏误
        belief.positive_count += 1 if polarity == "positive" else 0
        if belief.positive_count >= self.CONFIRMATION_BIAS_THRESHOLD:
            belief.positive_count = 0
            self._log("confirmation_bias_alert", {
                "belief_id": belief_id,
                "positive_streak": self.CONFIRMATION_BIAS_THRESHOLD,
            })

        self._compute_strength(belief)
        self._log("belief_updated", {
            "belief_id": belief_id,
            "old_prob": round(old_prob, 4),
            "new_prob": round(belief.probability, 4),
            "quadrant": belief.quadrant.value,
        })
        return belief

    # ── Decay ─────────────────────────────────────────────────────────────

    def decay_check(self, now: Optional[float] = None) -> list[Belief]:
        """检查所有信念的时间衰减。返回衰减超过阈值的信念列表。"""
        now = now or time.time()
        decayed = []

        for belief in list(self._beliefs.values()):
            days_since_update = (now - belief.last_updated) / 86400.0
            if days_since_update <= 0:
                continue

            # P(t) = P₀ × (1 - decay_rate)^days
            new_prob = belief.probability * ((1.0 - belief.decay_rate) ** days_since_update)
            old_prob = belief.probability
            belief.probability = max(self.MIN_PROBABILITY, min(self.MAX_PROBABILITY, new_prob))

            if belief.probability <= self.DECAY_FLOOR:
                decayed.append(belief)
                self._log("belief_dormant", {
                    "belief_id": belief.belief_id,
                    "statement": belief.statement[:60],
                    "prob": round(belief.probability, 4),
                })
            elif abs(new_prob - old_prob) > 0.01:
                self._compute_strength(belief)
                self._log("belief_decayed", {
                    "belief_id": belief.belief_id,
                    "old_prob": round(old_prob, 4),
                    "new_prob": round(new_prob, 4),
                    "days": round(days_since_update, 2),
                })

        return decayed

    def prune_dormant(self, max_age_days: int = 30) -> int:
        """清理 dormant 超过 max_age_days 的信念。"""
        now = time.time()
        removed = 0
        for bid in list(self._beliefs.keys()):
            b = self._beliefs[bid]
            if b.probability <= self.DECAY_FLOOR:
                age_days = (now - b.last_updated) / 86400.0
                if age_days > max_age_days:
                    del self._beliefs[bid]
                    removed += 1
        return removed

    # ── Query ─────────────────────────────────────────────────────────────

    def query(
        self,
        dimension: Optional[BeliefDimension] = None,
        quadrant: Optional[BeliefQuadrant] = None,
        min_probability: float = 0.0,
        min_strength: float = 0.0,
        limit: int = 50,
    ) -> list[Belief]:
        """按条件检索信念。"""
        results = []
        for b in self._beliefs.values():
            if dimension and b.dimension != dimension:
                continue
            if quadrant and b.quadrant != quadrant:
                continue
            if b.probability < min_probability:
                continue
            if b.strength < min_strength:
                continue
            results.append(b)

        results.sort(key=lambda b: b.strength, reverse=True)
        return results[:limit]

    def get_strongest(self, n: int = 10, dimension: Optional[BeliefDimension] = None) -> list[Belief]:
        """获取最强的 N 条信念。"""
        return self.query(dimension=dimension, min_strength=0.1, limit=n)

    def get_convictions(self, dimension: Optional[BeliefDimension] = None) -> list[Belief]:
        """获取所有确信信念。"""
        return self.query(dimension=dimension, quadrant=BeliefQuadrant.CONVICTION)

    def find_by_statement(self, statement: str) -> Optional[Belief]:
        """精确匹配信念（用于合并检测）。"""
        for b in self._beliefs.values():
            if b.statement.strip().lower() == statement.strip().lower():
                return b
        return None

    # ── Merge ─────────────────────────────────────────────────────────────

    def merge_beliefs(self, belief_id_a: str, belief_id_b: str) -> Optional[Belief]:
        """合并两个相同 statement 的信念。

        规则:
            1. 合并 evidence_chain
            2. 加权平均 probability (按 evidence_count 加权)
            3. 保留最早的 created_at
        """
        a = self._beliefs.get(belief_id_a)
        b = self._beliefs.get(belief_id_b)
        if not a or not b or a.statement.strip().lower() != b.statement.strip().lower():
            return None

        # 合并证据
        a.evidence_chain.extend(b.evidence_chain)

        # 加权平均
        total_evidence = a.evidence_count + b.evidence_count
        if total_evidence > 0:
            a.probability = (a.probability * a.evidence_count + b.probability * b.evidence_count) / total_evidence

        a.created_at = min(a.created_at, b.created_at)
        a.last_updated = time.time()

        # 移除 b
        del self._beliefs[belief_id_b]
        self._compute_strength(a)
        self._log("beliefs_merged", {
            "survivor": belief_id_a,
            "merged": belief_id_b,
            "final_prob": round(a.probability, 4),
        })
        return a

    # ── Stats ─────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        beliefs = list(self._beliefs.values())
        by_dimension = {}
        by_quadrant = {}
        for b in beliefs:
            d = b.dimension.value
            q = b.quadrant.value
            by_dimension[d] = by_dimension.get(d, 0) + 1
            by_quadrant[q] = by_quadrant.get(q, 0) + 1

        return {
            "total_beliefs": len(beliefs),
            "by_dimension": by_dimension,
            "by_quadrant": by_quadrant,
            "avg_probability": round(sum(b.probability for b in beliefs) / max(len(beliefs), 1), 4),
            "conviction_count": sum(1 for b in beliefs if b.quadrant == BeliefQuadrant.CONVICTION),
            "dormant_count": sum(1 for b in beliefs if b.probability <= self.DECAY_FLOOR),
        }

    def drain_events(self) -> list[dict]:
        events = list(self._event_log)
        self._event_log.clear()
        return events

    # ── Internal ──────────────────────────────────────────────────────────

    def _compute_strength(self, belief: Belief):
        """strength = prob × (1 + evidence_count × 0.1)。"""
        belief.strength = belief.probability * (1.0 + belief.evidence_count * 0.1)

    def _garbage_collect(self):
        """超出 MAX_BELIEFS 时淘汰最弱的。"""
        if len(self._beliefs) >= self.MAX_BELIEFS:
            sorted_beliefs = sorted(
                self._beliefs.values(),
                key=lambda b: b.strength,
            )
            to_remove = sorted_beliefs[: len(sorted_beliefs) - self.MAX_BELIEFS + 10]
            for b in to_remove:
                del self._beliefs[b.belief_id]
            self._log("gc", {"removed": len(to_remove)})

    def _log(self, event: str, data: dict):
        self._event_log.append({"event": event, "timestamp": time.time(), **data})
