"""Phase 23 — Cognitive Cortex 数据模型。

包含:
  - Skill: 认知能力单元（含 fallback_strategy）
  - SkillGraph: 技能图（Kahn 拓扑排序 + 环检测）
  - ProcessGraph: 执行会话
  - SkillExecutionRecord: 单次执行记录

关键设计 (防 Workflow 退化):
  Skill 包含 fallback_strategy — 失败后可以 retry/skip/fallback/abort，
  单个 Skill 失败 ≠ 整个 Process 失败。
"""

from __future__ import annotations

import enum
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


# ── Enums ────────────────────────────────────────────────────────────────────


class SkillStatus(str, enum.Enum):
    """Skill / Process 执行状态。"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


# ── CyclicDependencyError ────────────────────────────────────────────────────


class CyclicDependencyError(Exception):
    """SkillGraph 包含循环依赖时抛出。"""
    def __init__(self, graph_id: str, remaining_nodes: list[str]):
        self.graph_id = graph_id
        self.remaining_nodes = remaining_nodes
        super().__init__(
            f"SkillGraph '{graph_id}' contains cyclic dependency among: {remaining_nodes}"
        )


class UnknownPrerequisiteError(Exception):
    """前置 Skill 不在 SkillGraph 中时抛出。"""
    def __init__(self, skill_id: str, missing_prereq: str):
        self.skill_id = skill_id
        self.missing_prereq = missing_prereq
        super().__init__(
            f"Skill '{skill_id}' has unknown prerequisite: {missing_prereq}"
        )


# ── Skill ────────────────────────────────────────────────────────────────────


@dataclass
class Skill:
    """可组合、可评价、可优化的认知能力单元。

    与 Workflow 的区别:
      - 有 Fallback 策略，失败后可重试/跳过/切换
      - 有 evaluation_method，执行后可评价
      - 有 improvement_history，记录演化过程
      - 有 input_state / output_state schema
    """
    id: str
    name: str
    description: str = ""
    prerequisite: list[str] = field(default_factory=list)
    input_state: dict[str, Any] = field(default_factory=dict)
    output_state: dict[str, Any] = field(default_factory=dict)
    required_capability: str = "reasoning"
    failure_condition: Optional[str] = None
    evaluation_method: Optional[str] = None
    improvement_history: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"

    # ── 认知弹性（防 Workflow 退化）──
    fallback_strategy: str = "abort"  # "abort" | "retry" | "skip" | "fallback:<skill_id>"
    max_retries: int = 0

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self):
        valid_strategies = {"abort", "retry", "skip"}
        if (
            self.fallback_strategy not in valid_strategies
            and not self.fallback_strategy.startswith("fallback:")
        ):
            raise ValueError(
                f"Invalid fallback_strategy: '{self.fallback_strategy}'. "
                f"Must be one of {valid_strategies} or 'fallback:<skill_id>'"
            )


# ── SkillGraph ───────────────────────────────────────────────────────────────


@dataclass
class SkillGraph:
    """技能图 — 认知能力的编排模板。

    通过 Kahn 算法拓扑排序确保障无循环依赖。
    """
    id: str
    name: str
    description: str = ""
    skills: list[Skill] = field(default_factory=list)
    entry_point: Optional[str] = None
    version: str = "1.0.0"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── 内部缓存 ──
    _skill_map: dict[str, Skill] | None = field(default=None, repr=False, init=False)

    def _build_skill_map(self) -> dict[str, Skill]:
        if self._skill_map is None:
            self._skill_map = {s.id: s for s in self.skills}
        return self._skill_map

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self._build_skill_map().get(skill_id)

    def get_dependency_order(self) -> list[str]:
        """Kahn 算法拓扑排序。

        返回 Skill ID 的执行顺序（依赖在前，被依赖在后）。

        Raises:
            UnknownPrerequisiteError: 前置 Skill 不在 SkillGraph 中
            CyclicDependencyError: 存在循环依赖
        """
        skill_map = self._build_skill_map()

        # 构建入度表和邻接表
        in_degree: dict[str, int] = {}
        adj: dict[str, list[str]] = {}
        for skill in self.skills:
            if skill.id not in in_degree:
                in_degree[skill.id] = 0
                adj[skill.id] = []

        for skill in self.skills:
            for prereq in skill.prerequisite:
                if prereq not in skill_map:
                    raise UnknownPrerequisiteError(skill.id, prereq)
                adj[prereq].append(skill.id)
                in_degree[skill.id] = in_degree.get(skill.id, 0) + 1

        # Kahn 算法
        queue = deque(
            node for node in in_degree if in_degree[node] == 0
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 环检测
        if len(order) != len(self.skills):
            remaining = [
                node for node, deg in in_degree.items() if deg > 0
            ]
            raise CyclicDependencyError(self.id, remaining)

        return order

    def has_cycle(self) -> bool:
        """检测是否存在循环依赖（不抛异常）。"""
        try:
            self.get_dependency_order()
            return False
        except CyclicDependencyError:
            return True

    def validate(self) -> list[str]:
        """验证 SkillGraph 完整性，返回违例列表。"""
        violations: list[str] = []

        # 检查空图
        if not self.skills:
            violations.append("SkillGraph has no skills")
            return violations

        # 检查重复 ID
        ids = [s.id for s in self.skills]
        if len(ids) != len(set(ids)):
            violations.append("Duplicate skill IDs found")

        # 检查循环依赖
        if self.has_cycle():
            violations.append("Cyclic dependency detected")

        # 检查 entry_point 有效性
        if self.entry_point and not self.get_skill(self.entry_point):
            violations.append(
                f"entry_point '{self.entry_point}' not found in skills"
            )

        return violations


# ── SkillExecutionRecord ─────────────────────────────────────────────────────


@dataclass
class SkillExecutionRecord:
    """单个 Skill 的一次执行记录。"""
    skill_id: str
    skill_name: str
    status: SkillStatus = SkillStatus.PENDING
    attempt: int = 1
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None


# ── ProcessGraph ─────────────────────────────────────────────────────────────


@dataclass
class ProcessGraph:
    """一次完整的 SkillGraph 执行会话。

    包含执行历史、状态、异步控制信号。
    """
    id: str
    skill_graph_id: str
    session_id: str
    status: SkillStatus = SkillStatus.PENDING
    current_skill_index: int = 0
    execution_history: list[SkillExecutionRecord] = field(default_factory=list)
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None
    total_duration: float = 0.0
    error_log: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def add_record(self, record: SkillExecutionRecord) -> None:
        """添加执行记录。"""
        self.execution_history.append(record)
        self.current_skill_index = len(self.execution_history)
        self.last_update = datetime.now(timezone.utc)

    def last_record(self) -> Optional[SkillExecutionRecord]:
        """最后一条执行记录。"""
        return self.execution_history[-1] if self.execution_history else None

    def failed_count(self) -> int:
        """连续失败计数。"""
        count = 0
        for record in reversed(self.execution_history):
            if record.status == SkillStatus.FAILED:
                count += 1
            else:
                break
        return count

    def repeated_skill_count(self) -> int:
        """末尾同一 Skill 连续执行次数（死循环检测用）。"""
        if not self.execution_history:
            return 0
        last_id = self.execution_history[-1].skill_id
        count = 0
        for record in reversed(self.execution_history):
            if record.skill_id == last_id:
                count += 1
            else:
                break
        return count
