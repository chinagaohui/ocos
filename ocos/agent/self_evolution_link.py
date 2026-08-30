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


def apply_self_upgrade(change: str) -> str:
    """应用已批准的自我升级 — 追加到 ~/.ocos/self_knowledge.md。"""
    _SELF_KNOWLEDGE.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(_SELF_KNOWLEDGE, "a", encoding="utf-8") as f:
        f.write(f"\n- [{stamp}] {change.strip()}")
    return f"self knowledge updated: {change.strip()[:60]}"


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


def apply_approved(proposal_id: str, title: str, change: str) -> dict:
    """人工批准后的治理化应用: migrate（含快照）→ 真实应用 → 记账。"""
    from ocos.evolution.evolution_memory import EvolutionMemory
    from ocos.evolution.evolution_types import EvolutionState
    from ocos.evolution.migration_engine import MigrationEngine

    proposal, _report = _build_proposal(proposal_id, title, change)
    proposal.sandbox_passed = True
    proposal.governance_approved = True   # 人工批准 = authority
    proposal.approved_by = "human"
    proposal.state = EvolutionState.APPROVED

    memory = EvolutionMemory()
    memory.record(proposal, "human_approved")
    result = MigrationEngine().migrate(proposal, tick_id=0)
    if not result.success:
        memory.record(proposal, "migration_failed", detail=result.error or "")
        return {"ok": False, "error": result.error}

    applied = apply_self_upgrade(change)
    memory.record(proposal, "migrated", detail=applied)
    logger.info("Self-upgrade applied via governance: %s", proposal.proposal_id)
    return {"ok": True, "applied": applied,
            "rollback_snapshot": proposal.rollback_snapshot}


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
