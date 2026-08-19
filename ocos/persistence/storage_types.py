"""Phase 51.1: Persistent Cognitive Storage — Types.

OCOS v1.1 的核心基础设施 — 让智能跨越关机，持续存在。

设计目标:
    关机 → Checkpoint → 启动 → Restore → 继续存在
    不是: 关机 → 死亡

核心类型:
    - Snapshot: 完整状态快照 (Runtime + Cognitive + Memory + World)
    - Checkpoint: 增量检查点 (tick 触发)
    - RecoveryState: 恢复后的状态评估
    - LifecyclePhase: 生命周期阶段

边界:
    PS51-01: Snapshot ≠ Live State — 快照是副本，不影响运行时
    PS51-02: Restore ≠ Overwrite — 恢复是填充，不覆盖已有
    PS51-03: Partial Recovery OK — 允许部分域恢复失败
    PS51-04: Storage Format Stable — 快照格式跨版本保持可读
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time as _time


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot Domains
# ═══════════════════════════════════════════════════════════════════════════════


class SnapshotDomain(Enum):
    """快照覆盖的状态域。"""
    RUNTIME = "runtime"             # Tick/Attention/Current Context/Active Goals
    COGNITIVE = "cognitive"         # SelfModel/CognitiveSignature/Preferences
    MEMORY = "memory"               # Experience/Episode/Wisdom/Knowledge
    WORLD = "world"                 # Entity/Relation/State History


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot Status
# ═══════════════════════════════════════════════════════════════════════════════


class SnapshotStatus(Enum):
    """快照状态。"""
    TAKEN = "taken"                 # 已创建
    VALIDATED = "validated"         # 已验证
    CORRUPT = "corrupt"             # 损坏
    EXPIRED = "expired"             # 过期
    RESTORING = "restoring"         # 恢复中
    RESTORED = "restored"           # 已恢复
    PARTIAL = "partial"             # 部分恢复 (PS51-03)


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle Phase
# ═══════════════════════════════════════════════════════════════════════════════


class LifecyclePhase(Enum):
    """OCOS 生命周期阶段。"""
    COLD_BOOT = "cold_boot"         # 首次启动（无快照）
    WARM_BOOT = "warm_boot"         # 从快照恢复
    RUNNING = "running"             # 正常运行
    CHECKPOINTING = "checkpointing" # 保存快照中
    DEGRADED = "degraded"           # 部分恢复 (PS51-03)
    SHUTTING_DOWN = "shutting_down" # 正常关闭
    CRASHED = "crashed"             # 异常终止


# ═══════════════════════════════════════════════════════════════════════════════
# Recovery Outcome
# ═══════════════════════════════════════════════════════════════════════════════


class RecoveryOutcome(Enum):
    """恢复结果。"""
    FULL = "full"                   # 全部域恢复成功
    PARTIAL = "partial"             # 部分域恢复 (PS51-03)
    FAILED = "failed"               # 无法恢复
    NO_SNAPSHOT = "no_snapshot"     # 无可用快照


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Snapshot
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DomainSnapshot:
    """单域快照。"""
    domain: SnapshotDomain = field(default=SnapshotDomain.RUNTIME)
    tick: int = 0
    timestamp: float = 0.0
    data: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""              # 完整性校验
    status: SnapshotStatus = SnapshotStatus.TAKEN


# ═══════════════════════════════════════════════════════════════════════════════
# Full Snapshot
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Snapshot:
    """完整系统快照。

    包含 Runtime/Cognitive/Memory/World 四个域。
    PS51-04: format_version 保证跨版本可读。
    """
    snapshot_id: str = ""           # uuid or iso-ts
    format_version: str = "1.0.0"  # PS51-04: 跨版本格式标识
    tick: int = 0
    timestamp: float = field(default_factory=_time.time)
    domains: dict[str, DomainSnapshot] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)  # host/user/os/version
    status: SnapshotStatus = SnapshotStatus.TAKEN

    def domain(self, d: SnapshotDomain) -> DomainSnapshot | None:
        return self.domains.get(d.value)

    @property
    def domain_count(self) -> int:
        return len(self.domains)

    @property
    def is_complete(self) -> bool:
        return self.domain_count >= 4


# ═══════════════════════════════════════════════════════════════════════════════
# Checkpoint (incremental)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Checkpoint:
    """增量检查点 — 轻量级，tick 触发。"""
    checkpoint_id: str = ""
    parent_snapshot_id: str = ""    # 引用的完整快照
    tick: int = 0
    timestamp: float = field(default_factory=_time.time)
    changed_domains: list[SnapshotDomain] = field(default_factory=list)
    delta: dict[str, Any] = field(default_factory=dict)  # 增量数据
    reason: str = ""                # 触发原因 (tick/schedule/critical_op)


# ═══════════════════════════════════════════════════════════════════════════════
# Recovery State
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class RecoveryState:
    """冷启动恢复后的状态报告。"""
    outcome: RecoveryOutcome = RecoveryOutcome.NO_SNAPSHOT
    snapshot: Snapshot | None = None
    recovered_domains: list[SnapshotDomain] = field(default_factory=list)
    failed_domains: list[SnapshotDomain] = field(default_factory=list)
    tick_at_recovery: int = 0
    age_seconds: float = 0.0        # 快照距恢复的时间
    warnings: list[str] = field(default_factory=list)

    @property
    def is_partial(self) -> bool:
        return len(self.failed_domains) > 0 and len(self.recovered_domains) > 0

    @property
    def is_degraded(self) -> bool:
        """PS51-03: 允许部分恢复，此时进入 DEGRADED 模式。"""
        return self.outcome == RecoveryOutcome.PARTIAL


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle Event
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LifecycleEvent:
    """生命周期事件。"""
    event_id: str = ""
    phase: LifecyclePhase = LifecyclePhase.RUNNING
    timestamp: float = field(default_factory=_time.time)
    tick: int = 0
    detail: str = ""
    snapshot_id: str | None = None


@dataclass
class LifecycleLog:
    """生命周期事件日志。"""
    events: list[LifecycleEvent] = field(default_factory=list)
    current_phase: LifecyclePhase = LifecyclePhase.COLD_BOOT
    boot_count: int = 0
    total_uptime_ticks: int = 0


__all__ = [
    "SnapshotDomain", "SnapshotStatus", "LifecyclePhase", "RecoveryOutcome",
    "DomainSnapshot", "Snapshot",
    "Checkpoint",
    "RecoveryState",
    "LifecycleEvent", "LifecycleLog",
]
