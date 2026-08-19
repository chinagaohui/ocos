"""Phase 56: RepairProposer — 修复提案生成器。

输入: DiagnosisReport + FaultSignal
输出: RepairProposal

SD56-02: 修复只恢复原状，不改变能力
SD56-03: 禁止的修复类型会被过滤

映射规则:
    CAPABILITY_FAILURE → RECONNECT / RELOAD
    STORAGE_FAILURE → REINDEX / REINIT
    CONNECTION_FAILURE → RECONNECT
    PERFORMANCE_DEGRADATION → CLEAR_CACHE / PAUSE_RESUME
    STATE_CORRUPTION → ROLLBACK
    SCHEDULER_STALL → RESTART_SUBSYS
    CONSISTENCY_WARNING → REBUILD_INDEX / RESYNC
    MEMORY_LEAK → CLEAR_CACHE
    IDENTITY_DRIFT → REINIT (with extra validation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time
import uuid

from ocos.diagnosis.diagnosis_types import (
    DiagnosisReport, FaultSignal, FaultCategory, Severity,
)
from ocos.diagnosis.repair_types import (
    RepairProposal, RepairType, RepairRisk, RepairStatus,
)


# ══════════════════════════════════════════════════
# Fault → Repair Type Mapping
# ══════════════════════════════════════════════════

FAULT_TO_REPAIR: dict[FaultCategory, list[tuple[RepairType, RepairRisk, str]]] = {
    FaultCategory.CAPABILITY_FAILURE: [
        (RepairType.RECONNECT, RepairRisk.LOW, "重新连接能力适配器"),
        (RepairType.RELOAD, RepairRisk.MODERATE, "重新加载能力配置"),
    ],
    FaultCategory.STORAGE_FAILURE: [
        (RepairType.REINDEX, RepairRisk.MODERATE, "重建存储索引"),
        (RepairType.REINIT, RepairRisk.HIGH, "重新初始化存储"),
    ],
    FaultCategory.CONNECTION_FAILURE: [
        (RepairType.RECONNECT, RepairRisk.LOW, "重新连接"),
        (RepairType.RESTART_SUBSYS, RepairRisk.MODERATE, "重启子系统"),
    ],
    FaultCategory.PERFORMANCE_DEGRADATION: [
        (RepairType.CLEAR_CACHE, RepairRisk.LOW, "清理缓存"),
        (RepairType.PAUSE_RESUME, RepairRisk.MODERATE, "暂停后恢复调度"),
    ],
    FaultCategory.STATE_CORRUPTION: [
        (RepairType.ROLLBACK, RepairRisk.HIGH, "回滚到最近检查点"),
        (RepairType.REBUILD_INDEX, RepairRisk.HIGH, "重建索引"),
    ],
    FaultCategory.SCHEDULER_STALL: [
        (RepairType.RESTART_SUBSYS, RepairRisk.MODERATE, "重启调度器"),
        (RepairType.PAUSE_RESUME, RepairRisk.LOW, "暂停后恢复"),
    ],
    FaultCategory.CONSISTENCY_WARNING: [
        (RepairType.REBUILD_INDEX, RepairRisk.MODERATE, "重建索引"),
        (RepairType.RESYNC, RepairRisk.LOW, "重新同步"),
    ],
    FaultCategory.MEMORY_LEAK: [
        (RepairType.CLEAR_CACHE, RepairRisk.LOW, "清理缓存"),
    ],
    FaultCategory.IDENTITY_DRIFT: [
        (RepairType.REINIT, RepairRisk.CRITICAL, "重新初始化(需额外验证)"),
    ],
    FaultCategory.RESOURCE_PRESSURE: [
        (RepairType.CLEAR_CACHE, RepairRisk.LOW, "清理缓存释放资源"),
        (RepairType.PAUSE_RESUME, RepairRisk.MODERATE, "暂停非关键任务"),
    ],
}


@dataclass
class RepairProposer:
    """修复提案生成器。

    从诊断报告生成候选修复方案。
    """

    # 提案数限制
    max_proposals_per_diagnosis: int = 3
    auto_propose_threshold: Severity = Severity.MODERATE

    def propose(self, diagnosis: DiagnosisReport,
                fault: FaultSignal | None = None) -> list[RepairProposal]:
        """从诊断报告生成修复提案列表。

        SD56-03: 自动过滤禁止的修复类型。
        """
        proposals: list[RepairProposal] = []

        repair_options = FAULT_TO_REPAIR.get(diagnosis.category, [])
        if not repair_options:
            # 无匹配规则 → 不提案
            return proposals

        for repair_type, risk, description in repair_options[:self.max_proposals_per_diagnosis]:
            proposal = self._build_proposal(
                diagnosis, repair_type, risk, description,
                diagnosis.affected_components,
            )
            # SD56-03: 跳过禁止的修复
            if not proposal.is_allowed:
                continue
            proposals.append(proposal)

        return proposals

    def _build_proposal(self, diagnosis: DiagnosisReport,
                        repair_type: RepairType, risk: RepairRisk,
                        description: str,
                        components: list[str]) -> RepairProposal:
        target = components[0] if components else "unknown"

        steps = self._build_steps(repair_type, target)

        proposal = RepairProposal(
            proposal_id=f"rprop-{uuid.uuid4().hex[:10]}",
            timestamp=_time.time(),
            diagnosis_report_id=diagnosis.report_id,
            repair_type=repair_type,
            target_component=target,
            description=description,
            steps=steps,
            risk=risk,
            reversible=risk != RepairRisk.CRITICAL,
            estimated_duration=self._estimate_duration(repair_type),
            success_criteria=self._build_criteria(repair_type, target),
            rollback_plan=self._build_rollback(repair_type, risk),
        )
        return proposal

    def _build_steps(self, repair_type: RepairType, target: str) -> list[str]:
        steps_map = {
            RepairType.RECONNECT: [
                f"1. 中断 {target} 当前连接",
                f"2. 建立新连接到 {target}",
                "3. 验证连接状态",
            ],
            RepairType.RELOAD: [
                f"1. 保存 {target} 当前状态",
                f"2. 重新加载 {target} 配置",
                "3. 验证功能正常",
            ],
            RepairType.CLEAR_CACHE: [
                f"1. 标记 {target} 缓存为待清理",
                "2. 清空缓存",
                "3. 验证性能恢复",
            ],
            RepairType.REINDEX: [
                f"1. 锁住 {target} 写入",
                "2. 重建索引",
                "3. 解锁写入",
                "4. 验证查询正常",
            ],
            RepairType.ROLLBACK: [
                "1. 查找最近有效检查点",
                "2. 恢复到检查点",
                "3. 验证数据一致性",
            ],
            RepairType.PAUSE_RESUME: [
                f"1. 暂停 {target} 操作",
                "2. 等待 n 秒",
                "3. 恢复 {target} 操作",
                "4. 验证正常",
            ],
            RepairType.RESTART_SUBSYS: [
                f"1. 优雅关闭 {target}",
                f"2. 重新初始化 {target}",
                "3. 验证启动成功",
            ],
            RepairType.RESYNC: [
                f"1. 标记 {target} 不同步",
                "2. 执行全量同步",
                "3. 验证一致性",
            ],
            RepairType.REBUILD_INDEX: [
                f"1. 删除 {target} 旧索引",
                f"2. 全量重建索引",
                "3. 验证索引完整",
            ],
            RepairType.REINIT: [
                f"1. 备份 {target} 当前状态",
                f"2. 重置 {target} 到初始状态",
                "3. 恢复数据",
                "4. 验证功能",
            ],
        }
        return steps_map.get(repair_type, [f"执行 {repair_type.value} 操作"])

    def _estimate_duration(self, repair_type: RepairType) -> float:
        durations = {
            RepairType.RECONNECT: 2.0,
            RepairType.RELOAD: 5.0,
            RepairType.CLEAR_CACHE: 1.0,
            RepairType.REINDEX: 10.0,
            RepairType.ROLLBACK: 30.0,
            RepairType.PAUSE_RESUME: 3.0,
            RepairType.RESTART_SUBSYS: 15.0,
            RepairType.RESYNC: 20.0,
            RepairType.REBUILD_INDEX: 15.0,
            RepairType.REINIT: 30.0,
        }
        return durations.get(repair_type, 5.0)

    def _build_criteria(self, repair_type: RepairType, target: str) -> list[str]:
        return [
            f"{target} 状态恢复正常",
            "无异常日志",
            "健康检查通过",
        ]

    def _build_rollback(self, repair_type: RepairType, risk: RepairRisk) -> str:
        if risk == RepairRisk.CRITICAL:
            return "从快照完全恢复"
        if risk == RepairRisk.HIGH:
            return "从检查点回滚"
        return "撤销操作，恢复前状态"


__all__ = ["RepairProposer"]
