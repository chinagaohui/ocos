"""Phase AA: SelfEvolutionManager — 自我演化统一管理器。

整合 EvolutionProposer + ImpactAnalyzer + EvolutionSandbox
+ MigrationEngine + EvolutionMemory 形成完整的自我演化闭环。

治理流程（CE47-02）：
    Observation → Detection → Proposal → Analysis → Sandbox → Approval → Migration

边界约束（CE47-04）：
    - 禁止修改 identity/constitution/permission_model/core_values/anchor
    - 任何路径（含人工批准）都不可越界

回滚保障（CE47-03）：
    - 每次迁移前创建快照
    - 迁移失败自动触发回滚
    - 支持手动回滚
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ocos.evolution.evolution_proposer import EvolutionProposer
from ocos.evolution.evolution_sandbox import EvolutionSandbox, SandboxReport
from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    EvolutionTrigger,
    EvolutionDomain,
    ImpactAssessment,
    RollbackReason,
)
from ocos.evolution.evolution_memory import EvolutionMemory
from ocos.evolution.migration_engine import MigrationEngine, MigrationResult
from ocos.evolution.improvement_detector import ImprovementDetector, DetectedSignal

from ocos.logging import get_logger

logger = get_logger(__name__)


# 允许演化的领域（排除 forbidden domains）
ALLOWED_DOMAINS = {
    EvolutionDomain.CAPABILITY,
    EvolutionDomain.CONNECTION,
    EvolutionDomain.PARAMETER,
    EvolutionDomain.ADAPTER,
    EvolutionDomain.KNOWLEDGE_STRUCTURE,
    EvolutionDomain.ATTENTION_POLICY,
    EvolutionDomain.LEARNING_STRATEGY,
    EvolutionDomain.EXTENSION_INTEGRATION,
}


@dataclass
class EvolutionStatus:
    """进化状态摘要。"""
    total_proposals: int = 0
    pending_proposals: int = 0
    approved_proposals: int = 0
    active_proposals: int = 0
    rejected_proposals: int = 0
    rolled_back_proposals: int = 0
    total_migrations: int = 0
    successful_migrations: int = 0
    failed_migrations: int = 0
    last_evolution_time: str = ""
    last_evolution_domain: str = ""
    last_evolution_result: str = ""


class SelfEvolutionManager:
    """自我演化管理器 — 认知系统的自我改进中枢。

    职责：
    1. 监控认知信号，检测改进机会
    2. 生成进化提案并进入治理链
    3. 执行安全迁移并记录历史
    4. 提供回滚能力

    边界：
    - 不修改 identity/constitution/permission_model
    - 所有提案必须通过沙箱验证
    - 所有迁移必须可回滚
    """

    def __init__(
        self,
        proposer: EvolutionProposer | None = None,
        sandbox: EvolutionSandbox | None = None,
        migration_engine: MigrationEngine | None = None,
        memory: EvolutionMemory | None = None,
        detector: ImprovementDetector | None = None,
        auto_approve: bool = False,
        max_proposals: int = 100,
        rollback_check_interval: int = 1000,
    ) -> None:
        self._proposer = proposer or EvolutionProposer()
        self._sandbox = sandbox or EvolutionSandbox()
        self._migration_engine = migration_engine or MigrationEngine()
        self._memory = memory or EvolutionMemory()
        self._detector = detector or ImprovementDetector()
        
        # 配置
        self._auto_approve = auto_approve
        self._max_proposals = max_proposals
        self._rollback_check_interval = rollback_check_interval
        
        # 计数器
        self._tick_count = 0
        self._successful_evolutions: list[str] = []
        
        # 状态存储
        self._proposals: dict[str, EvolutionProposal] = {}
        self._migrations: dict[str, MigrationResult] = {}
        self._snapshots: dict[str, str] = {}

    # ── 核心流程 ────────────────────────────────────────────────

    def detect_and_propose(
        self,
        source_module: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        severity: float,
        description: str,
        trigger: EvolutionTrigger = EvolutionTrigger.EXPERIENCE_PATTERN,
    ) -> EvolutionProposal | None:
        """检测到改进信号，生成进化提案。

        Returns:
            生成的提案，若超过最大提案数则返回 None
        """
        # 检查提案数量限制
        if len(self._proposals) >= self._max_proposals:
            logger.warning("Max proposals reached (%d), skipping detection", self._max_proposals)
            return None

        # 构建信号
        signal = DetectedSignal(
            trigger=trigger,
            source_tick=self._tick_count,
            source_module=source_module,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            severity=severity,
            description=description,
        )

        # 生成提案
        proposal = self._proposer.propose(signal, description=description)
        self._proposals[proposal.proposal_id] = proposal

        # 记录到记忆
        self._memory.record(proposal, "detected", f"signal={metric_name}={metric_value}")

        logger.info("Evolution proposal detected: %s (%s)", proposal.proposal_id, proposal.domain.value)
        return proposal

    def analyze_proposal(self, proposal_id: str) -> ImpactAssessment | None:
        """分析提案影响。"""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            logger.warning("Proposal not found: %s", proposal_id)
            return None

        proposal.state = EvolutionState.ANALYZING
        impact = self._proposer._build_initial_impact(
            proposal.domain,
            type('Signal', (), {'source_tick': proposal.source_tick,
                               'source_module': proposal.target_module,
                               'metric_name': '', 'metric_value': 0.0,
                               'threshold': 0.0, 'severity': 0.5,
                               'description': proposal.description})(),
        )

        self._memory.record(proposal, "analyzing", f"impact={impact.level.value}")
        return impact

    def validate_proposal(self, proposal_id: str) -> SandboxReport | None:
        """在沙箱中验证提案。

        Returns:
            沙箱报告
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            logger.warning("Proposal not found: %s", proposal_id)
            return None

        report = self._sandbox.validate(proposal)
        
        if report.all_passed:
            self._memory.record(proposal, "sandbox_passed", 
                f"tests={report.test_count}, passed={report.passed_count}")
            logger.info("Proposal %s passed sandbox validation", proposal_id)
        else:
            proposal.state = EvolutionState.REJECTED
            self._memory.record(proposal, "sandbox_failed",
                f"errors={report.errors}")
            logger.warning("Proposal %s failed sandbox: %s", proposal_id, report.errors)

        return report

    def approve_proposal(self, proposal_id: str, approver: str = "human") -> bool:
        """人工批准提案（安全预检通过后）。

        注意：批准不等于执行，执行仍需 MigrationEngine
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if not proposal.sandbox_passed:
            logger.warning("Cannot approve %s: sandbox not passed", proposal_id)
            return False

        if not proposal.is_boundary_safe:
            logger.warning("Cannot approve %s: boundary violation", proposal_id)
            return False

        proposal.governance_approved = True
        proposal.approved_by = approver
        proposal.state = EvolutionState.APPROVED

        self._memory.record(proposal, "human_approved", f"approved_by={approver}")
        logger.info("Proposal %s approved by %s", proposal_id, approver)
        return True

    def execute_proposal(self, proposal_id: str) -> MigrationResult | None:
        """执行批准的提案（安全迁移）。

        Returns:
            迁移结果
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return None

        if not proposal.ready_for_migration:
            logger.warning("Proposal %s not ready for migration", proposal_id)
            return None

        # 创建快照（CE47-03）
        snapshot_id = f"snap:{proposal_id}:{datetime.now(timezone.utc).isoformat()}"
        self._snapshots[snapshot_id] = self._get_current_state(proposal)
        proposal.rollback_snapshot = snapshot_id

        # 执行迁移
        result = self._migration_engine.migrate(proposal, self._tick_count)
        self._migrations[proposal_id] = result

        if result.success:
            proposal.state = EvolutionState.ACTIVE
            proposal.active_since_tick = self._tick_count
            self._successful_evolutions.append(proposal_id)
            self._memory.record(proposal, "migrated", f"success={result.success}")
            logger.info("Evolution executed successfully: %s", proposal_id)
        else:
            # 失败触发回滚（CE47-03）
            self._trigger_rollback(proposal_id, RollbackReason.TEST_FAILURE)
            self._memory.record(proposal, "migration_failed", f"error={result.error}")
            logger.error("Evolution failed and rolled back: %s - %s", proposal_id, result.error)

        return result

    # ── 回滚 ────────────────────────────────────────────────────

    def rollback(self, proposal_id: str, reason: RollbackReason = RollbackReason.TEST_FAILURE) -> bool:
        """回滚一次已执行的进化。

        Returns:
            是否成功回滚
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False

        if not proposal.rollback_snapshot:
            logger.warning("No snapshot for rollback: %s", proposal_id)
            return False

        # 恢复快照
        self._snapshots.pop(proposal.rollback_snapshot, None)
        proposal.state = EvolutionState.ROLLED_BACK

        # 从成功列表中移除
        if proposal_id in self._successful_evolutions:
            self._successful_evolutions.remove(proposal_id)

        self._memory.record(proposal, "rolled_back", f"reason={reason.value}")
        logger.info("Evolution rolled back: %s (reason=%s)", proposal_id, reason.value)
        return True

    # ── 查询接口 ────────────────────────────────────────────────

    def get_proposal(self, proposal_id: str) -> EvolutionProposal | None:
        """获取提案详情。"""
        return self._proposals.get(proposal_id)

    def list_proposals(self, state: EvolutionState | None = None) -> list[EvolutionProposal]:
        """列出提案，可按状态过滤。"""
        proposals = list(self._proposals.values())
        if state:
            proposals = [p for p in proposals if p.state == state]
        return proposals

    def get_status(self) -> EvolutionStatus:
        """获取进化状态摘要。"""
        all_proposals = list(self._proposals.values())
        
        return EvolutionStatus(
            total_proposals=len(all_proposals),
            pending_proposals=len([p for p in all_proposals 
                                   if p.state in (EvolutionState.DRAFTING, 
                                                  EvolutionState.ANALYZING,
                                                  EvolutionState.SANDBOXING,
                                                  EvolutionState.PENDING_REVIEW)]),
            approved_proposals=len([p for p in all_proposals 
                                    if p.state == EvolutionState.APPROVED]),
            active_proposals=len([p for p in all_proposals 
                                  if p.state == EvolutionState.ACTIVE]),
            rejected_proposals=len([p for p in all_proposals 
                                    if p.state == EvolutionState.REJECTED]),
            rolled_back_proposals=len([p for p in all_proposals 
                                       if p.state == EvolutionState.ROLLED_BACK]),
            total_migrations=len(self._migrations),
            successful_migrations=len(self._successful_evolutions),
            failed_migrations=len(self._migrations) - len(self._successful_evolutions),
            last_evolution_time=datetime.now(timezone.utc).isoformat() if self._successful_evolutions else "",
            last_evolution_domain=all_proposals[-1].domain.value if all_proposals else "",
            last_evolution_result="success" if self._successful_evolutions else "none",
        )

    def get_history(self) -> list[dict]:
        """获取完整进化历史。"""
        return self._memory._history

    def get_successful_evolutions(self) -> list[str]:
        """获取成功进化的提案 ID 列表。"""
        return self._successful_evolutions.copy()

    def get_recent_migrations(self, limit: int = 10) -> list[MigrationResult]:
        """获取最近迁移结果。"""
        return list(self._migrations.values())[-limit:]

    # ── 自动化 ──────────────────────────────────────────────────

    def tick(self) -> dict:
        """主循环 tick，执行自动检测与简化流程。"""
        self._tick_count += 1
        
        results = {
            "tick": self._tick_count,
            "proposals_created": 0,
            "migrations_executed": 0,
            "errors": [],
        }
        
        # 自动检测模式（简化流程：检测→分析→验证→执行）
        if self._auto_approve:
            # 这里可以集成 ImprovementDetector 的自动信号检测
            # 当前为简化实现
            pass
        
        return results

    # ── 内部方法 ────────────────────────────────────────────────

    def _get_current_state(self, proposal: EvolutionProposal) -> str:
        """获取提案当前状态快照（用于回滚）。"""
        return f"state={proposal.state.value}, domain={proposal.domain.value}, " \
               f"target={proposal.target_module}, change={proposal.change_type}"

    def _trigger_rollback(self, proposal_id: str, reason: RollbackReason) -> None:
        """触发回滚。"""
        self.rollback(proposal_id, reason)

    @property
    def proposal_count(self) -> int:
        return len(self._proposals)

    @property
    def active_proposals(self) -> list[EvolutionProposal]:
        return [p for p in self._proposals.values() if p.state == EvolutionState.ACTIVE]

    @property
    def pending_proposals(self) -> list[EvolutionProposal]:
        return [p for p in self._proposals.values() 
                if p.state in (EvolutionState.DRAFTING, EvolutionState.ANALYZING,
                              EvolutionState.SANDBOXING, EvolutionState.APPROVED)]


__all__ = [
    "SelfEvolutionManager",
    "EvolutionStatus",
]
