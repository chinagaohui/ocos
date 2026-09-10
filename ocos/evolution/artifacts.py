"""EvolutionArtifactStore — OCOS 自进化产物的固定产出仓库.

所有自进化方案、代码补丁、研究报告都通过此 store 入库,
status=PENDING 的产物必须经人工审核 (approve/reject) 后才能进入
下游 knowledge principle 层或 GrowthOptimizer 执行管线。

DB 表 evolution_artifacts 存储元数据 + status.
完整文件内容写到 ~/.ocos/artifacts/{type}/{artifact_id}.md.
人工审核日志写到 ~/.ocos/artifacts/audit.jsonl.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ArtifactType(str, Enum):
    PLAN = "plan"           # 自我优化方案 (LLM 生成)
    PATCH = "patch"         # 代码改动补丁 (GrowthOptimizer)
    REPORT = "report"       # 研究报告 (WebResearcher + LLMTutor 综合)
    EXPERIMENT = "experiment"  # 实验产物 (daemon 自动探索)


class ArtifactStatus(str, Enum):
    PENDING = "pending"       # 待人工审核
    APPROVED = "approved"     # 已批准 → 可沉淀/可执行
    REJECTED = "rejected"     # 已拒绝
    APPLIED = "applied"       # 已落地执行 (patch 被应用)
    SUPERSEDED = "superseded" # 被后续方案替代


@dataclass
class EvolutionArtifact:
    artifact_id: str
    type: ArtifactType
    title: str
    content: str                    # 完整 Markdown 内容
    status: ArtifactStatus = ArtifactStatus.PENDING
    summary: str = ""               # 一句话摘要 (CLI 列表用)
    confidence: float = 0.7
    source_agent: str = ""          # 哪个 agent/渠道产出的
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    risk_level: str = "LOW"         # LOW / MEDIUM / HIGH
    human_review_required: bool = True

    created_at: str = ""
    reviewed_at: str = ""
    reviewer: str = ""
    review_comment: str = ""
    applied_at: str = ""
    supersedes: str = ""            # 替代的旧 artifact_id

    @classmethod
    def new(
        cls,
        type: ArtifactType,
        title: str,
        content: str,
        *,
        summary: str = "",
        confidence: float = 0.7,
        source_agent: str = "",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        risk_level: str = "LOW",
        human_review_required: bool = True,
    ) -> "EvolutionArtifact":
        return cls(
            artifact_id=f"EVO-{uuid.uuid4().hex[:12].upper()}",
            type=type,
            title=title,
            content=content,
            summary=summary or content[:120].replace("\n", " "),
            confidence=confidence,
            source_agent=source_agent,
            tags=tags or [],
            metadata=metadata or {},
            risk_level=risk_level,
            human_review_required=human_review_required,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class EvolutionArtifactStore:
    """自进化产物的固定仓库.

    双写: DB (元数据+status) + 文件系统 (完整 Markdown).
    """

    ARTIFACTS_DIR = Path.home() / ".ocos" / "artifacts"
    AUDIT_LOG = ARTIFACTS_DIR / "audit.jsonl"

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_dirs()
        self._ensure_table()

    # ── 初始化 ──

    def _ensure_dirs(self) -> None:
        for sub in ("plans", "patches", "reports", "experiments"):
            (self.ARTIFACTS_DIR / sub).mkdir(parents=True, exist_ok=True)

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolution_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    summary TEXT,
                    content TEXT,              -- Markdown 全文 (同时也存文件)
                    confidence REAL DEFAULT 0.7,
                    source_agent TEXT,
                    tags TEXT,                 -- JSON array
                    metadata TEXT,             -- JSON object
                    risk_level TEXT DEFAULT 'LOW',
                    human_review_required INTEGER DEFAULT 1,
                    created_at TEXT,
                    reviewed_at TEXT,
                    reviewer TEXT,
                    review_comment TEXT,
                    applied_at TEXT,
                    supersedes TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ── CRUD ──

    def save(self, artifact: EvolutionArtifact) -> None:
        """入库 + 写文件系统."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO evolution_artifacts
                (artifact_id, type, title, status, summary, content, confidence,
                 source_agent, tags, metadata, risk_level, human_review_required,
                 created_at, reviewed_at, reviewer, review_comment, applied_at, supersedes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.artifact_id,
                    artifact.type.value,
                    artifact.title,
                    artifact.status.value,
                    artifact.summary,
                    artifact.content,
                    artifact.confidence,
                    artifact.source_agent,
                    json.dumps(artifact.tags, ensure_ascii=False),
                    json.dumps(artifact.metadata, ensure_ascii=False),
                    artifact.risk_level,
                    1 if artifact.human_review_required else 0,
                    artifact.created_at,
                    artifact.reviewed_at,
                    artifact.reviewer,
                    artifact.review_comment,
                    artifact.applied_at,
                    artifact.supersedes,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # 写文件系统 (固定产出仓库)
        subdir = {
            ArtifactType.PLAN: "plans",
            ArtifactType.PATCH: "patches",
            ArtifactType.REPORT: "reports",
            ArtifactType.EXPERIMENT: "experiments",
        }.get(artifact.type, "plans")

        file_path = self.ARTIFACTS_DIR / subdir / f"{artifact.artifact_id}.md"
        file_path.write_text(artifact._to_markdown())
        logger.info(
            "EvolutionArtifact saved: %s (%s) → %s",
            artifact.artifact_id, artifact.type.value, file_path,
        )

    def get(self, artifact_id: str) -> Optional[EvolutionArtifact]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM evolution_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
            return self._row_to_artifact(row) if row else None
        finally:
            conn.close()

    def list(
        self,
        *,
        status: ArtifactStatus | None = None,
        type: ArtifactType | None = None,
        limit: int = 50,
    ) -> list[EvolutionArtifact]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            sql = "SELECT * FROM evolution_artifacts WHERE 1=1"
            params: list[Any] = []
            if status:
                sql += " AND status = ?"
                params.append(status.value)
            if type:
                sql += " AND type = ?"
                params.append(type.value)
            sql += " ORDER BY rowid DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_artifact(r) for r in rows]
        finally:
            conn.close()

    def review(
        self,
        artifact_id: str,
        decision: ArtifactStatus,
        *,
        reviewer: str = "human",
        comment: str = "",
    ) -> Optional[EvolutionArtifact]:
        """人工审核 — APPROVED / REJECTED. 返回更新后的 artifact."""
        artifact = self.get(artifact_id)
        if artifact is None:
            logger.warning("review: artifact %s not found", artifact_id)
            return None

        artifact.status = decision
        artifact.reviewed_at = datetime.now(timezone.utc).isoformat()
        artifact.reviewer = reviewer
        artifact.review_comment = comment

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """
                UPDATE evolution_artifacts
                SET status=?, reviewed_at=?, reviewer=?, review_comment=?
                WHERE artifact_id=?
                """,
                (decision.value, artifact.reviewed_at, reviewer, comment, artifact_id),
            )
            conn.commit()
        finally:
            conn.close()

        # 审计日志
        audit_entry = {
            "ts": artifact.reviewed_at,
            "artifact_id": artifact_id,
            "decision": decision.value,
            "reviewer": reviewer,
            "comment": comment,
        }
        with open(self.AUDIT_LOG, "a") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

        # 更新文件系统状态头
        self.save(artifact)
        logger.info(
            "EvolutionArtifact %s → %s (reviewer=%s)",
            artifact_id, decision.value, reviewer,
        )
        return artifact

    def mark_applied(self, artifact_id: str) -> None:
        artifact = self.get(artifact_id)
        if artifact is None:
            return
        artifact.status = ArtifactStatus.APPLIED
        artifact.applied_at = datetime.now(timezone.utc).isoformat()
        self.save(artifact)

    def count_pending(self) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM evolution_artifacts WHERE status='pending'"
            ).fetchone()[0]
        finally:
            conn.close()

    # ── 内部 ──

    def _row_to_artifact(self, row: sqlite3.Row) -> EvolutionArtifact:
        d = dict(row)
        return EvolutionArtifact(
            artifact_id=d["artifact_id"],
            type=ArtifactType(d["type"]),
            title=d["title"],
            content=d["content"] or "",
            status=ArtifactStatus(d["status"]),
            summary=d.get("summary", "") or "",
            confidence=d.get("confidence", 0.7) or 0.7,
            source_agent=d.get("source_agent", "") or "",
            tags=json.loads(d.get("tags") or "[]"),
            metadata=json.loads(d.get("metadata") or "{}"),
            risk_level=d.get("risk_level", "LOW") or "LOW",
            human_review_required=bool(d.get("human_review_required", 1)),
            created_at=d.get("created_at", "") or "",
            reviewed_at=d.get("reviewed_at", "") or "",
            reviewer=d.get("reviewer", "") or "",
            review_comment=d.get("review_comment", "") or "",
            applied_at=d.get("applied_at", "") or "",
            supersedes=d.get("supersedes", "") or "",
        )


# ── EvolutionArtifact → Markdown 格式化 ──

def _to_markdown(self: EvolutionArtifact) -> str:
    status_badge = {
        ArtifactStatus.PENDING: "⏳ PENDING",
        ArtifactStatus.APPROVED: "✅ APPROVED",
        ArtifactStatus.REJECTED: "❌ REJECTED",
        ArtifactStatus.APPLIED: "🚀 APPLIED",
        ArtifactStatus.SUPERSEDED: "🔄 SUPERSEDED",
    }.get(self.status, self.status.value)

    risk_badge = {"LOW": "🟢 LOW", "MEDIUM": "🟡 MEDIUM", "HIGH": "🔴 HIGH"}.get(
        self.risk_level, self.risk_level,
    )

    header = f"""# {self.title}

| 字段 | 值 |
|------|-----|
| ID | `{self.artifact_id}` |
| 类型 | `{self.type.value}` |
| 状态 | **{status_badge}** |
| 风险 | {risk_badge} |
| 置信度 | {self.confidence:.2f} |
| 来源 | {self.source_agent or "—"} |
| 标签 | {", ".join(self.tags) or "—"} |
| 需要人工审核 | {"✅ 是" if self.human_review_required else "❌ 否"} |
| 创建时间 | {self.created_at} |
| 审核人 | {self.reviewer or "—"} |
| 审核时间 | {self.reviewed_at or "—"} |
| 审核备注 | {self.review_comment or "—"} |

---

## 摘要

{self.summary}

## 完整内容

{self.content}
"""

    return header


# Monkey-patch EvolutionArtifact 加 _to_markdown
EvolutionArtifact._to_markdown = _to_markdown


__all__ = [
    "EvolutionArtifact",
    "EvolutionArtifactStore",
    "ArtifactType",
    "ArtifactStatus",
]
