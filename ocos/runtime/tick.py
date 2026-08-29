"""Phase 39.1: Tick Model — OCOS Runtime 最小时间单元。

对应 RUNTIME_ABI §Tick Model。39.1 不执行 Tick Pipeline 阶段，
只建立不可变容器。

Future (39.2+): 扩展 TickStage — PERCEIVE/EVALUATE/MAINTAIN/DECIDE/ACT/LEARN/CHECKPOINT。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class Tick:
    """OCOS Runtime 不可变心跳帧。

    每个 tick 是一个原子时间切片。39.1 只记录：
        - tick_id:  单调递增序号
        - timestamp: 创建时刻 (UTC)
        - state:     Runtime 状态快照
        - checkpoint_id: 最近一次 checkpoint 标识

    约束:
        - tick_id MUST be monotonically increasing
        - checkpoint_id 可以为 None (尚未生成 checkpoint)
    """

    tick_id: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    state: str = "RUNNING"
    checkpoint_id: str | None = None

    def __post_init__(self):
        if self.tick_id < 1:
            raise ValueError(f"tick_id must be >= 1, got {self.tick_id}")


def tick_id_generator(start: int = 1):
    """生成单调递增的 tick ID。"""
    current = start
    while True:
        yield current
        current += 1
