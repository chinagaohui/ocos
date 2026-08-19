"""LocalAttentionState — Agent 内部注意力状态记录。

Phase 35 重定义（Freeze 附录A，A 层）:
  本模块仅记录 Agent 自身的局部注意力状态。不持有 OCOS 全局注意力决策权。

  允许:
    ✅ focus duration / fatigue / local context

  禁止:
    ❌ 决定 OCOS 系统级焦点
    ❌ 修改 OCOS Focus
    ❌ 触发执行

  全局决策权: CognitiveAttentionController（C 层）
  评分: AttentionScoringEngine（B 层）

旧名: Attention（降权为 LocalAttentionState）
"""

from __future__ import annotations

import time
import threading
from enum import Enum
from typing import Any, Optional

# ═══════════════════════════════════════════════════════════════════════
# Phase 35: 此模块降权。仅保留 Agent 自身状态记录。
# 全局注意力由 CognitiveAttentionController 统一决策。
# ═══════════════════════════════════════════════════════════════════════


class FocusMode(Enum):
    FOCUSED = "focused"           # 专注单一目标
    SCANNING = "scanning"         # 扫描环境
    IDLE = "idle"                 # 空闲（低能耗）
    DISTRIBUTED = "distributed"   # 分心（多任务）


class Attention:
    """Agent 局部注意力状态（Phase 35 降权为 A 层）。

    仅管理 Agent 自身的疲劳和焦点状态。不参与 OCOS 全局注意力决策。
    全局决策由 CognitiveAttentionController 独立执行。
    """

    FATIGUE_RATE: dict[FocusMode, float] = {
        FocusMode.FOCUSED: 0.01,       # 专注模式疲劳累积最快
        FocusMode.SCANNING: 0.003,     # 扫描模式疲劳较慢
        FocusMode.IDLE: 0.001,         # 空闲几乎无疲劳
        FocusMode.DISTRIBUTED: 0.008,  # 多任务也有疲劳
    }

    def __init__(self, fatigue_max: float = 1.0):
        self._fatigue_max = fatigue_max
        self._fatigue: float = 0.0
        self._mode: FocusMode = FocusMode.IDLE
        self._focus_item: Optional[dict[str, Any]] = None
        self._lock = threading.Lock()
        self._last_tick: float = time.time()

    def focus(self, item_id: str, item_type: str, priority: float) -> None:
        """聚焦到某个项目。"""
        with self._lock:
            self._focus_item = {
                "id": item_id,
                "type": item_type,
                "priority": priority,
                "since": time.time(),
            }
            # 聚焦时自动进入 FOCUSED 模式
            self._mode = FocusMode.FOCUSED

    def unfocus(self, item_id: str) -> None:
        """取消聚焦。"""
        with self._lock:
            if self._focus_item and self._focus_item["id"] == item_id:
                self._focus_item = None
                self._mode = FocusMode.IDLE

    def switch_to(self, item_id: str, priority: float) -> bool:
        """切换到新焦点。仅当新优先级 > 当前优先级时成功。"""
        with self._lock:
            if self._focus_item and priority <= self._focus_item.get("priority", 0):
                return False
            self._focus_item = {
                "id": item_id,
                "type": "unknown",
                "priority": priority,
                "since": time.time(),
            }
            self._mode = FocusMode.FOCUSED
            return True

    @property
    def mode(self) -> FocusMode:
        return self._mode

    @mode.setter
    def mode(self, value: FocusMode) -> None:
        with self._lock:
            self._mode = value

    @property
    def current_focus(self) -> Optional[str]:
        if self._focus_item:
            return self._focus_item["id"]
        return None

    @property
    def fatigue(self) -> float:
        return self._fatigue

    def tick(self, seconds: float | None = None) -> None:
        """按时间更新疲劳度。"""
        now = time.time()
        if seconds is None:
            seconds = now - self._last_tick
        self._last_tick = now

        with self._lock:
            rate = self.FATIGUE_RATE.get(self._mode, 0.01)
            self._fatigue = min(self._fatigue + rate * seconds, self._fatigue_max)

    def needs_sleep(self) -> bool:
        """是否建议进入 SLEEP（疲劳 > 0.9）。

        Phase 35: 此方法仅反映 Agent 局部状态。
        全局疲劳决策由 CognitiveAttentionController.tick() 统一管理。
        """
        return self._fatigue > 0.9

    def local_tick(self, seconds: float) -> None:
        """Agent 局部 tick — 仅更新 Agent 自身疲劳。

        Phase 35: 此方法不影响 OCOS 全局注意力。
        全局 tick 由 CognitiveAttentionController.tick() 执行。
        """
        now = time.time()
        seconds = seconds or (now - self._last_tick)
        self._last_tick = now
        with self._lock:
            rate = self.FATIGUE_RATE.get(self._mode, 0.01)
            self._fatigue = min(self._fatigue + rate * seconds, self._fatigue_max)

    def reset(self) -> None:
        """重置疲劳（SLEEP 后调用）。"""
        with self._lock:
            self._fatigue = 0.0
            self._mode = FocusMode.IDLE


# Phase 35 aliases for clarity
LocalAttentionState = Attention
"""Phase 35 别名: 明确此模块是局部状态而非全局控制器。"""
