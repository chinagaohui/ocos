"""ocos/autonomous/goal_genesis.py — GoalGenesis 提案引擎 (P1 宪法修正案).

## 设计原则

现有 GoalOriginLevel 枚举已有 SELF 值（Phase 25 放开），无需修改枚举。
本引擎在 **Goal 创建之前** 加一层 GoalProposal 中间层：

  EpistemicDrive.suggest_*()
    → GoalGenesis.produce() → [GoalProposal]
    → GoalGenesis.approve() → 分级批准 (LOW/MEDIUM auto, HIGH reject)
    → GoalGenesis.to_goal() → GoalStore.save()  (origin_level=SELF, authority=PROPOSAL)
    → DB goal_proposal 审计表可追溯

分级批准通道:
  LOW    → 自动批准 (approval_path="auto")
  MEDIUM → 自动批准 + logger.info (approval_path="auto")
  HIGH   → 拒绝 (approval_path="rejected") + 审计日志

## 与现有代码的关系

- 不修改 GoalSource (deprecated) 枚举
- 不修改 GoalOriginLevel / GoalAuthority 枚举
- 不修改 GoalStore.save() 签名（只是多传一个 authority=PROPOSAL）
- 不修改 validator 的 GoalSource hard check（SELF goal 不走 validator）
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# 数据契约
# ═══════════════════════════════════════════════════════════════════════════

class ProposalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class RiskLevel(str, Enum):
    LOW = "LOW"          # 不涉及权限/文件写/SelfModification
    MEDIUM = "MEDIUM"    # 涉及搜索/调研但不改代码
    HIGH = "HIGH"        # 涉及 SelfModification / 文件写权限


class ApprovalPath(str, Enum):
    AUTO = "auto"
    REQUESTED = "requested"
    REJECTED = "rejected"


@dataclass
class GoalProposal:
    """Goal 提案中间层 — 宪法修正案要求的可审计层."""

    description: str
    domain: str
    source: str = "epistemic"
    value_score: float = 0.5
    risk_level: str = "LOW"
    required_resources: list = field(default_factory=list)

    # 运行时填充
    proposal_id: str = ""
    status: str = "PENDING"
    approval_path: str = ""
    approved_at: Optional[str] = None
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.proposal_id:
            self.proposal_id = "PROP-" + hashlib.sha1(
                (self.description + self.domain + self.source).encode("utf-8")
            ).hexdigest()[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_row(self) -> tuple:
        return (
            self.proposal_id, self.description, self.domain, self.source,
            self.value_score, self.risk_level, self.status, self.approval_path,
            self.approved_at, self.created_at,
            json.dumps({"required_resources": self.required_resources, **self.metadata})
                if (self.required_resources or self.metadata) else None,
        )

    @classmethod
    def from_row(cls, row: tuple) -> "GoalProposal":
        (pid, desc, domain, source, vs, rl, st, ap, aa, ca, meta_json) = row
        meta = json.loads(meta_json) if meta_json else {}
        return cls(
            description=desc, domain=domain, source=source,
            value_score=vs, risk_level=rl,
            required_resources=meta.pop("required_resources", []),
            proposal_id=pid, status=st, approval_path=ap,
            approved_at=aa, created_at=ca, metadata=meta,
        )


# ═══════════════════════════════════════════════════════════════════════════
# GoalGenesis 引擎
# ═══════════════════════════════════════════════════════════════════════════

class GoalGenesis:
    """GoalProposal 生成 + 分级批准."""

    def __init__(self, db_path: Optional[str] = None, conn: Optional[sqlite3.Connection] = None):
        self._db_path = db_path
        self._conn = conn
        self._ensure_table()

    # ── DB ────────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        if not self._db_path:
            raise ValueError("GoalGenesis requires db_path or conn")
        return sqlite3.connect(self._db_path)

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_proposal (
                proposal_id    TEXT PRIMARY KEY,
                description    TEXT NOT NULL,
                domain         TEXT,
                source         TEXT,
                value_score    REAL DEFAULT 0.5,
                risk_level     TEXT DEFAULT 'LOW',
                status         TEXT DEFAULT 'PENDING',
                approval_path  TEXT,
                approved_at    TEXT,
                created_at     TEXT NOT NULL,
                metadata_json  TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gp_status ON goal_proposal(status)"
        )
        conn.commit()

    def _persist(self, proposal: GoalProposal) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO goal_proposal
                (proposal_id, description, domain, source, value_score,
                 risk_level, status, approval_path, approved_at, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            proposal.to_row(),
        )
        conn.commit()

    # ── 核心方法 ────────────────────────────────────────────────────────

    def produce(
        self,
        suggestions: list[str],
        domain: str = "",
        source: str = "epistemic",
    ) -> list[GoalProposal]:
        """从 EpistemicDrive suggestions 生成 GoalProposal 列表."""
        proposals = []
        for s in suggestions:
            prop = GoalProposal(description=s, domain=domain, source=source)
            prop.value_score = self._score_value(prop)
            prop.risk_level = self._assess_risk(prop)
            self._persist(prop)
            proposals.append(prop)
        return proposals

    def _score_value(self, proposal: GoalProposal) -> float:
        """价值评分 = f(不确定性关键词, 历史成功率) — 当前启发式."""
        desc = proposal.description.lower()
        score = 0.5  # 基线
        if any(kw in desc for kw in ["调研", "research", "学习", "learn", "explore", "unknown", "gap", "不明"]):
            score += 0.2
        if any(kw in desc for kw in ["修复", "fix", "repair", "problem", "bug"]):
            score += 0.15
        if any(kw in desc for kw in ["安全", "security", "audit", "风险"]):
            score += 0.15
        # 可加: 从 goal_proposal 历史看同类 domain 的完成率
        return round(min(score, 1.0), 3)

    def _assess_risk(self, proposal: GoalProposal) -> str:
        """风险评估 = g(description 关键词, required_resources)."""
        desc = proposal.description.lower()
        resources = proposal.required_resources
        high_keywords = ["self_modification", "self-mod", "code_write", "修改代码", "修改文件"]
        medium_keywords = ["search", "research", "调研", "fetch", "download"]

        if any(kw in desc for kw in high_keywords) or "self_modification" in resources:
            return RiskLevel.HIGH.value
        if any(kw in desc for kw in medium_keywords):
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value

    def approve(self, proposal: GoalProposal) -> GoalProposal:
        """分级批准通道 (核心宪法修正案逻辑)."""
        if proposal.risk_level == RiskLevel.HIGH.value:
            proposal.status = ProposalStatus.REJECTED.value
            proposal.approval_path = ApprovalPath.REJECTED.value
            logger.warning(
                "GoalGenesis REJECTED (HIGH risk): %s — %s",
                proposal.proposal_id, proposal.description[:60],
            )
        elif proposal.risk_level in (RiskLevel.LOW.value, RiskLevel.MEDIUM.value):
            proposal.status = ProposalStatus.APPROVED.value
            proposal.approval_path = ApprovalPath.AUTO.value
            proposal.approved_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                "GoalGenesis APPROVED (%s): %s — %s",
                proposal.risk_level, proposal.proposal_id, proposal.description[:60],
            )
        self._persist(proposal)
        return proposal

    def to_goal(self, proposal: GoalProposal, goal_store: Any) -> Optional[str]:
        """proposal → GoalStore.save() — origin_level=SELF, authority=PROPOSAL."""
        if proposal.status != ProposalStatus.APPROVED.value:
            return None
        import uuid
        goal_id = f"GOAL-PROP-{uuid.uuid4().hex[:8].upper()}"
        goal_store.save(
            goal_id=goal_id,
            level="STRATEGIC",
            status="PENDING",
            description=proposal.description,
            source="goal_genesis",
            source_id=proposal.proposal_id,
            metadata={"proposal_id": proposal.proposal_id, "value_score": proposal.value_score,
                      "risk_level": proposal.risk_level},
            origin_level="SELF",       # GoalOriginLevel.SELF
            authority="PROPOSAL",      # GoalAuthority.PROPOSAL (刚定义的新 authority)
        )
        logger.info("GoalGenesis → Goal: %s from proposal %s", goal_id, proposal.proposal_id)
        return goal_id

    # ── 查询 ────────────────────────────────────────────────────────────

    def get_pending(self) -> list[GoalProposal]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM goal_proposal WHERE status='PENDING' ORDER BY created_at DESC LIMIT 50"
        ).fetchall()
        return [GoalProposal.from_row(r) for r in rows]

    def mark_completed(self, proposal_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE goal_proposal SET status='COMPLETED' WHERE proposal_id=?",
            (proposal_id,),
        )
        conn.commit()

    def stats(self) -> dict:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM goal_proposal").fetchone()[0]
        by_status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM goal_proposal GROUP BY status"
        ).fetchall()}
        by_risk = {r[0]: r[1] for r in conn.execute(
            "SELECT risk_level, COUNT(*) FROM goal_proposal GROUP BY risk_level"
        ).fetchall()}
        return {"total": total, "by_status": by_status, "by_risk": by_risk}
