"""Phase 41: Wisdom Types — 个人智慧类型定义。

三层严格分离:
    Layer 1 — Memory:         "发生过什么" (事件存储)
    Layer 2 — ExperienceProfile: "呈现什么统计规律" (Phase 40)
    Layer 3 — Personal Wisdom:   "未来应该如何判断" (Phase 41)

区分:
    Knowledge = "世界是什么"        (事实)
    Pattern   = "什么规律重复出现"  (统计)
    Wisdom    = "这个经验值得遵循"  (判断)

Wisdom 生命周期状态机:
    CANDIDATE → VALIDATING → CONFIRMED → ACTIVE → DEPRECATED

边界:
    PM41-01: Memory ≠ Wisdom       (存储不是理解)
    PM41-02: Pattern ≠ Principle   (统计不是必然)
    PM41-03: Wisdom ≠ Command      (智慧不能直接控制行为)
    PM41-04: Wisdom ≠ Identity     (经验不能改变主体)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
# 智慧状态机
# ═══════════════════════════════════════════════════════════════════════════════


class WisdomState(Enum):
    """智慧条目生命周期状态。

    CANDIDATE → VALIDATING → CONFIRMED → ACTIVE → DEPRECATED
    """

    CANDIDATE = "candidate"
    """候选智慧 — 从 Pattern 中提取，尚未验证。"""

    VALIDATING = "validating"
    """验证中 — 正在检查证据充分性和反例。"""

    CONFIRMED = "confirmed"
    """已确认 — 通过验证，等待应用。"""

    ACTIVE = "active"
    """活跃 — 当前可用的智慧。"""

    DEPRECATED = "deprecated"
    """已废弃 — 被新证据推翻或不再适用。"""

    @property
    def is_usable(self) -> bool:
        return self in (WisdomState.CONFIRMED, WisdomState.ACTIVE)

    @property
    def is_mutable(self) -> bool:
        """仍可修改的状态。"""
        return self in (WisdomState.CANDIDATE, WisdomState.VALIDATING)


# ═══════════════════════════════════════════════════════════════════════════════
# 适用范围
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class WisdomScope:
    """智慧的适用范围 — 防止过度泛化。

    例如:
        "接口冻结优先" 适用于 architecture_design, 不适用于 quick_script
    """

    domains: tuple[str, ...] = ()
    """适用领域。空 = 通用。"""

    conditions: tuple[str, ...] = ()
    """适用条件。例如 ("large_system", "multi_team")"""

    exclusions: tuple[str, ...] = ()
    """排除条件。例如 ("prototype", "throwaway_code")"""

    user_scope: str = "current_user"
    """适用用户范围: current_user | all_users | specific"""

    @property
    def is_universal(self) -> bool:
        return not self.domains and not self.conditions and not self.exclusions

    def applies_to(self, domain: str, conditions: tuple[str, ...] = ()) -> bool:
        """检查此智慧是否适用于给定场景。"""
        # 硬排除
        for exc in self.exclusions:
            if exc in conditions:
                return False
        # 域匹配
        if self.domains and domain not in self.domains:
            return False
        # 条件匹配（满足任一即可）
        if self.conditions:
            if not any(c in conditions for c in self.conditions):
                return False
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# 证据条目
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class WisdomEvidence:
    """支持（或反对）一条智慧的单个证据。"""

    evidence_id: str
    source_type: str         # "episode" | "pattern" | "outcome"
    source_id: str           # Memory entry ID / Pattern ID
    supports: bool           # True = 支持, False = 反例
    strength: float          # [0, 1] 证据强度
    tick_id: int
    note: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 智慧条目
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WisdomItem:
    """一条个人智慧。

    不是通用知识，而是针对特定用户/场景的经验判断。

    例如:
        principle: "大型系统设计优先冻结接口边界"
        scope: domains=("architecture_design",), conditions=("large_system",)
        evidence: 5 次成功的项目, 2 次失败的反例佐证
    """

    wisdom_id: str
    """唯一标识。"""

    principle: str
    """智慧表述 — 简短、可执行的判断原则。"""

    state: WisdomState = WisdomState.CANDIDATE

    # ── 来源 ──

    source_patterns: tuple[str, ...] = ()
    """来源 ExperiencePattern IDs。"""

    # ── 证据 ──

    evidence: list[WisdomEvidence] = field(default_factory=list)
    """支持/反对证据列表。"""

    @property
    def supporting_evidence(self) -> list[WisdomEvidence]:
        return [e for e in self.evidence if e.supports]

    @property
    def counter_evidence(self) -> list[WisdomEvidence]:
        return [e for e in self.evidence if not e.supports]

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def support_count(self) -> int:
        return len(self.supporting_evidence)

    @property
    def counter_count(self) -> int:
        return len(self.counter_evidence)

    @property
    def evidence_strength(self) -> float:
        """整体证据强度 [0, 1]。"""
        if not self.evidence:
            return 0.0
        total = sum(e.strength for e in self.supporting_evidence)
        against = sum(e.strength for e in self.counter_evidence)
        if total + against == 0:
            return 0.0
        return total / (total + against)

    # ── 适用范围 ──

    scope: WisdomScope = field(default_factory=WisdomScope)

    # ── 元信息 ──

    confidence: float = 0.0
    """置信度 [0, 1]。由 Validator 计算。"""

    created_tick: int = 0
    confirmed_tick: int = 0
    deprecated_tick: int = 0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── 状态转换 ──

    def promote_to(self, new_state: WisdomState, tick_id: int) -> bool:
        """合法状态转换。"""
        allowed = {
            WisdomState.CANDIDATE: {WisdomState.VALIDATING, WisdomState.DEPRECATED},
            WisdomState.VALIDATING: {WisdomState.CONFIRMED, WisdomState.CANDIDATE, WisdomState.DEPRECATED},
            WisdomState.CONFIRMED: {WisdomState.ACTIVE, WisdomState.DEPRECATED},
            WisdomState.ACTIVE: {WisdomState.DEPRECATED},
            WisdomState.DEPRECATED: set(),  # 终点，不可逆
        }

        if new_state not in allowed.get(self.state, set()):
            return False

        self.state = new_state
        if new_state == WisdomState.CONFIRMED:
            self.confirmed_tick = tick_id
        elif new_state == WisdomState.DEPRECATED:
            self.deprecated_tick = tick_id
        self.updated_at = datetime.now(timezone.utc)
        return True

    # ── 查询 ──

    def applies_to(self, domain: str, conditions: tuple[str, ...] = ()) -> bool:
        """在给定场景下是否适用。"""
        if not self.state.is_usable:
            return False
        return self.scope.applies_to(domain, conditions)

    @property
    def summary(self) -> str:
        return (
            f"Wisdom({self.wisdom_id}): [{self.state.value}] "
            f"\"{self.principle[:60]}\" "
            f"evidence={self.support_count}s/{self.counter_count}c "
            f"conf={self.confidence:.2f}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 集合类型
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class WisdomCollection:
    """用户特定的智慧集合。

    每个用户有独立的 WisdomCollection。
    相同事件在不同用户身上形成不同的智慧。
    """

    user_id: str
    items: dict[str, WisdomItem] = field(default_factory=dict)

    @property
    def active(self) -> list[WisdomItem]:
        return [w for w in self.items.values() if w.state == WisdomState.ACTIVE]

    @property
    def confirmed(self) -> list[WisdomItem]:
        return [w for w in self.items.values()
                if w.state in (WisdomState.CONFIRMED, WisdomState.ACTIVE)]

    @property
    def candidates(self) -> list[WisdomItem]:
        return [w for w in self.items.values() if w.state == WisdomState.CANDIDATE]

    def add(self, item: WisdomItem) -> None:
        self.items[item.wisdom_id] = item

    def get(self, wisdom_id: str) -> Optional[WisdomItem]:
        return self.items.get(wisdom_id)

    def applicable_to(self, domain: str, conditions: tuple[str, ...] = ()) -> list[WisdomItem]:
        """查找适用于特定场景的已确认智慧。"""
        return [w for w in self.confirmed if w.applies_to(domain, conditions)]


# ── 禁止导出 ──

__all__ = [
    "WisdomState",
    "WisdomScope",
    "WisdomEvidence",
    "WisdomItem",
    "WisdomCollection",
]
