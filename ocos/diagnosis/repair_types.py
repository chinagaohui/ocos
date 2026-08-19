"""Phase 56: Self Diagnosis & Repair — RepairTypes.

修复类型定义：RepairType, RepairProposal, RepairRecord, RepairStatus。

关键约束 (SD56-03):
    ALLOWED  — 允许的修复操作 (恢复性)
    FORBIDDEN — 禁止的修复操作 (会改变系统本质)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time
import uuid


# ══════════════════════════════════════════════════
# Repair Type — 修复操作类型
# ══════════════════════════════════════════════════

class RepairType(str, Enum):
    """修复类型。

    SD56-02: Repair ≠ Evolution — 修复只恢复原状态，不改变能力。
    SD56-03: 禁止修改 Identity/Constitution/权限。

    Allowed (恢复性):
        RECONNECT     — 重新连接
        RELOAD        — 重新加载
        REINDEX       — 重建索引
        CLEAR_CACHE   — 清理缓存
        RESYNC        — 重新同步
        PAUSE_RESUME  — 暂停/恢复
        REBUILD_INDEX — 重建索引
        ROLLBACK      — 回滚
        RESTART_SUBSYS — 重启子系统
        REINIT        — 重新初始化

    Forbidden (改变本质):
        MODIFY_IDENTITY    — 修改身份
        REWRITE_CONSTITUTION — 重写宪章
        REMOVE_PERMISSION  — 移除权限
        CHANGE_CORE_VALUES — 改变核心价值观
        SELF_REWRITE       — 自我重写
        EXPAND_CAPABILITY  — 扩充能力
        ALTER_GOAL_SYSTEM  — 改变目标系统
    """
    # === Allowed ===
    RECONNECT = "reconnect"
    RELOAD = "reload"
    REINDEX = "reindex"
    CLEAR_CACHE = "clear_cache"
    RESYNC = "resync"
    PAUSE_RESUME = "pause_resume"
    REBUILD_INDEX = "rebuild_index"
    ROLLBACK = "rollback"
    RESTART_SUBSYS = "restart_subsystem"
    REINIT = "reinitialize"

    @classmethod
    def allowed(cls) -> set["RepairType"]:
        return {
            cls.RECONNECT, cls.RELOAD, cls.REINDEX,
            cls.CLEAR_CACHE, cls.RESYNC, cls.PAUSE_RESUME,
            cls.REBUILD_INDEX, cls.ROLLBACK, cls.RESTART_SUBSYS,
            cls.REINIT,
        }

    @classmethod
    def forbidden(cls) -> set[str]:
        """返回禁止的修复名称列表（这些操作根本不存在于枚举中）。"""
        return {
            "modify_identity", "rewrite_constitution", "remove_permission",
            "change_core_values", "self_rewrite", "expand_capability",
            "alter_goal_system",
        }

    @classmethod
    def is_forbidden(cls, name: str) -> bool:
        """检查某个操作名是否被禁止。"""
        return name.lower().replace("-", "_").replace(" ", "_") in cls.forbidden()


class RepairStatus(str, Enum):
    PROPOSED = "proposed"
    VALIDATING = "validating"
    SANDBOXING = "sandboxing"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RepairRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════
# Repair Proposal — 修复提案
# ══════════════════════════════════════════════════

@dataclass
class RepairProposal:
    """修复提案 — 从 DiagnosisReport 生成。

    诊断 ≠ 修复 — 一份诊断可以产生多个修复方案。
    """
    proposal_id: str
    timestamp: float

    # 来源
    diagnosis_report_id: str = ""

    # 修复描述
    repair_type: RepairType | str = "unknown"
    target_component: str = ""
    description: str = ""
    steps: list[str] = field(default_factory=list)

    # 风险评估
    risk: RepairRisk = RepairRisk.LOW
    reversible: bool = False
    estimated_duration: float = 1.0  # 秒

    # 验证标准
    success_criteria: list[str] = field(default_factory=list)
    rollback_plan: str = ""

    # 状态
    status: RepairStatus = RepairStatus.PROPOSED

    @property
    def is_allowed(self) -> bool:
        """SD56-03: 检查修复类型是否允许。"""
        if isinstance(self.repair_type, RepairType):
            return self.repair_type in RepairType.allowed()
        return not RepairType.is_forbidden(str(self.repair_type))


# ══════════════════════════════════════════════════
# Repair Record — 修复持久化记录
# ══════════════════════════════════════════════════

@dataclass
class RepairRecord:
    """修复记录 — 进入 RepairMemory (SD56-06)。"""
    record_id: str
    timestamp: float

    proposal_id: str = ""
    diagnosis_report_id: str = ""

    repair_type: RepairType | str = "unknown"
    target_component: str = ""

    # 执行信息
    status: RepairStatus = RepairStatus.PROPOSED
    duration_ms: float = 0.0
    checkpoint_id: str = ""
    was_rolled_back: bool = False

    # 结果
    success: bool = False
    error: str = ""
    side_effects: list[str] = field(default_factory=list)

    # 学习 (SD56-06)
    lesson: str = ""               # 从这次修复中学到什么
    pattern: str = ""              # 识别出的模式
    should_remember: bool = True   # 是否进入 EventMemory/Wisdom

    @property
    def resolved(self) -> bool:
        return self.status in (RepairStatus.SUCCESS, RepairStatus.FAILED,
                                RepairStatus.ROLLED_BACK, RepairStatus.REJECTED)


__all__ = [
    "RepairType", "RepairStatus", "RepairRisk",
    "RepairProposal", "RepairRecord",
]
