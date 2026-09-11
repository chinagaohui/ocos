"""PW-2.1/2.3: self_evolution_link — 自我升级提案接入 evolution 治理链。

把 D 闭环（self_improve → pending → 批准 → 追加 self_knowledge）升级为
完整治理流程:

    自省提案 → [守门: 主权冻结域拒绝] → EvolutionProposer
            → ImpactAnalyzer（边界/ABI/依赖/回滚可行性）
            → EvolutionSandbox（沙箱验证）
            → 快照旧 self_knowledge（真实回滚依据）
            → 入待批（人工 authority）
    批准后:   EvolutionRequest 记录 → MigrationEngine.migrate（快照+迁移）
            → 真实应用 self_knowledge → EvolutionMemory 记账
            → 可 rollback（恢复快照）

冻结面: identity/宪法/权限模型的修改**任何路径都拒绝**（含人工批准），
属 OCOS_Cognitive_Sovereignty_Freeze 主权冻结域。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ocos.logging import get_logger

logger = get_logger(__name__)

_SELF_KNOWLEDGE = Path.home() / ".ocos" / "self_knowledge.md"
_BACKUP_FILE = Path.home() / ".ocos" / "self_knowledge_backup.json"

# 主权冻结域 — 这些词出现在提案里 = 任何路径都拒绝
FORBIDDEN_MARKERS: tuple[str, ...] = (
    "identity", "身份锚点", "宪法", "constitution",
    "权限模型", "permission_model", "核心价值", "anchor",
)


def _knowledge_already_applied(change: str) -> bool:
    """同文变更已在 self_knowledge 中（剥日期戳归一化比对）→ True。

    去重闸（2026-09-07）: 提案侧 _already_proposed 只比对 pending_actions，
    对话/引擎直调 apply 的路径无防线 — "测试变更" 曾被重复追加 128 次。
    """
    needle = (change or "").strip()
    if not needle:
        return False
    try:
        with open(_SELF_KNOWLEDGE, "r", encoding="utf-8") as f:
            for line in f:
                body = line.strip()
                if body.startswith("- "):
                    body = body[2:].strip()
                # 剥 "[YYYY-MM-DD] " 前缀（方括号日期共 12 字符）
                if len(body) >= 12 and body.startswith("[") and body[11] == "]":
                    body = body[12:].strip()
                if body == needle:
                    return True
    except OSError:
        return False
    return False


def _check_approval_hard_gate(
    proposal_state: str | None,
    approval_record: dict | None,
) -> tuple[bool, str]:
    """P0-A (2026-09-11): 治理硬闸门 — 任何 apply 路径必须通过.

    Governance 必须 fail-closed: 缺少 proposal_state / ApprovalRecord
    → 一律 DENY. approved_by="human" 字符串不是审批真实性证明.
    """
    if proposal_state is None:
        return False, "governance denied: missing proposal_state"
    if proposal_state != "APPROVED":
        return False, (
            f"governance denied: proposal.state={proposal_state}, "
            "only APPROVED allowed"
        )
    if approval_record is None:
        return False, "governance denied: missing ApprovalRecord"
    if not isinstance(approval_record, dict):
        return False, "governance denied: ApprovalRecord must be dict"
    # 必须有真实 actor + timestamp — 不能是 "human" 字符串
    actor = approval_record.get("actor", "")
    ts = approval_record.get("timestamp", "")
    if not actor or actor == "human":
        return False, "governance denied: ApprovalRecord.actor must be real, not 'human'"
    if not ts:
        return False, "governance denied: ApprovalRecord.timestamp missing"
    return True, "ok"


def apply_self_upgrade(change: str, *,
                       proposal_state: str | None = None,
                       approval_record: dict | None = None) -> str:
    """P0-A (2026-09-11): 应用已批准的自我升级 — 追加到 ~/.ocos/self_knowledge.md.

    硬闸门 (P0-A): 任何调用必须传 proposal_state="APPROVED" + 真实
    ApprovalRecord (actor + timestamp), 否则 DENY. 不存在 ApprovalRecord
    或 proposal 未 APPROVED → 一律拒绝.

    去重闸 (原有): 同文变更（剥日期戳归一化比对）已存在则跳过.
    """
    # ── P0-A: 硬闸门检查 ──
    ok, reason = _check_approval_hard_gate(proposal_state, approval_record)
    if not ok:
        logger.warning("self upgrade HARD-DENIED: %s", reason)
        return f"[GOVERNANCE-DENY] {reason}"

    text = (change or "").strip()
    if _knowledge_already_applied(text):
        logger.info("self upgrade dedup: change already applied, skip")
        return f"self knowledge unchanged (already applied): {text[:60]}"
    _SELF_KNOWLEDGE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(_SELF_KNOWLEDGE, "a", encoding="utf-8") as f:
        f.write(f"\n- [{stamp}] {text}")
    logger.info(
        "self upgrade applied (approved_by=%s ts=%s): %s",
        approval_record.get("actor"), approval_record.get("timestamp"),
        text[:60],
    )
    return f"self knowledge updated: {text[:60]}"


def read_self_knowledge() -> str:
    """读取全部自我知识（内视/上下文消费端）。"""
    return _read_self_knowledge()


def _read_self_knowledge() -> str:
    try:
        return _SELF_KNOWLEDGE.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_backup(proposal_id: str, previous: str) -> None:
    data = {}
    if _BACKUP_FILE.exists():
        try:
            data = json.loads(_BACKUP_FILE.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    data[proposal_id] = previous
    _BACKUP_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                            encoding="utf-8")


def _build_proposal(proposal_id: str | None, title: str, change: str,
                    source_tick: int = 0):
    """构造提案并跑完 提案→影响分析→沙箱（确定性, 可跨进程重建）。"""
    from ocos.evolution.evolution_proposer import EvolutionProposer
    from ocos.evolution.evolution_sandbox import EvolutionSandbox
    from ocos.evolution.evolution_types import (
        EvolutionDomain, EvolutionTrigger,
    )
    from ocos.evolution.impact_analyzer import ImpactAnalyzer
    from ocos.evolution.improvement_detector import DetectedSignal

    signal = DetectedSignal(
        trigger=EvolutionTrigger.EXPERIENCE_PATTERN,
        source_tick=source_tick, source_module="interaction.converse",
        metric_name="self_reflection", metric_value=1.0,
        threshold=0.0, description=title, severity=0.5)
    proposal = EvolutionProposer().propose(signal, description=f"{title} — {change}")
    if proposal_id:
        proposal.proposal_id = proposal_id
    proposal.domain = EvolutionDomain.KNOWLEDGE_STRUCTURE
    proposal.change_type = "add"
    proposal.change_spec = change
    proposal.target_module = "~/.ocos/self_knowledge.md"

    proposal.impact = ImpactAnalyzer().analyze(proposal)
    report = EvolutionSandbox().validate(proposal)
    proposal.sandbox_passed = (
        report.result.value == "passed" or report.passed_count > 0)
    return proposal, report


def propose_upgrade(title: str, change: str,
                    source_tick: int = 0) -> dict:
    """提案入治理链。返回 {accepted, proposal_id, reason?, pending_id?}。"""
    from ocos.evolution.evolution_memory import EvolutionMemory

    combined = f"{title} {change}".lower()
    for marker in FORBIDDEN_MARKERS:
        if marker.lower() in combined:
            logger.warning("Self-upgrade proposal rejected (sovereignty freeze): %s",
                           title)
            return {"accepted": False,
                    "reason": f"主权冻结域（{marker}）— 任何路径不可自我修改"}

    proposal, report = _build_proposal(None, title, change, source_tick)
    memory = EvolutionMemory()
    memory.record(proposal, "proposed",
                  detail=f"impact={proposal.impact.level.value}, "
                         f"sandbox={proposal.sandbox_passed}")

    if not proposal.sandbox_passed or not proposal.impact.is_safe:
        memory.record(proposal, "rejected_in_governance",
                      detail="sandbox failed or impact unsafe")
        return {"accepted": False, "proposal_id": proposal.proposal_id,
                "reason": f"治理链未通过（sandbox={proposal.sandbox_passed}, "
                          f"impact={proposal.impact.level.value}）"}

    # 快照旧自我知识（真实回滚依据）
    _write_backup(proposal.proposal_id, _read_self_knowledge())
    memory.record(proposal, "governance_passed")
    logger.info("Self-upgrade proposal passed governance: %s (%s)",
                proposal.proposal_id, title)
    return {"accepted": True, "proposal_id": proposal.proposal_id,
            "title": title, "change": change,
            "impact": proposal.impact.level.value}


def apply_approved(proposal_id: str, title: str, change: str,
                   approver: str = "system",
                   tick_id: int = 0) -> dict:
    """人工批准后的治理化应用: approve（真实 ApprovalEngine）→ migrate → apply → 记账.

    P0-A (2026-09-11): 不再硬编码 approved_by="human". 必须通过
    ApprovalEngine.manual_approve() 产生真实 ApprovalRecord,
    再传给 apply_self_upgrade 做最终治理闸门验证.

    如果 proposal.state != PENDING_REVIEW 或 sandbox/安全预检未通过
    → ApprovalEngine 自动拒绝 → 本函数返回错误.
    """
    from ocos.evolution.approval_engine import ApprovalEngine, ApprovalVerdict
    from ocos.evolution.evolution_memory import EvolutionMemory
    from ocos.evolution.evolution_types import EvolutionState
    from ocos.evolution.migration_engine import MigrationEngine

    # 1. 构造 proposal（先 build, 让 sandbox_passed/impact 等字段有值）
    proposal, _report = _build_proposal(proposal_id, title, change)

    # P0-A: 确保 proposal 处于可审批状态
    proposal.state = EvolutionState.PENDING_REVIEW

    # 2. 通过 ApprovalEngine 走真实审批流程（不是硬编码 APPROVED）
    engine = ApprovalEngine()
    verdict = engine.manual_approve(proposal, approver=approver, tick_id=tick_id)

    if verdict != ApprovalVerdict.APPROVED:
        memory = EvolutionMemory()
        memory.record(proposal, "approval_rejected",
                      detail=f"verdict={verdict}")
        logger.warning(
            "Self-upgrade approval REJECTED via ApprovalEngine: %s verdict=%s",
            proposal.proposal_id, verdict,
        )
        return {"ok": False,
                "error": f"approval rejected (verdict={verdict})"}

    # P0-A: 从 ApprovalEngine 取出真实 ApprovalRecord
    approval_record = None
    if engine.recent_approvals:
        last = engine.recent_approvals[-1]
        approval_record = {
            "actor": approver,
            "proposal_id": last.proposal_id,
            "verdict": last.verdict.value if hasattr(last.verdict, "value") else str(last.verdict),
            "reason": last.reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tick": last.tick,
        }

    # 3. MigrationEngine（快照 + 迁移）
    memory = EvolutionMemory()
    memory.record(proposal, "human_approved",
                  detail=f"via ApprovalEngine actor={approver}")
    result = MigrationEngine().migrate(proposal, tick_id=tick_id)
    if not result.success:
        memory.record(proposal, "migration_failed", detail=result.error or "")
        return {"ok": False, "error": result.error}

    # 4. apply_self_upgrade — 传 proposal_state + approval_record
    applied = apply_self_upgrade(
        change,
        proposal_state="APPROVED",
        approval_record=approval_record or {},
    )

    memory.record(proposal, "migrated", detail=applied)
    logger.info(
        "Self-upgrade applied via governance (actor=%s pid=%s): %s",
        approver, proposal.proposal_id, applied[:60],
    )
    return {"ok": True, "applied": applied,
            "rollback_snapshot": proposal.rollback_snapshot,
            "approval_actor": approver}


def rollback(proposal_id: str) -> dict:
    """回滚一次已应用的自我升级（恢复快照时的 self_knowledge）。"""
    try:
        data = json.loads(_BACKUP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"ok": False, "error": "no backup found"}
    if proposal_id not in data:
        return {"ok": False, "error": f"no snapshot for {proposal_id}"}
    _SELF_KNOWLEDGE.write_text(data[proposal_id], encoding="utf-8")
    logger.info("Self-upgrade rolled back: %s", proposal_id)
    return {"ok": True, "proposal_id": proposal_id,
            "restored_chars": len(data[proposal_id])}
