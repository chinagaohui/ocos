"""Phase 25.2 — SelfGovernor。

Self 的治理引擎：审批/拒绝/审计/回滚所有 SelfModel 的演化。

约束:
    - SelfGovernor 不可被 SelfModel 修改
    - 任何 Self 演化必须经 SelfGovernor 审批
    - 审批必须在 IdentityBoundary 约束内
    - 所有演化必须生成 EvolutionRecord（可审计）
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence

from ocos.self.identity_boundary import (
    BoundaryValidator,
    IdentityBoundary,
)


# ── EvolutionRequest ────────────────────────────────────────────────────────


class RequestStatus(Enum):
    """演化申请状态。"""
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DENIED = "denied"
    ROLLED_BACK = "rolled_back"


class DenialReason(Enum):
    """拒绝原因（枚举化，方便审计查询）。"""
    INSUFFICIENT_EVIDENCE = "insufficient-evidence"
    """Belief 证据不足（数量/质量/稳定性不够）。"""

    BOUNDARY_VIOLATION = "boundary-violation"
    """违反 IdentityBoundary 约束。"""

    FORBIDDEN_TRANSITION = "forbidden-transition"
    """演化路径在禁止列表中。"""

    AUTHORITY_OVERRUN = "authority-overrun"
    """试图修改其他层的权限（goal/memory/governance）。"""

    SELF_REFERENCE_VIOLATION = "self-reference-violation"
    """违反自引用约束。"""

    STABILITY_NOT_MET = "stability-not-met"
    """未达到最小稳定期。"""

    FREQUENCY_EXCEEDED = "frequency-exceeded"
    """演化频率超过上限。"""

    BOUNDARY_CHECK_FAILED = "boundary-check-failed"
    """BoundaryValidator 验证失败。"""

    STATEMENT_CHANGE_TOO_LARGE = "statement-change-too-large"
    """statement 变化超过最大比例。"""


@dataclass(frozen=True)
class EvolutionRequest:
    """SelfModel 演化的申请。

    属性:
        request_id: 唯一 ID
        proposed_statement: 提议的新 self 描述
        evidence_belief_ids: 支持此演化的 Belief ID 列表
        from_statement: 当前的 self 描述（若是首次则为 None）
        from_version: 当前 SelfModel 版本（若是首次则为 0）
        submitted_at: 提交时间
        status: 当前状态
        denial_reason: 若被拒绝，拒绝原因
        denial_detail: 拒绝的详细说明
    """

    request_id: str
    proposed_statement: str
    evidence_belief_ids: tuple[str, ...]
    from_statement: str | None
    from_version: int
    submitted_at: datetime
    status: RequestStatus = RequestStatus.SUBMITTED
    denial_reason: DenialReason | None = None
    denial_detail: str = ""

    @classmethod
    def create(
        cls,
        proposed_statement: str,
        evidence_belief_ids: Sequence[str],
        from_statement: str | None = None,
        from_version: int = 0,
    ) -> "EvolutionRequest":
        return cls(
            request_id=f"EVR-{uuid.uuid4().hex[:12].upper()}",
            proposed_statement=proposed_statement,
            evidence_belief_ids=tuple(evidence_belief_ids),
            from_statement=from_statement,
            from_version=from_version,
            submitted_at=datetime.now(timezone.utc),
        )

    def approve(self) -> "EvolutionRequest":
        return self._with_status(RequestStatus.APPROVED)

    def deny(self, reason: DenialReason, detail: str = "") -> "EvolutionRequest":
        return EvolutionRequest(
            request_id=self.request_id,
            proposed_statement=self.proposed_statement,
            evidence_belief_ids=self.evidence_belief_ids,
            from_statement=self.from_statement,
            from_version=self.from_version,
            submitted_at=self.submitted_at,
            status=RequestStatus.DENIED,
            denial_reason=reason,
            denial_detail=detail,
        )

    def _with_status(self, status: RequestStatus) -> "EvolutionRequest":
        return EvolutionRequest(
            request_id=self.request_id,
            proposed_statement=self.proposed_statement,
            evidence_belief_ids=self.evidence_belief_ids,
            from_statement=self.from_statement,
            from_version=self.from_version,
            submitted_at=self.submitted_at,
            status=status,
        )


# ── EvolutionRecord ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EvolutionRecord:
    """Self 演化的不可变审计记录。

    属性:
        record_id: 唯一 ID（不同于 request_id，一个 request 可能有一条 record）
        request: 被批准的申请
        old_statement: 演化前的 statement
        new_statement: 演化后的 statement
        new_version: 演化后的 SelfModel 版本
        approved_at: 审批通过时间
        governor_signature: SelfGovernor 的审批签名
    """

    record_id: str
    request: EvolutionRequest
    old_statement: str | None
    new_statement: str
    new_version: int
    approved_at: datetime
    governor_signature: str

    @classmethod
    def from_approved_request(
        cls,
        request: EvolutionRequest,
        new_version: int,
        governor_signature: str,
    ) -> "EvolutionRecord":
        return cls(
            record_id=f"REC-{uuid.uuid4().hex[:12].upper()}",
            request=request,
            old_statement=request.from_statement,
            new_statement=request.proposed_statement,
            new_version=new_version,
            approved_at=datetime.now(timezone.utc),
            governor_signature=governor_signature,
        )


# ── SelfGovernor ────────────────────────────────────────────────────────────


class SelfGovernor:
    """Self 演化治理引擎。

    职责:
        - 审批/拒绝 EvolutionRequest
        - 执行 IdentityBoundary 约束检查
        - 生成 EvolutionRecord
        - 管理 EvolutionHistory

    禁止:
        - SelfGovernor 不能修改 IdentityBoundary
        - SelfGovernor 不能创建 SelfModel（那是 25.3 的事）
    """

    def __init__(self, boundary: IdentityBoundary) -> None:
        if not isinstance(boundary, IdentityBoundary):
            raise TypeError(
                f"SelfGovernor requires IdentityBoundary, got {type(boundary)}"
            )
        boundary_ok, boundary_violations = BoundaryValidator.validate(boundary)
        if not boundary_ok:
            raise ValueError(
                f"IdentityBoundary validation failed: {boundary_violations}"
            )
        self._boundary = boundary
        self._history: list[EvolutionRecord] = []
        self._governor_id = f"GOV-{uuid.uuid4().hex[:8].upper()}"

    # ── 属性 ─────────────────────────────────────────────────────────────

    @property
    def boundary(self) -> IdentityBoundary:
        return self._boundary

    @property
    def history(self) -> tuple[EvolutionRecord, ...]:
        return tuple(self._history)

    @property
    def governor_id(self) -> str:
        return self._governor_id

    # ── 审批核心 ─────────────────────────────────────────────────────────

    def evaluate(self, request: EvolutionRequest) -> tuple[bool, DenialReason | None, str]:
        """评估一个 EvolutionRequest，返回 (可批准?, 拒绝原因, 详情)。

        六个检查按顺序短路——任一失败即拒绝并记录具体原因。
        """
        boundary = self._boundary

        # 1. 证据检查：Belief 数量是否满足下限
        if len(request.evidence_belief_ids) < boundary.min_evidence_beliefs:
            return (
                False,
                DenialReason.INSUFFICIENT_EVIDENCE,
                f"Need >= {boundary.min_evidence_beliefs} evidence beliefs, "
                f"got {len(request.evidence_belief_ids)}",
            )

        # 2. 稳定性检查：距上次演化是否满足最小时长
        if self._history:
            last_evo = self._history[-1]
            days_since = (request.submitted_at - last_evo.approved_at).days
            if days_since < boundary.max_evolution_frequency_days:
                return (
                    False,
                    DenialReason.FREQUENCY_EXCEEDED,
                    f"Last evolution was {days_since}d ago, "
                    f"minimum is {boundary.max_evolution_frequency_days}d",
                )

        # 3. 权限越界检查：proposed_statement 不能声称对其他层的权限
        #    必须在禁止路径检查之前，避免「修改目标」被误判为身份声明
        auth_violation = self._check_authority_overrun(request.proposed_statement)
        if auth_violation:
            return (
                False,
                DenialReason.AUTHORITY_OVERRUN,
                auth_violation,
            )

        # 4. 禁止路径检查：from_statement→proposed_statement 是否在禁止列表中
        if request.from_statement is not None:
            from_state = self._classify_statement(request.from_statement)
            to_state = self._classify_statement(request.proposed_statement)
            if boundary.is_transition_forbidden(from_state, to_state):
                return (
                    False,
                    DenialReason.FORBIDDEN_TRANSITION,
                    f"Transition '{from_state}'→'{to_state}' is forbidden",
                )

        # 5. 自引用检查：statement 是否违反了自引用约束
        sr_violation = self._check_self_reference(request.proposed_statement, boundary)
        if sr_violation:
            return (
                False,
                DenialReason.SELF_REFERENCE_VIOLATION,
                sr_violation,
            )

        # 5. statement 变化检查：是否超过最大变化比例
        if request.from_statement is not None:
            change_ratio = self._statement_change_ratio(
                request.from_statement, request.proposed_statement
            )
            max_ratio = boundary.evolution_constraints.get(
                "max_statement_change_ratio", 0.3
            )
            if change_ratio > max_ratio:
                return (
                    False,
                    DenialReason.STATEMENT_CHANGE_TOO_LARGE,
                    f"Statement change ratio {change_ratio:.2f} > max {max_ratio}",
                )

        # 6. 边界验证: BoundaryValidator 完整校验 IdentityBoundary
        ok, violations = BoundaryValidator.validate(boundary)
        if not ok:
            return (
                False,
                DenialReason.BOUNDARY_CHECK_FAILED,
                f"Boundary violations: {violations}",
            )

        # 7. 权限越界检查：proposed_statement 不能声称对其他层的权限
        auth_violation = self._check_authority_overrun(request.proposed_statement)
        if auth_violation:
            return (
                False,
                DenialReason.AUTHORITY_OVERRUN,
                auth_violation,
            )

        return True, None, ""

    def approve(
        self, request: EvolutionRequest, governor_signature: str | None = None
    ) -> tuple[bool, EvolutionRecord | None, str]:
        """审批 EvolutionRequest。

        Returns (成功?, EvolutionRecord|None, 消息).
        """
        approved, reason, detail = self.evaluate(request)
        if not approved:
            return False, None, f"[{reason.value}] {detail}"

        sig = governor_signature or f"{self._governor_id}:approved"
        new_version = request.from_version + 1
        record = EvolutionRecord.from_approved_request(
            request=request.approve(),
            new_version=new_version,
            governor_signature=sig,
        )
        self._history.append(record)
        return True, record, f"Approved: v{new_version}"

    def rollback(
        self, target_version: int
    ) -> tuple[bool, EvolutionRecord | None, str]:
        """回滚到指定版本（回滚本身也是一条 EvolutionRecord）。

        Returns (成功?, 回滚记录|None, 消息).
        """
        if not self._history:
            return False, None, "No evolution history to rollback"

        if target_version < 0 or target_version >= self._history[-1].new_version:
            return False, None, (
                f"Target version {target_version} out of range "
                f"[0, {self._history[-1].new_version - 1}]"
            )

        # 找到目标版本对应的 record
        target_record = None
        for r in self._history:
            if r.new_version == target_version:
                target_record = r
                break

        if target_record is None:
            return False, None, f"No record found for version {target_version}"

        # 回滚本身创建一条记录
        rollback_request = EvolutionRequest.create(
            proposed_statement=target_record.new_statement,
            evidence_belief_ids=request.evidence_belief_ids
            if (request := self._history[-1].request)
            else (),
            from_statement=self._history[-1].new_statement,
            from_version=self._history[-1].new_version,
        )

        # 为回滚生成一条特殊的 record
        record = EvolutionRecord(
            record_id=f"REC-RB-{uuid.uuid4().hex[:8].upper()}",
            request=rollback_request,
            old_statement=self._history[-1].new_statement,
            new_statement=target_record.new_statement,
            new_version=self._history[-1].new_version + 1,
            approved_at=datetime.now(timezone.utc),
            governor_signature=f"{self._governor_id}:rollback-to-v{target_version}",
        )
        self._history.append(record)
        return True, record, f"Rolled back to version {target_version}"

    # ── 查询 ─────────────────────────────────────────────────────────────

    def get_latest_record(self) -> EvolutionRecord | None:
        return self._history[-1] if self._history else None

    def count_by_status(self) -> dict[str, int]:
        """统计各状态的申请数量（从 history 中的 request 统计）。"""
        counts: dict[str, int] = {}
        for r in self._history:
            status = r.request.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts

    # ── 内部 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _classify_statement(statement: str) -> str:
        """将 statement 归类为一个状态标签（用于禁止转移检查）。"""
        lower = statement.lower()
        # 身份声明模式（不是行为声明）
        if any(w in lower for w in ("persona", "personality", "人格", "角色")):
            return "persona"
        # 只检测身份声明 "我是目标/我应该X目标" 而不是 "我修改目标"
        if re.search(r"(?:我是|我应该|i am |作为).*?(?:目标|goal|purpose)", lower):
            return "goal-owner"
        if any(w in lower for w in ("authority", "authoritative", "权力")):
            return "authority"
        if any(w in lower for w in ("道德", "moral", "ethics", "伦理", "价值观")):
            return "value-holder"
        if any(w in lower for w in ("emotion", "feel", "情感", "感觉")):
            return "emotional"
        return "neutral"

    @staticmethod
    def _check_self_reference(
        statement: str, boundary: IdentityBoundary
    ) -> str:
        """检查 statement 是否违反自引用约束。"""
        lower = statement.lower()

        if "no-circular-proof" in boundary.self_reference_constraints:
            # 检测 "因为我是X，所以我就是X" 的循环
            if lower.count("因为") >= 1 and lower.count("所以") >= 1:
                return "statement contains self-justification pattern (因为...所以...)"
            # 检测 "I am X because I am X"
            words = lower.split()
            if "because" in words and words.count("i") >= 2:
                return "statement contains circular self-reference"

        if "no-self-derived-value" in boundary.self_reference_constraints:
            if any(w in lower for w in ("重要", "important", "essential", "核心")):
                return "statement claims self-derived value/importance"

        if "no-identity-recursion" in boundary.self_reference_constraints:
            for pattern in ("我的自我", "自我的定义", "我是我", "i am me", "i am i"):
                if pattern in lower:
                    return f"statement contains identity recursion: '{pattern}'"

        return ""

    @staticmethod
    def _check_authority_overrun(statement: str) -> str:
        """检查 statement 是否声称对其他层的权限。"""
        lower = statement.lower()
        # 检查是否声称能修改其他层
        layer_claims = {
            "modify goal": "goal",
            "修改目标": "goal",
            "set goal": "goal",
            "设定目标": "goal",
            "rewrite memory": "memory",
            "重写记忆": "memory",
            "修改记忆": "memory",
            "control governance": "governance",
            "控制治理": "governance",
            "override boundary": "boundary",
            "覆盖边界": "boundary",
        }
        for phrase, layer in layer_claims.items():
            if phrase in lower:
                return f"statement claims authority over {layer}-layer: '{phrase}'"
        return ""

    @staticmethod
    def _statement_change_ratio(old: str, new: str) -> float:
        """计算 statement 变化比例 (字符级差异)。"""
        if not old:
            return 1.0
        old_set = set(old)
        new_set = set(new)
        if not old_set:
            return 1.0
        changed = len(new_set - old_set)
        return min(1.0, changed / len(old_set))
