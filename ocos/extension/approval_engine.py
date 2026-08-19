"""Phase 44: ApprovalEngine — 扩展批准引擎。

批准不是扩展自己决定。

流程:
    Candidate → Analysis → Validation → Decision Proposal → Governance Approval → Integration

复用 Phase 43: Decision Proposal 作为批准判断依据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.extension.extension_types import (
    ExtensionCandidate, AnalysisReport,
    CompatibilityReport, SandboxResult,
    ExtensionState,
)


class ApprovalDecision(Enum):
    """批准决定。"""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_INFO = "needs_more_info"


@dataclass(frozen=True)
class ApprovalRequest:
    """批准请求 — 提交给治理层的完整审批包。"""

    candidate: ExtensionCandidate
    analysis: AnalysisReport
    compatibility: CompatibilityReport
    sandbox: SandboxResult
    tick_id: int = 0


@dataclass
class ApprovalEngine:
    """批准引擎 — 基于完整分析+验证结果做出批准判断。

    规则:
        - 兼容性检查不通过 → REJECTED
        - 沙箱验证不通过   → REJECTED
        - 否则 → APPROVED（遵循 CG44-02 流程）
    """

    def evaluate(self, request: ApprovalRequest) -> ApprovalDecision:
        """评估是否批准一个扩展。"""

        # 兼容性不通过 → 拒绝
        if not request.compatibility.is_fully_compatible:
            return ApprovalDecision.REJECTED

        # 沙箱不通过 → 拒绝
        if not request.sandbox.passed:
            return ApprovalDecision.REJECTED

        # 分析置信度过低 → 需要更多信息
        if request.analysis.confidence < 0.3:
            return ApprovalDecision.NEEDS_MORE_INFO

        return ApprovalDecision.APPROVED

    def apply_state(self, candidate_id: str, decision: ApprovalDecision) -> ExtensionState:
        """将决定映射为扩展状态。"""
        mapping = {
            ApprovalDecision.APPROVED: ExtensionState.APPROVED,
            ApprovalDecision.REJECTED: ExtensionState.REJECTED,
            ApprovalDecision.NEEDS_MORE_INFO: ExtensionState.VALIDATING,
        }
        return mapping[decision]


__all__ = ["ApprovalDecision", "ApprovalRequest", "ApprovalEngine"]
