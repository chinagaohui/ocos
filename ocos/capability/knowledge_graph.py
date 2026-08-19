"""Phase 25-A: Capability Knowledge Graph。

Freeze §4.4.2 定义：
  - CapabilityNode: 能力本身
  - ProviderNode: 能力提供者
  - ExperienceNode: 历史经验
  - Edge types: PROVIDES / INSTANCE_OF / PROVIDED_BY / REQUIRES

查询接口:
  - query_by_task_type(task_type)
  - rank_providers(capability_id, top_n=5)
  - query_by_capability(capability_id)
  - dependency_chain(capability_id)
"""
from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    pass


# ── Edge Types ────────────────────────────────────────────────────────────────


class EdgeType(enum.Enum):
    """Knowledge Graph 边类型（Freeze §4.4.2）."""
    PROVIDES = "provides"        # ProviderNode → CapabilityNode
    INSTANCE_OF = "instance_of"  # ExperienceNode → CapabilityNode
    PROVIDED_BY = "provided_by"  # ExperienceNode → ProviderNode
    REQUIRES = "requires"        # CapabilityNode → CapabilityNode


# ── Resource Limits ───────────────────────────────────────────────────────────


@dataclass
class ResourceLimits:
    """Provider 资源限制."""
    max_concurrent: int = 1
    max_runtime_ms: int = 300_000
    token_budget: int = 0  # 0 = unlimited


# ── Nodes ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CapabilityNode:
    """能力节点（Freeze §4.4.2）."""
    capability_id: str
    domain: str
    actions: tuple[str, ...] = ()
    input_types: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class ProviderNode:
    """能力提供者（Freeze §4.4.2）."""
    provider_id: str
    capabilities: tuple[str, ...]  # CapabilityNode IDs
    protocol: str  # "subprocess", "http", "mcp"
    auth_required: bool = False
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)


@dataclass(frozen=True)
class ExperienceNode:
    """历史经验节点（Freeze §4.4.2）."""
    experience_id: str
    task_type: str
    capability_id: str
    provider_id: str
    outcome: str  # "success", "failure", "partial"
    quality_score: float  # [0, 1]
    duration_ms: int
    user_satisfaction: float  # [0, 1]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not (0.0 <= self.quality_score <= 1.0):
            raise ValueError(f"quality_score must be [0, 1], got {self.quality_score}")
        if not (0.0 <= self.user_satisfaction <= 1.0):
            raise ValueError(f"user_satisfaction must be [0, 1], got {self.user_satisfaction}")

    @property
    def is_success(self) -> bool:
        return self.outcome == "success"


# ── KnowledgeGraph ─────────────────────────────────────────────────────────────


@dataclass
class KnowledgeGraph:
    """能力知识图谱（Freeze §4.4.2 #3）.

    平面邻接表实现，三类节点 + 四种边类型。
    """

    # Node storage
    _capabilities: dict[str, CapabilityNode] = field(default_factory=dict)
    _providers: dict[str, ProviderNode] = field(default_factory=dict)
    _experiences: dict[str, ExperienceNode] = field(default_factory=dict)

    # Edge storage: {source_id: [(edge_type, target_id), ...]}
    _edges_out: dict[str, list[tuple[EdgeType, str]]] = field(default_factory=dict)

    # ── node management ─────────────────────────────────────────────────

    def add_capability(self, node: CapabilityNode) -> None:
        self._capabilities[node.capability_id] = node

    def add_provider(self, node: ProviderNode) -> None:
        self._providers[node.provider_id] = node

    def add_experience(self, node: ExperienceNode) -> None:
        self._experiences[node.experience_id] = node

    def remove_capability(self, capability_id: str) -> None:
        del self._capabilities[capability_id]
        self._edges_out.pop(capability_id, None)

    def remove_provider(self, provider_id: str) -> None:
        del self._providers[provider_id]
        self._edges_out.pop(provider_id, None)

    def get_capability(self, capability_id: str) -> CapabilityNode | None:
        return self._capabilities.get(capability_id)

    def get_provider(self, provider_id: str) -> ProviderNode | None:
        return self._providers.get(provider_id)

    @property
    def capability_count(self) -> int:
        return len(self._capabilities)

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    @property
    def experience_count(self) -> int:
        return len(self._experiences)

    # ── edge management ─────────────────────────────────────────────────

    def add_edge(self, source_id: str, edge_type: EdgeType, target_id: str) -> None:
        """添加一条有向边."""
        if source_id not in self._edges_out:
            self._edges_out[source_id] = []
        self._edges_out[source_id].append((edge_type, target_id))

    def get_edges(self, source_id: str) -> list[tuple[EdgeType, str]]:
        """获取某个节点的所有出边."""
        return self._edges_out.get(source_id, [])

    def get_edges_by_type(self, source_id: str, edge_type: EdgeType) -> list[str]:
        """获取某个节点指定类型的出边目标."""
        return [t for e, t in self.get_edges(source_id) if e == edge_type]

    def get_incoming(self, target_id: str, edge_type: EdgeType | None = None) -> list[str]:
        """反向查询：谁指向我？"""
        result = []
        for src, edges in self._edges_out.items():
            for e, tgt in edges:
                if tgt == target_id and (edge_type is None or e == edge_type):
                    result.append(src)
        return result

    # ── query interfaces (25a2) ─────────────────────────────────────────

    def query_by_task_type(self, task_type: str) -> list[CapabilityNode]:
        """根据任务类型查询相关能力（匹配 domain / actions）."""
        results = []
        for cap in self._capabilities.values():
            domain_match = task_type.lower() in cap.domain.lower()
            action_match = any(task_type.lower() in a.lower() for a in cap.actions)
            if domain_match or action_match:
                results.append(cap)
        return results

    def query_by_capability(self, capability_id: str) -> dict[str, Any]:
        """查询能力的完整信息：节点 + Provider + 经验."""
        cap = self._capabilities.get(capability_id)
        if cap is None:
            return {"error": f"capability '{capability_id}' not found"}

        # Provider→Capability 是 PROVIDES 边 → 反向查 incoming
        provider_ids = self.get_incoming(capability_id, EdgeType.PROVIDES)
        providers = [self._providers[pid] for pid in provider_ids if pid in self._providers]

        # Experience→Capability 是 INSTANCE_OF 边 → 反向查 incoming
        exp_ids = self.get_incoming(capability_id, EdgeType.INSTANCE_OF)
        experiences = [self._experiences[eid] for eid in exp_ids if eid in self._experiences]

        return {"capability": cap, "providers": providers, "experiences": experiences}

    def rank_providers(self, capability_id: str, top_n: int = 5) -> list[dict[str, Any]]:
        """按历史表现排序 Provider（Freeze §4.4.2 #2）.

        排序权重：quality_score × 0.4 + user_satisfaction × 0.4 + (1 - duration_norm) × 0.2
        """
        experiences = [
            self._experiences[eid]
            for eid in self.get_incoming(capability_id, EdgeType.INSTANCE_OF)
            if eid in self._experiences
        ]
        if not experiences:
            # Fallback: 从 Provider 中查
            provider_ids = self.get_incoming(capability_id, EdgeType.PROVIDES)
            return [
                {"provider_id": pid, "score": 0.0, "experience_count": 0}
                for pid in provider_ids[:top_n]
            ]

        # Group by provider
        by_provider: dict[str, list[ExperienceNode]] = defaultdict(list)
        for exp in experiences:
            by_provider[exp.provider_id].append(exp)

        # Score each provider
        scores: list[dict[str, Any]] = []
        all_durations = [e.duration_ms for e in experiences]
        max_dur = max(all_durations) if all_durations else 1

        for pid, exps in by_provider.items():
            avg_q = sum(e.quality_score for e in exps) / len(exps)
            avg_s = sum(e.user_satisfaction for e in exps) / len(exps)
            avg_dur = sum(e.duration_ms for e in exps) / len(exps)
            duration_norm = avg_dur / max_dur if max_dur > 0 else 1.0
            success_rate = sum(1 for e in exps if e.is_success) / len(exps)

            score = avg_q * 0.4 + avg_s * 0.4 + (1 - duration_norm) * 0.2
            # Penalize low success rate
            score *= success_rate

            scores.append({
                "provider_id": pid,
                "score": round(score, 4),
                "experience_count": len(exps),
                "success_rate": round(success_rate, 3),
                "avg_quality": round(avg_q, 3),
                "avg_satisfaction": round(avg_s, 3),
                "avg_duration_ms": int(avg_dur),
            })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_n]

    def dependency_chain(self, capability_id: str, visited: set[str] | None = None) -> list[str]:
        """计算能力依赖链（REQUIRES 边 BFS）."""
        if visited is None:
            visited = set()
        if capability_id in visited:
            return []
        visited.add(capability_id)

        chain = [capability_id]
        for dep_id in self.get_edges_by_type(capability_id, EdgeType.REQUIRES):
            chain.extend(self.dependency_chain(dep_id, visited))
        return chain

    # ── clear ─────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空所有节点和边."""
        self._capabilities.clear()
        self._providers.clear()
        self._experiences.clear()
        self._edges_out.clear()
