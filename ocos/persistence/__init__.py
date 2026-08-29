"""Phase 51.1: Persistent Cognitive Storage.

OCOS v1.1 核心基础设施 — 让认知智能跨越关机，持续存在。

职责分工(GAP-P3-2 裁决): 本包 = 通用多域快照框架(JSON 落盘,
Phase 51 契约测试锁定, register_provider/take/restore 多域 API);
ocos/snapshot/ = agent 专用快照(SQLite, 生产路径在用,
resurrection_drill 演练依赖)。两套并存、职责不重叠, 不作合并;
统一抽象收敛留待后续阶段, 不在 GAP-P3 范围内。

核心能力:
    - Snapshot: 全系统状态快照 (Runtime/Cognitive/Memory/World)
    - Checkpoint: 增量检查点
    - Recovery: 冷启动恢复 (discover → select → validate → restore)
    - Lifecycle: 完整的生命循环管理

边界:
    PS51-01: Snapshot ≠ Live State
    PS51-02: Restore ≠ Overwrite
    PS51-03: Partial Recovery OK
    PS51-04: Storage Format Stable

典型用法:

    from ocos.persistence import (
        SnapshotManager, RecoveryManager, LifecycleManager,
    )

    sm = SnapshotManager()
    rm = RecoveryManager(snapshot_manager=sm)
    lm = LifecycleManager(snapshot_manager=sm, recovery_manager=rm)

    # 启动
    result = lm.boot()
    print(f"Boot phase: {lm.current_phase}")
    print(f"Recovered at tick {result.tick_at_recovery}")

    # 正常运行
    lm.run(my_tick_function)

    # 定期 checkpoint
    sm.take_and_save(tick=5000, reason="hourly")

    # 正常关闭
    lm.shutdown("user request")
"""

from ocos.persistence.storage_types import (
    SnapshotDomain, SnapshotStatus, LifecyclePhase, RecoveryOutcome,
    DomainSnapshot, Snapshot, Checkpoint,
    RecoveryState, LifecycleEvent, LifecycleLog,
)

from ocos.persistence.state_serializer import StateSerializer
from ocos.persistence.snapshot_manager import SnapshotManager, StateProvider
from ocos.persistence.recovery_manager import RecoveryManager
from ocos.persistence.lifecycle_manager import LifecycleManager
from ocos.persistence.persistence_validator import PersistenceValidator


__all__ = [
    # Types
    "SnapshotDomain", "SnapshotStatus", "LifecyclePhase", "RecoveryOutcome",
    "DomainSnapshot", "Snapshot", "Checkpoint",
    "RecoveryState", "LifecycleEvent", "LifecycleLog",
    # Core
    "StateSerializer",
    "SnapshotManager", "StateProvider",
    "RecoveryManager",
    "LifecycleManager",
    "PersistenceValidator",
]
