"""ReflectionEngine — 双层反思回环 (Self-Reflection + Gap Resolution).

挂在 KnowledgeRegistry 旁边: 每次 UnifiedIngestor 批量摄入后,
对这批新知识做结构化反思, 输出反思报告 → evolution_artifacts(PENDING).

借鉴 LLM Agent 的 self-reflection + self-improving 循环思想,
以及 SOAR/CLARION 的元认知层 (让 GrowthOptimizer 从单纯护栏
变成学习策略调节器).

双回环:
  Loop 1 (Self-Reflection): 这批新知识和已有知识是什么关系?
    → 填补了哪些预测缺口? 和已有知识是否冲突?
    → 值得深入学习的方向是什么?
  Loop 2 (Gap-Driven): 这批摄入是否缩小了 PredictionGapTracker 的 gap?
    → 未消除的 gap → 升级为下一轮 EpistemicDrive 种子

触发条件:
  - 每 ingest_batch_threshold (默认 10) 条知识后触发一次
  - 或者 EpistemicDrive.curiosity 变化时
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReflectionBatch:
    """一批待反思的新知识."""
    knowledge_ids: list[str]
    statements: list[str]
    source_channels: list[str]  # WEB_RESEARCH / LLM_QA / EXPERIENCE
    total_count: int


@dataclass
class ReflectionReport:
    """反思报告 — 结构化输出."""
    batch_size: int
    timestamp: str
    knowledge_ids_examined: list[str]

    # Loop 1 输出
    fills_gaps: list[str]          # 填补的预测缺口 (gap_id)
    conflicts: list[str]           # 和已有知识冲突的条目
    deepen_topics: list[str]       # 值得深入学习的方向

    # Loop 2 输出
    gaps_resolved: int             # 本次消除的 gap 数
    gaps_remaining: list[str]      # 未消除的 gap_ids (EpistemicDrive 种子)

    # 质量评估
    high_quality_ids: list[str]    # 高质量知识 (建议沉淀到 principle)
    low_quality_ids: list[str]     # 低质量知识 (建议过滤)

    def to_markdown(self) -> str:
        """转为 Markdown 写入 evolution_artifacts."""
        lines = [
            "# Reflection Report (Self-Reflection + Gap Resolution)",
            "",
            f"- Batch size: {self.batch_size}",
            f"- Generated at: {self.timestamp}",
            f"- Knowledge examined: {len(self.knowledge_ids_examined)}",
            "",
            "## Loop 1: Self-Reflection",
            "",
        ]
        if self.fills_gaps:
            lines.append("### 填补的预测缺口")
            for g in self.fills_gaps:
                lines.append(f"- ✅ {g}")
            lines.append("")
        if self.conflicts:
            lines.append("### ⚠️ 与已有知识冲突")
            for c in self.conflicts:
                lines.append(f"- ❓ {c}")
            lines.append("")
        if self.deepen_topics:
            lines.append("### 🎯 值得深入学习")
            for t in self.deepen_topics:
                lines.append(f"- 📚 {t}")
            lines.append("")
        lines.append("## Loop 2: Gap Resolution")
        lines.append("")
        lines.append(f"- Gaps resolved this batch: **{self.gaps_resolved}**")
        lines.append(f"- Gaps remaining (defer to next EpistemicDrive): {len(self.gaps_remaining)}")
        if self.gaps_remaining:
            for g in self.gaps_remaining[:5]:
                lines.append(f"- 🔴 {g}")
        lines.append("")
        if self.high_quality_ids:
            lines.append(f"## ✨ High Quality ({len(self.high_quality_ids)})")
        if self.low_quality_ids:
            lines.append(f"## 🗑️ Low Quality ({len(self.low_quality_ids)})")
        return "\n".join(lines)


class ReflectionEngine:
    """双层反思回环引擎.

    Args:
        db_path: OCOS DB 路径
        ingest_batch_threshold: 每多少条知识触发一次反思
        auto_save: True=反思报告自动写 evolution_artifacts(PENDING)
    """

    def __init__(
        self,
        db_path: str,
        ingest_batch_threshold: int = 10,
        auto_save: bool = True,
    ):
        self._db_path = db_path
        self._threshold = ingest_batch_threshold
        self._auto_save = auto_save
        self._pending_buffer: list[dict[str, Any]] = []

    # ── Buffer management ──

    def add_batch(self, knowledge_ids: list[str]) -> Optional[ReflectionReport]:
        """摄入一批新知识 — 达到 threshold 就触发反思.

        Returns: ReflectionReport 或 None (还没达到 threshold)
        """
        # 拉这批知识的完整内容
        batch = self._load_knowledge(knowledge_ids)
        if not batch:
            return None

        self._pending_buffer.extend([
            {
                "id": kid,
                "statement": stmt,
                "channel": ch,
            }
            for kid, stmt, ch in zip(
                batch.knowledge_ids, batch.statements, batch.source_channels,
            )
        ])

        if len(self._pending_buffer) >= self._threshold:
            report = self._reflect()
            self._pending_buffer.clear()
            return report
        return None

    def reflect_now(self) -> Optional[ReflectionReport]:
        """强制触发一次反思 (不等 threshold)."""
        if not self._pending_buffer:
            return None
        report = self._reflect()
        self._pending_buffer.clear()
        return report

    # ── 核心反思逻辑 ──

    def _reflect(self) -> ReflectionReport:
        """对 buffer 里的知识做 LLM 反思 + 与 PredictionGapTracker 比对."""
        buffer = self._pending_buffer
        now = datetime.now(timezone.utc).isoformat()

        # 构建报告骨架 — 先用规则引擎填充基础数据
        report = ReflectionReport(
            batch_size=len(buffer),
            timestamp=now,
            knowledge_ids_examined=[b["id"] for b in buffer],
            fills_gaps=[],
            conflicts=[],
            deepen_topics=[],
            gaps_resolved=0,
            gaps_remaining=[],
            high_quality_ids=[b["id"] for b in buffer],  # 默认全部高质量
            low_quality_ids=[],
        )

        # Loop 1 + Loop 2: 尝试 LLM 反思
        llm_output = self._run_llm_reflect(buffer)
        if llm_output:
            report.fills_gaps = llm_output.get("fills_gaps", [])
            report.conflicts = llm_output.get("conflicts", [])
            report.deepen_topics = llm_output.get("deepen_topics", [])
            report.high_quality_ids = llm_output.get("high_quality_ids", report.high_quality_ids)
            report.low_quality_ids = llm_output.get("low_quality_ids", [])

        # Loop 2: PredictionGapTracker 比对
        gap_info = self._resolve_gaps(buffer)
        report.gaps_resolved = gap_info["resolved"]
        report.gaps_remaining = gap_info["remaining"]

        # 自动存 evolution_artifacts (PENDING)
        if self._auto_save:
            self._save_as_artifact(report)

        logger.info(
            "ReflectionEngine: batch=%d fills=%d conflicts=%d deepen=%d "
            "gaps_resolved=%d gaps_remaining=%d",
            report.batch_size, len(report.fills_gaps),
            len(report.conflicts), len(report.deepen_topics),
            report.gaps_resolved, len(report.gaps_remaining),
        )

        # 若有 deepen_topics — 写回 EpistemicDrive 种子
        if report.deepen_topics:
            self._seed_epistemic_drive(report.deepen_topics)

        return report

    def _run_llm_reflect(self, buffer: list[dict]) -> dict:
        """用 LLMTutor 做结构化反思. 返回 JSON dict."""
        try:
            from ocos.engines.text_generator import TextGenerator

            tg = TextGenerator()
            if not tg.available:
                return {}

            statements_text = "\n".join(
                f"- [{b['id']}] ({b['channel']}) {b['statement'][:100]}"
                for b in buffer[:15]  # 限制长度
            )

            prompt = f"""你是 OCOS 数字生命的认知反思引擎。
下面是 OCOS 最近摄入的 {len(buffer)} 条新知识。

{statements_text}

请对这批知识做结构化反思, 输出 JSON:
{{
  "fills_gaps": ["填补的预测缺口描述 (自然语言)"],
  "conflicts": ["与已有知识冲突的条目"],
  "deepen_topics": ["值得深入学习的方向"],
  "high_quality_ids": ["高质量知识 id 列表"],
  "low_quality_ids": ["低质量知识 id 列表 (建议过滤)"]
}}

注意: 只输出 JSON, 不要解释。如果某列表为空就返回空数组。
"""
            raw = tg.generate(prompt, system_prompt="你是严谨的认知分析师,只输出 JSON")
            # 提取 JSON (LLM 可能用 ```json 包裹)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(raw)
        except Exception as e:
            logger.debug("LLM reflect failed: %s", e)
            return {}

    def _resolve_gaps(self, buffer: list[dict]) -> dict:
        """Loop 2: 和 PredictionGapTracker 比对 — 哪些 gap 被消除了."""
        result = {"resolved": 0, "remaining": []}
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker

            tracker = PredictionGapTracker(db_path=self._db_path)
            gaps = tracker.get_recent_gaps(limit=10)

            for gap in gaps:
                target = getattr(gap, "target_pattern", "") or ""
                resolved = False
                for b in buffer:
                    if target and target in b["statement"]:
                        resolved = True
                        break
                if resolved:
                    result["resolved"] += 1
                else:
                    gap_id = getattr(gap, "gap_id", None) or str(getattr(gap, "id", ""))
                    if gap_id:
                        result["remaining"].append(gap_id)
        except Exception:
            pass
        return result

    def _save_as_artifact(self, report: ReflectionReport) -> None:
        """反思报告 → evolution_artifacts(PENDING) — 等人工审核."""
        try:
            from ocos.evolution.artifacts import (
                EvolutionArtifact, ArtifactType, EvolutionArtifactStore,
            )

            store = EvolutionArtifactStore(self._db_path)
            art = EvolutionArtifact.new(
                type=ArtifactType.REPORT,
                title=f"Reflection Report (batch={report.batch_size})",
                content=report.to_markdown(),
                summary=(
                    f"reflect {report.batch_size} items: "
                    f"fills={len(report.fills_gaps)} conflicts={len(report.conflicts)} "
                    f"deepen={len(report.deepen_topics)} "
                    f"gaps_resolved={report.gaps_resolved} remaining={len(report.gaps_remaining)}"
                ),
                confidence=0.75,
                source_agent="reflection_engine",
                tags=["reflection", "double_loop", "pending_review"],
                risk_level="MEDIUM",
                human_review_required=True,
            )
            store.save(art)
        except Exception as e:
            logger.debug("ReflectionEngine save artifact failed: %s", e)

    def _seed_epistemic_drive(self, topics: list[str]) -> None:
        """deepen_topics → EpistemicDrive suggest_explore 种子."""
        try:
            c = sqlite3.connect(self._db_path)
            c.execute(
                "CREATE TABLE IF NOT EXISTS reflection_seed_topics ("
                "topic TEXT, source TEXT, created_at TEXT, used INTEGER)"
            )
            now = datetime.now(timezone.utc).isoformat()
            for t in topics:
                c.execute(
                    "INSERT INTO reflection_seed_topics VALUES (?,?,?,0)",
                    (t, "reflection", now),
                )
            c.commit()
            c.close()
            logger.info(
                "ReflectionEngine seeded %d topics → reflection_seed_topics",
                len(topics),
            )
        except Exception as e:
            logger.debug("seed_epistemic_drive failed: %s", e)

    def _load_knowledge(self, ids: list[str]) -> Optional[ReflectionBatch]:
        """从 DB 拉知识详情."""
        if not ids:
            return None
        try:
            c = sqlite3.connect(self._db_path)
            placeholders = ",".join("?" * len(ids))
            rows = c.execute(
                f"SELECT rowid, statement, scope_domain FROM knowledge "
                f"WHERE rowid IN ({placeholders})", ids
            ).fetchall()
            c.close()
            if not rows:
                return None
            return ReflectionBatch(
                knowledge_ids=[str(r[0]) for r in rows],
                statements=[r[1] or "" for r in rows],
                source_channels=[r[2] or "unknown" for r in rows],
                total_count=len(rows),
            )
        except Exception as e:
            logger.debug("load_knowledge failed: %s", e)
            return None


__all__ = ["ReflectionEngine", "ReflectionBatch", "ReflectionReport"]
