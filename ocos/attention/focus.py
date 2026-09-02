"""Phase O: AttentionFocus — 注意力焦点管理器。

整合 AttentionEngine（评分）+ Homeostasis（驱力）
形成统一的焦点决策层，决定系统当前应该关注什么。

职责:
  - 接收 Observation 并计算注意力度量
  - 结合 Homeostasis 驱力信号调整焦点权重
  - 输出当前 FocusState（当前关注的主题/目标）
  - 支持焦点转移和保持机制
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional

from ocos.runtime.attention_engine import (
    AttentionEngine,
    AttentionScore,
    ContentAnalyzer,
    DefaultContentAnalyzer,
)
from ocos.capability.homeostasis import DriveType, DriveSignal, RegulateResult

logger = logging.getLogger(__name__)


class FocusType(Enum):
    """焦点类型。"""
    EXTERNAL = auto()      # 外部输入驱动（用户消息、新观察）
    INTERNAL = auto()      # 内生驱动（Homeostasis 驱力）
    GOAL_DRIVEN = auto()   # 目标驱动（当前活跃目标）
    IDLE = auto()          # 空闲/待机


@dataclass(frozen=True)
class FocusState:
    """当前注意力焦点状态。"""
    focus_type: FocusType
    focus_target: str                    # 当前关注主题
    focus_score: float                   # 0.0-1.0 强度
    attention_scores: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (novelty, relevance, urgency)
    active_drives: tuple[str, ...] = ()  # 当前激活的驱力
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def is_focused(self) -> bool:
        return self.focus_score >= 0.3

    @property
    def is_idle(self) -> bool:
        return self.focus_type == FocusType.IDLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "focus_type": self.focus_type.name,
            "focus_target": self.focus_target,
            "focus_score": self.focus_score,
            "attention_scores": list(self.attention_scores),
            "active_drives": list(self.active_drives),
            "timestamp": self.timestamp,
        }


class AttentionFocus:
    """注意力焦点管理器 — Phase O。

    整合:
    - AttentionEngine: 观察评分
    - Homeostasis 驱力: 内生驱动
    - 焦点决策: 输出当前 FocusState
    """

    def __init__(
        self,
        engine: Optional[AttentionEngine] = None,
        novelty_weight: float = 0.3,
        relevance_weight: float = 0.4,
        urgency_weight: float = 0.3,
        focus_threshold: float = 0.3,
        idle_timeout: float = 300.0,
    ) -> None:
        self._engine = engine or AttentionEngine()
        self._novelty_weight = novelty_weight
        self._relevance_weight = relevance_weight
        self._urgency_weight = urgency_weight
        self._focus_threshold = focus_threshold
        self._idle_timeout = idle_timeout

        self._current_focus = FocusState(
            focus_type=FocusType.IDLE,
            focus_target="",
            focus_score=0.0,
        )
        self._last_focus_change = time.time()
        self._observation_history: list[Any] = []
        self._max_history = 100

        # 回调
        self._on_focus_change: Optional[Any] = None
        self._on_new_attention: Optional[Any] = None

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def focus_state(self) -> FocusState:
        return self._current_focus

    @property
    def is_focused(self) -> bool:
        return self._current_focus.is_focused

    @property
    def focus_target(self) -> str:
        return self._current_focus.focus_target

    def process_observation(self, observation: Any) -> FocusState:
        """处理新观察，更新焦点状态。"""
        # 计算注意力分数
        score = self._engine.score(observation, self._observation_history)

        # 更新焦点
        if score.composite >= self._focus_threshold:
            self._update_focus(
                focus_type=FocusType.EXTERNAL,
                focus_target=observation.content[:80] if hasattr(observation, 'content') else str(observation)[:80],
                attention_scores=(
                    score.novelty,
                    score.goal_relevance,
                    score.urgency,
                ),
            )

        # 记录历史
        self._observation_history.append(observation)
        if len(self._observation_history) > self._max_history:
            self._observation_history = self._observation_history[-self._max_history:]

        return self._current_focus

    def update_from_homeostasis(self, regulate_result: RegulateResult) -> FocusState:
        """根据 Homeostasis 结果更新焦点。"""
        drives = regulate_result.drives
        if not drives:
            return self._current_focus

        # 找出最强驱力
        strongest = max(drives, key=lambda d: d.intensity)

        # 映射驱力到焦点类型
        focus_type = self._drive_to_focus_type(strongest.drive)

        # 更新焦点
        self._update_focus(
            focus_type=focus_type,
            target=strongest.drive.value,
            score=strongest.intensity,
            active_drives=tuple(d.drive.value for d in drives),
        )

        return self._current_focus

    def set_focus(self, focus_type: FocusType, target: str, score: float = 1.0) -> FocusState:
        """手动设置焦点（用于外部注入）。"""
        self._update_focus(focus_type, target, score)
        return self._current_focus

    def clear_focus(self) -> FocusState:
        """清除焦点，回到空闲状态。"""
        self._update_focus(FocusType.IDLE, "", 0.0)
        return self._current_focus

    def check_idle(self) -> bool:
        """检查是否进入空闲状态（长时间无焦点）。"""
        if time.time() - self._last_focus_change > self._idle_timeout:
            if self._current_focus.is_focused:
                self.clear_focus()
                return True
        return False

    # ── Hooks ───────────────────────────────────────────────────────────

    def on_focus_change(self, fn: Any) -> "AttentionFocus":
        """注册焦点变化回调。"""
        self._on_focus_change = fn
        return self

    def on_new_attention(self, fn: Any) -> "AttentionFocus":
        """注册新注意力回调 (observation, score)。"""
        self._on_new_attention = fn
        return self

    # ── Internal ────────────────────────────────────────────────────────

    def _update_focus(
        self,
        focus_type: FocusType,
        target: str,
        score: float,
        attention_scores: tuple[float, float, float] = (0.0, 0.0, 0.0),
        active_drives: tuple[str, ...] = (),
    ) -> None:
        """更新焦点状态。"""
        old_focus = self._current_focus
        self._current_focus = FocusState(
            focus_type=focus_type,
            focus_target=target,
            focus_score=score,
            attention_scores=attention_scores,
            active_drives=active_drives,
        )
        self._last_focus_change = time.time()

        # 触发回调
        if self._on_focus_change and old_focus != self._current_focus:
            try:
                self._on_focus_change(old_focus, self._current_focus)
            except Exception as e:
                logger.warning("on_focus_change hook failed: %s", e)

    def _drive_to_focus_type(self, drive: DriveType) -> FocusType:
        """将 DriveType 映射到 FocusType。"""
        mapping = {
            DriveType.EXPLORE: FocusType.INTERNAL,
            DriveType.MASTERY: FocusType.INTERNAL,
            DriveType.CONNECTION: FocusType.INTERNAL,
            DriveType.RESTORE: FocusType.INTERNAL,
            DriveType.REFLECT: FocusType.INTERNAL,
        }
        return mapping.get(drive, FocusType.INTERNAL)


# ── Factory ─────────────────────────────────────────────────────────────

def create_attention_focus(
    novelty_weight: float = 0.3,
    relevance_weight: float = 0.4,
    urgency_weight: float = 0.3,
) -> AttentionFocus:
    """工厂函数：创建 AttentionFocus 实例。"""
    return AttentionFocus(
        novelty_weight=novelty_weight,
        relevance_weight=relevance_weight,
        urgency_weight=urgency_weight,
    )
