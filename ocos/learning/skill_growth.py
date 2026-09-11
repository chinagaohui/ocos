"""skill_growth — 技能生长 (Blueprint L4/L5/L6, Phase 49-C).

Freeze Phase 49-C: 纯逻辑 + 有限 OCOS 类型依赖 (Skill/SkillRegistry)。

职责:
  C1 Replanner:     TaskDAG 任务失败 → 诊断 → 重试/跳过/替代 (L4)
  C2 SkillProposer: 同任务成功 N 次 → Candidate Skill (L5, N=候选生成阈值)
  C3 Governed Skill: Candidate → Verification → Validated → Committed (L5/L6)

治理纪律 (Blueprint v1.1 §5/§10):
  - N=3 只生成候选, 不授予执行权
  - 写类 Skill 即使注册仍走 DecisionBridge AUTO/ASK 分级
  - 学习产物无直接 Action 路径
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════════
# C1 — Replanner (L4: 失败 → 重试/跳过/替代)
# ═══════════════════════════════════════════════════════════════════════════════


class ReplanAction(str, Enum):
    """失败后的重规划动作。"""

    RETRY = "retry"                    # 可重试 (执行错误/超时) → 重试同任务
    SKIP_DEPENDENTS = "skip_dependents"  # 不可重试且无替代 → 跳过后续依赖任务
    CONTINUE_NEXT = "continue_next"    # 单任务失败不影响后续 → 继续
    AMBIGUOUS_BLOCK = "ambiguous_block"  # 模糊任务 → 标记待澄清, 不重试


# 失败原因 → 重规划动作映射 (确定性规则)
_CAUSE_TO_REPLAN = {
    "ambiguous_task": ReplanAction.AMBIGUOUS_BLOCK,
    "execution_error": ReplanAction.RETRY,
    "timeout": ReplanAction.RETRY,
    # BV5-2026-09-11: sql_schema_mismatch 可修复 → RETRY
    # Schema Provider 已注入真实列名，但 LLM 仍可能幻觉不存在列；
    # retry 走 FIX-9 _revise_task_description 回注失败原因 →
    # LLM 应该会先查 PRAGMA table_info 再用真实列重建 SQL
    "sql_schema_mismatch": ReplanAction.RETRY,
    "permission_denied": ReplanAction.CONTINUE_NEXT,  # 待批不阻塞其余
    "tool_unavailable": ReplanAction.SKIP_DEPENDENTS,
    # P0-2026-09-10: 硬依赖缺失 → 终态跳过（不是软错误重试能解决的）
    # writer 循环几百次失败就是因为 DEPENDENCY_MISSING 没被识别 →
    # 当成 EXECUTION_ERROR 无限重试
    "dependency_missing": ReplanAction.SKIP_DEPENDENTS,
    "llm_conversion_failed": ReplanAction.AMBIGUOUS_BLOCK,
    "unknown": ReplanAction.CONTINUE_NEXT,
}

# 最多重试次数 (治理上限)
MAX_RETRY_PER_TASK = 2


@dataclass
class ReplanDecision:
    """单个任务失败的重规划决策。"""

    task_id: str
    action: ReplanAction
    cause: str
    reason: str
    retry_count: int = 0
    retryable: bool = False


class TaskReplanner:
    """L4: 任务失败重规划器 — 确定性规则 (无 LLM)。

    ABI:
        decide(task_id, cause, retry_count) -> ReplanDecision
        should_retry(decision) -> bool
    """

    @classmethod
    def decide(cls, task_id: str, cause: str,
               retry_count: int = 0) -> ReplanDecision:
        """根据失败原因 + 重试次数决定动作。"""
        action = _CAUSE_TO_REPLAN.get(cause, ReplanAction.CONTINUE_NEXT)
        retryable = action == ReplanAction.RETRY and retry_count < MAX_RETRY_PER_TASK
        if action == ReplanAction.RETRY and not retryable:
            # 重试耗尽 → 跳过依赖 (诚实归档, 不伪装)
            action = ReplanAction.SKIP_DEPENDENTS
            reason = (f"cause={cause} retry_count={retry_count} "
                      f"exceeds max={MAX_RETRY_PER_TASK}")
        else:
            reason = f"cause={cause} → {action.value}"
        return ReplanDecision(
            task_id=task_id,
            action=action,
            cause=cause,
            reason=reason,
            retry_count=retry_count,
            retryable=retryable,
        )

    @classmethod
    def should_retry(cls, decision: ReplanDecision) -> bool:
        """是否应重试该任务。"""
        return decision.retryable and decision.action == ReplanAction.RETRY

    @classmethod
    def is_terminal(cls, decision: ReplanDecision) -> bool:
        """是否终态 (不可再重试)。"""
        return decision.action in (
            ReplanAction.SKIP_DEPENDENTS,
            ReplanAction.AMBIGUOUS_BLOCK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# C2 — SkillProposer (L5: 成功 N 次 → Candidate Skill)
# ═══════════════════════════════════════════════════════════════════════════════


class SkillProposalStatus(str, Enum):
    """候选技能生命周期 (Blueprint v1.1 §5 四段)。"""

    CANDIDATE = "candidate"      # N 次成功 → 候选 (未验证)
    VALIDATED = "validated"      # 规则验证通过 (只读/低风险)
    REJECTED = "rejected"        # 验证失败
    COMMITTED = "committed"      # 注册完成 (Governed)


@dataclass(frozen=True)
class SkillProposal:
    """技能生长候选 — 从成功 Episode 模式归纳。"""

    skill_id: str
    name: str
    trigger_pattern: str        # 目标描述模式 (applicable_context)
    procedure: tuple[str, ...]  # 成功执行序列 (agent_type + task_type)
    success_count: int
    confidence: float
    status: SkillProposalStatus = SkillProposalStatus.CANDIDATE
    source_episodes: tuple[str, ...] = ()
    approval_required: bool = False   # 写类/高风险 → 需审批
    approval_id: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_skill(self) -> Any:
        """转换为可注册 Skill (SkillRegistry.save_skill 输入)。

        仅当 status == VALIDATED/COMMITTED 时调用 — 治理约束。
        """
        from ocos.capability.models import Skill
        return Skill(
            id=self.skill_id,
            name=self.name,
            description=f"[auto-proposed] trigger: {self.trigger_pattern}",
            input_state={"trigger_pattern": self.trigger_pattern},
            output_state={"procedure": list(self.procedure)},
            required_capability="reasoning",
            fallback_strategy="retry",
            max_retries=1,
        )


# 候选生成阈值 (Blueprint v1.1 §5: 只生成候选, 非技能成立)
CANDIDATE_MIN_SUCCESS = 3


class SkillProposer:
    """L5: 从成功 Episode 模式提议候选技能。

    确定性规则 (无 LLM):
      - 聚类键 = task 描述归一化指纹 (同 Phase 49-A RuleBasedLearner)
      - 同指纹成功 ≥ CANDIDATE_MIN_SUCCESS (3) → 生成候选
      - 写类/高风险 task_type (create/modify/execute) → approval_required=True
    """

    # 写类/高风险 task_type — 即使成功也不自动执行 (治理)
    WRITE_TASK_TYPES = frozenset({"create", "modify", "delete", "execute"})

    @classmethod
    def _fingerprint(cls, task: str) -> str:
        norm = "".join(task.split()).lower()[:40]
        return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12] if norm else ""

    @classmethod
    def propose_from_episodes(cls, episodes: list[Any]) -> list[SkillProposal]:
        """从成功 Episode 归纳候选技能。

        Episode 需含: goal (任务描述), decision/outcome (成功标记),
        context.agent (执行 agent)。
        """
        # 按任务指纹聚合成功 episode
        successes: dict[str, list[Any]] = {}
        for ep in episodes:
            goal = getattr(ep, "goal", None) or ""
            outcome = getattr(ep, "outcome", None) or {}
            ok = outcome.get("success", True) if isinstance(outcome, dict) else True
            if ok is False or ok == 0:
                continue  # 只统计成功
            if not goal:
                continue
            fp = cls._fingerprint(str(goal))
            if fp:
                successes.setdefault(fp, []).append(ep)

        proposals: list[SkillProposal] = []
        for fp, eps in successes.items():
            if len(eps) < CANDIDATE_MIN_SUCCESS:
                continue  # 不足候选阈值
            goal = str(getattr(eps[0], "goal", "") or "")[:60]
            # 提取执行 procedure (agent_type 序列)
            agent_types: list[str] = []
            task_types: list[str] = []
            for ep in eps[:10]:
                ctx = getattr(ep, "context", None) or {}
                if isinstance(ctx, dict):
                    at = ctx.get("agent", "") or ""
                    tt = ctx.get("task_type", "") or ""
                else:
                    at = getattr(ctx, "agent", "") or ""
                    tt = getattr(ctx, "task_type", "") or ""
                if at:
                    agent_types.append(at)
                if tt:
                    task_types.append(tt)

            procedure = tuple(
                f"{a}:{t}" for a, t in zip(agent_types, task_types)
                if a and t
            ) or tuple(f"{a}:analyze" for a in agent_types[:1])

            # 写类判定: 依 task_type (如均为 analyze/verify → 只读)
            is_write = any(t in cls.WRITE_TASK_TYPES for t in task_types) \
                or not task_types  # 未知类型 → 保守视为需审批
            # 保守: 无法证明只读 → approval_required
            skill_id = f"SKL-{fp}"
            proposals.append(SkillProposal(
                skill_id=skill_id,
                name=f"auto:{goal[:20]}",
                trigger_pattern=goal,
                procedure=procedure or ("reasoning:analyze",),
                success_count=len(eps),
                confidence=min(0.5 + 0.1 * len(eps), 0.95),
                status=SkillProposalStatus.CANDIDATE,
                source_episodes=tuple(ep.id for ep in eps[:10]),
                approval_required=is_write,
            ))
        return proposals


# ═══════════════════════════════════════════════════════════════════════════════
# C3 — Governed Skill Commit (L5/L6)
# ═══════════════════════════════════════════════════════════════════════════════


class GovernedSkillCommitter:
    """L5/L6: 候选技能 → 验证 → 注册 (治理四段).

    ABI:
        validate(proposal) -> SkillProposal (CANDIDATE→VALIDATED/REJECTED)
        commit(proposal, registry) -> Skill | None (VALIDATED→注册)
    """

    @classmethod
    def validate(cls, proposal: SkillProposal,
                 read_only_ok: bool = True) -> SkillProposal:
        """规则验证 (无 LLM, 无执行).

        只读候选 → VALIDATED; 写类候选 → 保持 CANDIDATE + approval_required
        (等待人工审批, 见 approve()).
        """
        if proposal.approval_required:
            return SkillProposal(  # 写类: 等待审批, 保持 CANDIDATE
                skill_id=proposal.skill_id,
                name=proposal.name,
                trigger_pattern=proposal.trigger_pattern,
                procedure=proposal.procedure,
                success_count=proposal.success_count,
                confidence=proposal.confidence,
                status=SkillProposalStatus.CANDIDATE,
                source_episodes=proposal.source_episodes,
                approval_required=True,
                created_at=proposal.created_at,
            )
        return SkillProposal(
            skill_id=proposal.skill_id,
            name=proposal.name,
            trigger_pattern=proposal.trigger_pattern,
            procedure=proposal.procedure,
            success_count=proposal.success_count,
            confidence=proposal.confidence,
            status=SkillProposalStatus.VALIDATED,
            source_episodes=proposal.source_episodes,
            approval_required=False,
            created_at=proposal.created_at,
        )

    @classmethod
    def approve(cls, proposal: SkillProposal,
                approval_id: str) -> SkillProposal:
        """人工审批写类候选 → VALIDATED (携带 approval_id)."""
        return SkillProposal(
            skill_id=proposal.skill_id,
            name=proposal.name,
            trigger_pattern=proposal.trigger_pattern,
            procedure=proposal.procedure,
            success_count=proposal.success_count,
            confidence=proposal.confidence,
            status=SkillProposalStatus.VALIDATED,
            source_episodes=proposal.source_episodes,
            approval_required=False,
            approval_id=approval_id,
            created_at=proposal.created_at,
        )

    @classmethod
    def commit(cls, proposal: SkillProposal, registry: Any) -> Optional[Any]:
        """VALIDATED 候选 → 注册到 SkillRegistry (持久化).

        治理: 仅 VALIDATED/COMMITTED 可注册; CANDIDATE/REJECTED 拒绝.
        """
        if proposal.status != SkillProposalStatus.VALIDATED:
            return None
        skill = proposal.to_skill()
        try:
            registry.save_skill(skill)
            return skill
        except Exception:
            return None


__all__ = [
    "ReplanAction", "ReplanDecision", "TaskReplanner",
    "MAX_RETRY_PER_TASK", "CANDIDATE_MIN_SUCCESS",
    "SkillProposalStatus", "SkillProposal", "SkillProposer",
    "GovernedSkillCommitter",
]
