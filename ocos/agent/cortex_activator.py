"""CortexActivator — 皮层激活管理。

控制认知皮层的激活/休眠/紧急激活模式。
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional


class CortexMode(Enum):
    """皮层激活模式。"""
    ACTIVE = auto()        # 正常运行
    SLEEPING = auto()      # 休眠（低能耗）
    EMERGENCY = auto()     # 紧急激活（重置）
    BLOCKED = auto()       # 被 MetaController 熔断


class CortexActivator:
    """皮层激活器。

    管理认知皮层的三种运行模式。
    Blocked 时提供紧急激活恢复。
    """

    def __init__(self):
        self._mode: CortexMode = CortexMode.ACTIVE
        self._block_count: int = 0
        self._last_emergency: float = 0.0

    @property
    def mode(self) -> CortexMode:
        return self._mode

    def activate(self) -> None:
        """激活皮层。"""
        self._mode = CortexMode.ACTIVE

    def sleep(self) -> None:
        """休眠皮层。"""
        self._mode = CortexMode.SLEEPING

    def block(self) -> None:
        """熔断皮层。"""
        self._mode = CortexMode.BLOCKED
        self._block_count += 1

    def emergency_activate(self) -> bool:
        """紧急激活（从 BLOCKED 恢复）。

        返回是否允许激活。
        连续阻塞次数决定是否需要外部干预。
        """
        if self._block_count >= 3:
            return False  # 需人工干预

        self._mode = CortexMode.EMERGENCY
        self._last_emergency = __import__("time").time()
        return True

    def recover(self) -> bool:
        """从 EMERGENCY 恢复到 ACTIVE。

        在 ACTIVE/EMERGENCY 调用 resume()，从 BLOCKED/SLEEP 调用 reset()。
        """
        if self._mode == CortexMode.EMERGENCY:
            self._mode = CortexMode.ACTIVE
            return True
        return False

    def is_active(self) -> bool:
        return self._mode == CortexMode.ACTIVE

    def is_blocked(self) -> bool:
        return self._mode == CortexMode.BLOCKED

    def needs_intervention(self) -> bool:
        """是否需要外部干预（连续阻塞 3 次以上）。"""
        return self._block_count >= 3

    def get_status(self) -> dict:
        return {
            "mode": self._mode.name,
            "block_count": self._block_count,
            "is_active": self.is_active(),
            "needs_intervention": self._block_count >= 3,
        }
