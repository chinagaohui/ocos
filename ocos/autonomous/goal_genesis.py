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
        """从 EpistemicDrive suggestions 生成 GoalProposal 列表.

        P1-2026-09-10: 防重复 — 同类失败目标在冷却窗口内不重复生成。
        writer 循环就是因为没有防重复: 同一个 writer 探查目标被连续
        生成了几十次，每次都是 sqlite3 not found → dependency_missing →
        SKIP_DEPENDENTS，但新 goal 又生成了。

        防重复规则:
          1. 描述归一化后（去空格/标点/大小写）和近 10 分钟已存在 proposal
             相似度 ≥ 0.8 → 跳过
          2. 同类 source + domain 在近 10 分钟有 ≥3 个 PENDING/APPROVED
             且最终 FAILED 的 proposal → 冷却 10 分钟
          3. 同类 source 在近 10 分钟有硬依赖缺失 (exit 127 / not found)
             失败 → 标记依赖 offline，跳过
        """
        proposals = []
        conn = self._get_conn()

        for s in suggestions:
            # P1: 防重复检查
            if self._is_duplicate(conn, s, domain, source):
                logger.debug(
                    "GoalGenesis deduped: %s — 同类目标近期已存在/连续失败",
                    s[:60])
                continue
            if self._is_cooling_down(conn, s, domain, source):
                logger.debug(
                    "GoalGenesis cooldown: %s — 同类目标连续失败 ≥3",
                    s[:60])
                continue
            # P2c: agent 能力 offline 检查
            if self._agent_capability_offline(conn, s, domain):
                logger.info(
                    "GoalGenesis cap-offline: %s — %s 能力被标记为不可用",
                    s[:60], domain)
                continue

            prop = GoalProposal(description=s, domain=domain, source=source)
            prop.value_score = self._score_value(prop)
            prop.risk_level = self._assess_risk(prop)
            self._persist(prop)
            proposals.append(prop)
        return proposals

    # ── P1-2026-09-10: 防重复 ────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """归一化: 去空格/标点/数字 → 用于相似度比较。"""
        import re
        return re.sub(r"[\s\d_\-.,!?:;，。！？、；：]+", "", text.lower())

    def _is_duplicate(self, conn, desc: str, domain: str, source: str) -> bool:
        """近 10 分钟内已存在相似 proposal（归一化相似度 ≥ 0.8）?"""
        cutoff = self._now_iso(minutes_ago=10)
        try:
            rows = conn.execute(
                "SELECT description FROM goal_proposal "
                "WHERE created_at >= ? AND source = ? AND status IN ('PENDING','APPROVED')",
                (cutoff, source)).fetchall()
        except Exception:
            return False
        norm_new = self._normalize(desc)
        if not norm_new:
            return False
        for (existing,) in rows:
            if not existing:
                continue
            norm_old = self._normalize(existing)
            if norm_old and self._similarity(norm_new, norm_old) >= 0.75:
                return True
        return False

    def _is_cooling_down(self, conn, desc: str, domain: str, source: str) -> bool:
        """近 10 分钟内同类 source 连续失败 ≥3 → 冷却。"""
        cutoff = self._now_iso(minutes_ago=10)
        try:
            # 从 goal_proposal → goals 表连查
            rows = conn.execute(
                """SELECT g.status, g.description, g.metadata
                   FROM goals g
                   WHERE g.source = ? AND g.created_at >= ?
                   ORDER BY g.rowid DESC LIMIT 20""",
                (source, cutoff)).fetchall()
        except Exception:
            return False

        if len(rows) < 3:
            return False

        norm_new = self._normalize(desc)
        recent_fails = 0
        for status, g_desc, g_meta in rows:
            norm_old = self._normalize(g_desc or "")
            if not norm_old:
                continue
            # 语义相似 + 已失败 → 计失败
            if self._similarity(norm_new, norm_old) >= 0.7:
                if status in ("FAILED", "ABORTED"):
                    recent_fails += 1
                elif status == "COMPLETED":
                    # 检查 metadata 里 success 标志
                    try:
                        meta = json.loads(g_meta or "{}") if g_meta else {}
                        if meta.get("success") is False:
                            recent_fails += 1
                    except Exception:
                        pass

        return recent_fails >= 3

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """多维度相似度: Jaccard char 集 + 关键词重叠 + 双向子串包含.

        纯 Jaccard 不够 — 短描述 (如 "探查 writer") 和长描述
        ("探查 writer 在宿主机有 7 个可用工具没试过") Jaccard 只有 0.48,
        但语义几乎相同。
        """
        if not a or not b:
            return 0.0
        set_a, set_b = set(a), set(b)
        union = set_a | set_b
        jaccard = len(set_a & set_b) / len(union) if union else 0.0

        # 子串包含检测: 短串是长串的子串 → 相似度 = 0.8
        if len(a) < len(b):
            substring_hit = a in b
        else:
            substring_hit = b in a
        if substring_hit:
            # 加权: Jaccard 和 子串包含 取 max
            return max(jaccard, 0.8)

        # 关键词重叠检测: 提取 2+ 字高频 token, 匹配数 ≥2 → +0.2
        import re
        tokens_a = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z_]+", a))
        tokens_b = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-z_]+", b))
        if tokens_a and tokens_b:
            overlap = len(tokens_a & tokens_b)
            if overlap >= 2:
                jaccard = max(jaccard, 0.6 + 0.1 * min(overlap - 2, 3))

        return jaccard

    @staticmethod
    def _now_iso(minutes_ago: int = 0) -> str:
        """返回 UTC ISO 时间戳（减 N 分钟）。"""
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()

    def _agent_capability_offline(self, conn, desc: str, domain: str) -> bool:
        """P2b-2026-09-10: 能力 offline 检查 + 自恢复探测.

        逻辑:
          1. belief 表里有 capability_offline 标记 → 被拦截
          2. 但每次拦截都探测一下依赖是否已恢复 (command -v 检测)
          3. 如果依赖恢复了 → 删除 belief 标记 (unlock) → 放行
          4. 探测有 60 秒冷却 (不每次都跑 shell 命令)

        自恢复路径:
          belief "agent[writer]...sqlite3 不可用" → command -v sqlite3 成功
          → DELETE FROM belief WHERE tags LIKE '%capability_offline%'
          → GoalGenesis 放行 writer 目标
        """
        import re
        agent_pattern = re.compile(
            r"\b(writer|researcher|reviewer|planner|executor|exec|reader|critic|learner|curator)\b",
            re.IGNORECASE)
        found_agents = agent_pattern.findall(desc)
        if not found_agents:
            return False

        # 探测冷却 (类级变量，避免每 tick 都 shell)
        if not hasattr(GoalGenesis, "_capability_probe_cooldown"):
            GoalGenesis._capability_probe_cooldown = {}

        for agent in found_agents:
            try:
                rows = conn.execute(
                    """SELECT statement, confidence, tags FROM belief
                       WHERE tags LIKE ? AND confidence <= 0.1""",
                    (f"%\"{agent}\"%",)).fetchall()
            except Exception:
                continue

            for stmt, conf, tags in rows:
                if not (conf <= 0.1 and agent.lower() in stmt.lower()):
                    continue

                # P2b: 探测依赖是否恢复
                now_ts = __import__("time").time()
                cooldown_key = f"{agent}:{stmt[:30]}"
                last_probe = GoalGenesis._capability_probe_cooldown.get(cooldown_key, 0)
                if now_ts - last_probe >= 60:
                    GoalGenesis._capability_probe_cooldown[cooldown_key] = now_ts
                    dep = self._extract_dependency(stmt, tags)
                    if dep and self._probe_dependency_available(dep):
                        # 依赖恢复 → 删除 belief 标记
                        try:
                            conn.execute(
                                "DELETE FROM belief WHERE confidence <= 0.1 AND statement = ?",
                                (stmt,))
                            conn.commit()
                            logger.warning(
                                "P2b-capability-restored: agent[%s] dep='%s' recovered, "
                                "deleted offline belief", agent.lower(), dep)
                            return False  # 放行！
                        except Exception:
                            pass

                logger.info(
                    "capability offline hit: agent[%s] conf=%.1f stmt=%s",
                    agent.lower(), conf, stmt[:80])
                return True
        return False

    @staticmethod
    def _extract_dependency(stmt: str, tags: str) -> str | None:
        """从 belief statement / tags 提取依赖名."""
        import re
        # belief 格式: "agent[writer] 在当前环境因依赖 'sqlite3' 不可用"
        m = re.search(r"依赖\s*['\"](\S+?)['\"]\s*不可用", stmt)
        if m:
            return m.group(1)
        # 从 tags 里找
        try:
            tag_list = json.loads(tags) if tags else []
            for t in tag_list:
                if ":" in t:
                    return t.split(":", 1)[1]
        except Exception:
            pass
        return None

    @staticmethod
    def _probe_dependency_available(dep: str) -> bool:
        """探测依赖是否可用 (shell command -v / python import)."""
        if not dep:
            return False
        try:
            if dep.startswith("python:"):
                module = dep[len("python:"):]
                __import__(module)
                return True
            else:
                # shell command -v
                import subprocess
                result = subprocess.run(
                    ["command", "-v", dep],
                    capture_output=True, timeout=3)
                return result.returncode == 0
        except Exception:
            return False

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

        # Step 4.2: 审计增强 — 每次 approve/reject 写 JSONL
        try:
            from ocos.execution.autonomy import append_audit_record
            append_audit_record({
                "kind": "goal_proposal_approve",
                "proposal_id": proposal.proposal_id,
                "risk_level": proposal.risk_level,
                "status": proposal.status,
                "approval_path": proposal.approval_path,
                "description": proposal.description[:100],
            })
        except Exception:
            pass  # 审计失败不阻塞

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
