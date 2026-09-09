"""ExperienceExtractor — 任务经验提取适配层.

这是三个渠道中唯一一个"内部渠道" — 从 EpisodeStore + FailureDiagnoser
提取任务执行经验，产出 ExperienceArtifact → 喂给 UnifiedIngestor.

和另外两个渠道的区别:
    - WebResearcher / LLMTutor = 外部输入
    - ExperienceExtractor = 内部执行结果 → 归纳经验教训

实际上 OCOS 已经有 FailureDiagnoser + LessonsSynthesizer 在 dream 管线里
做类似的事（Phase B 任务经验提取）。这个渠道的作用是把它们的产出
也走 UnifiedIngestor 统一入口，从而让"经验教训"和"外部知识"沉淀到
同一套 KnowledgeRegistry + BeliefStore。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.learning.unified_ingestor import IngestArtifact, SourceChannel

logger = logging.getLogger(__name__)


@dataclass
class ExperienceArtifact:
    """从任务执行中提取的经验/教训."""

    goal_description: str
    action: str
    success: bool
    lessons: list[str] = field(default_factory=list)  # 经验教训文本
    failure_cause: str = ""  # 失败原因分类（FailureDiagnoser 给的）
    context: str = ""  # 任务上下文摘要
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_ingest_artifacts(self) -> list[IngestArtifact]:
        arts: list[IngestArtifact] = []

        # 1. 失败教训（最有价值 — 因为成功的经验已经在 belief 里了）
        if not self.success and self.lessons:
            for lesson in self.lessons:
                if not lesson or len(lesson.strip()) < 10:
                    continue
                arts.append(IngestArtifact(
                    channel=SourceChannel.EXPERIENCE,
                    content=lesson.strip()[:500],
                    title=f"失败教训: {self.goal_description[:60]}",
                    confidence=0.7,  # 自己的经验 = 高可信
                    tags=["experience", "failure", self.failure_cause[:20]],
                    knowledge_type="lesson",
                    metadata={
                        "goal": self.goal_description,
                        "action": self.action,
                        "failure_cause": self.failure_cause,
                    },
                ))

        # 2. 成功经验（有反事实的才值得）
        if self.success and self.lessons:
            for lesson in self.lessons:
                if not lesson or len(lesson.strip()) < 15:
                    continue
                arts.append(IngestArtifact(
                    channel=SourceChannel.EXPERIENCE,
                    content=lesson.strip()[:500],
                    title=f"成功经验: {self.goal_description[:60]}",
                    confidence=0.6,
                    tags=["experience", "success"],
                    knowledge_type="procedure",
                    metadata={
                        "goal": self.goal_description,
                        "action": self.action,
                    },
                ))

        return arts


class ExperienceExtractor:
    """任务经验提取.

    依赖 EpisodeStore（可选）— 从 episode 表读 goal_result / failure_lesson.
    依赖 FailureDiagnoser（可选）— 给失败原因分类.
    """

    def __init__(
        self,
        episode_store: Optional[Any] = None,
        db_path: Optional[str] = None,
    ):
        self._episode_store = episode_store
        self._db_path = db_path

    def extract_recent(self, days: int = 1, limit: int = 20) -> list[ExperienceArtifact]:
        """提取最近 N 天的经验.

        主要从 goal_result / failure_lesson 类型的 episode 提取.
        """
        artifacts: list[ExperienceArtifact] = []
        episodes = self._get_recent_episodes(days, limit)

        for ep in episodes:
            try:
                art = self._episode_to_artifact(ep)
                if art is not None:
                    artifacts.append(art)
            except Exception as e:
                logger.debug("ExperienceExtractor skip episode: %s", e)

        return artifacts

    # ── helpers ─────────────────────────────────────────────────────────

    def _get_recent_episodes(self, days: int, limit: int) -> list[Any]:
        """从 EpisodeStore 或直接查 DB 拿最近 episode."""
        # 优先用注入的 EpisodeStore
        if self._episode_store is not None:
            try:
                cutoff = datetime.now(timezone.utc)
                # EpisodeStore.query_by_time 按时间倒序
                all_eps = self._episode_store.query_by_time(
                    limit=limit * 3, active_only=False
                )
                target_actions = {"goal_result", "failure_lesson", "autonomous_goal_proposal"}
                return [
                    ep for ep in all_eps
                    if getattr(ep, "action", "") in target_actions
                ][:limit]
            except Exception as e:
                logger.warning("EpisodeStore query failed: %s", e)

        # 降级: 直接查 DB
        if self._db_path:
            try:
                import sqlite3
                from pathlib import Path
                conn = sqlite3.connect(self._db_path)
                rows = conn.execute("""
                    SELECT action, goal, decision, outcome, context,
                           evaluation_trace, created_at
                    FROM episodes
                    WHERE action IN ('goal_result', 'failure_lesson',
                                     'autonomous_goal_proposal')
                    AND created_at >= datetime('now', '-' || ? || ' days')
                    ORDER BY rowid DESC LIMIT ?
                """, (days, limit)).fetchall()
                conn.close()
                # 返回简单 dict（后面 _episode_to_artifact 要兼容）
                return [
                    type("Ep", (), {
                        "action": r[0], "goal": r[1],
                        "decision": r[2], "outcome": r[3],
                        "context": r[4],
                        "evaluation_trace": r[5],
                        "created_at": r[6],
                    })()
                    for r in rows
                ]
            except Exception as e:
                logger.warning("DB fallback query failed: %s", e)

        return []

    def _episode_to_artifact(self, ep: Any) -> Optional[ExperienceArtifact]:
        """Episode → ExperienceArtifact."""
        action = getattr(ep, "action", "")
        goal = getattr(ep, "goal", "") or ""
        decision = getattr(ep, "decision", "") or ""
        outcome = getattr(ep, "outcome", "") or ""
        success = getattr(ep, "success", None)

        # success 判断: failure_lesson action → 必然失败; 其他看 outcome 关键词
        if action == "failure_lesson":
            success = False
        else:
            success = not any(
                kw in outcome.lower()
                for kw in ["fail", "error", "失败", "not found", "timeout"]
            )

        # 经验提取（纯规则，零 LLM）
        lessons: list[str] = []
        if decision and len(decision) > 15:
            lessons.append(decision.strip())
        if outcome and len(outcome) > 15:
            lessons.append(outcome.strip())

        if not lessons:
            return None

        # 失败原因分类（简化版 — 按关键词）
        failure_cause = ""
        if not success:
            cause_keywords = {
                "ambiguous_task": ["不明确", "ambiguous", "模糊"],
                "timeout": ["超时", "timeout", "timed out"],
                "dependency_missing": ["依赖", "not found", "模块缺失"],
                "permission": ["权限", "permission", "denied"],
                "resource": ["资源", "resource", "memory", "disk"],
            }
            for cause, kws in cause_keywords.items():
                if any(kw in (decision + outcome).lower() for kw in kws):
                    failure_cause = cause
                    break
            if not failure_cause:
                failure_cause = "unknown"

        return ExperienceArtifact(
            goal_description=goal[:100] or "(无目标)",
            action=action,
            success=bool(success),
            lessons=lessons[:3],
            failure_cause=failure_cause,
            context=getattr(ep, "context", "")[:100] if getattr(ep, "context", None) else "",
            created_at=getattr(ep, "created_at", None) or datetime.now(timezone.utc),
        )
