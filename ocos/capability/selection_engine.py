"""Phase 25-C: Capability Selection Engine。

Freeze §4.4 #5 — 基于 Knowledge Graph + Experience Memory，
给定任务类型和所需能力，返回排序后的 Provider 列表。

决策公式:
  score = kg_score × 0.3 + exp_score × 0.3 + constraints_bonus × 0.2 + recency × 0.2
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocos.logging import get_logger

from .knowledge_graph import KnowledgeGraph
from .experience_memory import CapabilityExperienceMemory

logger = get_logger(__name__)


@dataclass
class SelectionConfig:
    """Selection 权重配置."""
    kg_weight: float = 0.3       # Knowledge Graph 排名权重
    exp_weight: float = 0.3       # Experience Memory 排名权重
    constraints_weight: float = 0.2  # Protocol/资源限制 兼容度
    recency_weight: float = 0.2   # 最近成功率
    fallback_threshold: float = 0.1  # 低于此分数不推荐
    max_results: int = 5


@dataclass
class SelectionResult:
    """Provider 选择结果."""
    provider_id: str
    score: float
    kg_rank: int  # 在 KG 中的排名 (1-based)
    exp_rank: int  # 在 Experience 中的排名 (1-based)
    success_rate: float
    avg_quality: float
    avg_satisfaction: float


@dataclass
class SelectionEngine:
    """能力选择引擎（Freeze §4.4 #5）.

    集成 Knowledge Graph + Experience Memory，为任务选择最优 Provider。
    """

    kg: KnowledgeGraph = field(default_factory=KnowledgeGraph)
    experience: CapabilityExperienceMemory = field(default_factory=CapabilityExperienceMemory)
    config: SelectionConfig = field(default_factory=SelectionConfig)

    # ── main API ───────────────────────────────────────────────────────────

    def select(self, task_type: str, capability_id: str | None = None,
               preferred_protocol: str | None = None) -> list[SelectionResult]:
        """给定任务，返回排序后的 Provider 选择列表。

        Args:
            task_type: 任务类型（如 "code_generation", "document_creation"）
            capability_id: 所需具体能力 ID（如不指定，从 task_type 推导）
            preferred_protocol: 优先协议（如 "subprocess", "http"）

        Returns:
            按总分降序排列的 SelectionResult 列表
        """
        # Step 1: 确定目标 capabilities
        if capability_id:
            cap = self.kg.get_capability(capability_id)
            if cap is None:
                return []
            cap_ids = [capability_id]
        else:
            # 从 task_type 推导
            matching = self.kg.query_by_task_type(task_type)
            cap_ids = [c.capability_id for c in matching]
            if not cap_ids:
                return []

        # Step 2: 收集所有 provider 评分
        kg_rankings: dict[str, int] = {}
        exp_rankings: dict[str, int] = {}
        provider_scores: dict[str, dict[str, Any]] = {}

        for cid in cap_ids:
            # KG-based ranking
            kg_ranks = self.kg.rank_providers(cid, top_n=100)
            for rank, r in enumerate(kg_ranks, 1):
                pid = r["provider_id"]
                kg_rankings[pid] = min(rank, kg_rankings.get(pid, 999))

            # Experience-based ranking
            exp_ranks = self.experience.rank_providers(cid, top_n=100)
            for rank, r in enumerate(exp_ranks, 1):
                pid = r["provider_id"]
                exp_rankings[pid] = min(rank, exp_rankings.get(pid, 999))
                if pid not in provider_scores:
                    provider_scores[pid] = r

        # Step 3: 综合打分
        all_pids = set(kg_rankings) | set(exp_rankings)
        if not all_pids:
            return []

        results: list[SelectionResult] = []
        max_kg_rank = max(kg_rankings.values()) if kg_rankings else 1
        max_exp_rank = max(exp_rankings.values()) if exp_rankings else 1

        for pid in all_pids:
            kg_norm = 1.0 - ((kg_rankings.get(pid, max_kg_rank + 1) - 1) / max(max_kg_rank, 1))
            exp_norm = 1.0 - ((exp_rankings.get(pid, max_exp_rank + 1) - 1) / max(max_exp_rank, 1))
            exp_data = provider_scores.get(pid, {})

            # Protocol constraint bonus
            protocol_bonus = 0.0
            if preferred_protocol:
                provider = self.kg.get_provider(pid)
                if provider and provider.protocol == preferred_protocol:
                    protocol_bonus = 0.5

            constraints_score = protocol_bonus

            # Recency bonus (reward providers with recent successes)
            recency = exp_data.get("success_rate", 0.0)

            score = (
                kg_norm * self.config.kg_weight +
                exp_norm * self.config.exp_weight +
                constraints_score * self.config.constraints_weight +
                recency * self.config.recency_weight
            )

            if score >= self.config.fallback_threshold:
                results.append(SelectionResult(
                    provider_id=pid,
                    score=round(score, 4),
                    kg_rank=kg_rankings.get(pid, max_kg_rank + 1),
                    exp_rank=exp_rankings.get(pid, max_exp_rank + 1),
                    success_rate=exp_data.get("success_rate", 0.0),
                    avg_quality=exp_data.get("avg_quality", 0.0),
                    avg_satisfaction=exp_data.get("avg_satisfaction", 0.0),
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:self.config.max_results]

    def select_top(self, task_type: str, capability_id: str | None = None,
                   preferred_protocol: str | None = None) -> SelectionResult | None:
        """返回最佳 Provider 或 None."""
        results = self.select(task_type, capability_id, preferred_protocol)
        return results[0] if results else None

    # ── lifecycle ───────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """初始化 Experience Memory 连接."""
        self.experience.connect()

    def shutdown(self) -> None:
        """关闭资源."""
        self.experience.close()
