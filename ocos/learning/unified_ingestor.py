"""UnifiedIngestor — 多渠道学习统一摄入入口。

所有外部学习渠道（网络搜索/LLM 问答/任务经验）的产出数据收敛到这里做:
    filter → extract → enrich → store → register

设计原则:
    UI-01: 只做摄入，不做触发 — 触发由各渠道/EpistemicDrive/motivation 负责
    UI-02: 主链路先落核心存储，失败降级为日志不阻断
    UI-03: 幂等 — 同 source+content_key 不重复注册
    UI-04: 纯确定性（零 LLM） — 让外部渠道负责 LLM 调用
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SourceChannel(str, Enum):
    WEB_RESEARCH = "web_research"
    LLM_QA = "llm_qa"
    EXPERIENCE = "experience"
    MANUAL = "manual"


class IngestStatus(str, Enum):
    STORED = "stored"
    FILTERED_LOW_QUALITY = "filtered_low_quality"
    DUPLICATE = "duplicate"
    FAILED = "failed"


@dataclass
class IngestArtifact:
    """摄入载体 — 所有渠道的原始数据统一包装成这个形状."""

    channel: SourceChannel
    content: str  # 核心知识文本（摘要/结论/经验教训）
    title: str = ""  # 可选标题
    source_url: str = ""  # 网络渠道来源 URL
    confidence: float = 0.5  # 渠道给出的初始置信度
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    knowledge_type: str = "fact"  # fact / procedure / concept / lesson
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def content_key(self) -> str:
        """幂等去重 key — 同 channel + content 就视为重复."""
        h = hashlib.sha1(
            f"{self.channel}:{self.content[:500]}".encode("utf-8")
        ).hexdigest()[:16]
        return f"UI-{h}"

    def quality_score(self) -> float:
        """0-1 质量评分 — 确定性规则，不依赖 LLM.

        用于 filter 阶段淘汰低质量输入.
        """
        score = self.confidence
        # 内容长度 — 太短可能无意义
        if len(self.content) >= 50:
            score += 0.1
        elif len(self.content) < 15:
            score -= 0.2
        # 有来源 URL（web 渠道）→ 加分
        if self.source_url and self.channel == SourceChannel.WEB_RESEARCH:
            score += 0.1
        # 有 title → 加分
        if self.title:
            score += 0.05
        # 负向关键词 — "不知道"/"不清楚"/"可能" 过多
        weak_words = ["不知道", "不清楚", "不确定", "可能", "大概", "也许", "I don't know"]
        weak_count = sum(1 for w in weak_words if w.lower() in self.content.lower())
        score -= 0.05 * weak_count
        return max(0.0, min(1.0, score))


@dataclass
class IngestResult:
    status: IngestStatus
    artifact_id: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class UnifiedIngestor:
    """统一摄入入口.

    依赖注入（全部可选）:
        - knowledge_registry: KnowledgeRegistry → register KnowledgeUnit
        - belief_store: BeliefStore → 高价值 lessons 也沉淀成 belief
        - db_path: 用于 WisdomStore 路径（experience 渠道）
    """

    MIN_QUALITY_THRESHOLD = 0.3  # 低于这个分数直接 filter 掉
    MAX_INGEST_PER_CALL = 20  # 单次 ingest 最多处理多少条（防批量轰炸）

    def __init__(
        self,
        *,
        knowledge_registry: Any = None,
        belief_store: Any = None,
        pattern_store: Any = None,
        db_path: Optional[str] = None,
        idempotent_check: Optional[Callable[[str], bool]] = None,
    ):
        self._registry = knowledge_registry
        self._belief_store = belief_store
        self._pattern_store = pattern_store
        self._db_path = db_path
        self._idempotent_check = idempotent_check  # (content_key) -> bool exists?
        self._stats = {
            "total": 0, "stored": 0, "filtered": 0,
            "duplicate": 0, "failed": 0,
        }

    # ── 主入口 ──────────────────────────────────────────────────────────

    def ingest(
        self,
        artifacts: IngestArtifact | list[IngestArtifact],
        *,
        owner: str = "unified_ingestor",
    ) -> list[IngestResult]:
        """摄入 — 单条或批量."""
        if isinstance(artifacts, IngestArtifact):
            artifacts = [artifacts]

        artifacts = artifacts[: self.MAX_INGEST_PER_CALL]
        results: list[IngestResult] = []

        for art in artifacts:
            self._stats["total"] += 1
            result = self._ingest_one(art, owner=owner)
            results.append(result)
            self._stats[result.status.value] = (
                self._stats.get(result.status.value, 0) + 1
            )

        return results

    # ── 内部: filter → extract → store → register ────────────────────────

    def _ingest_one(
        self, art: IngestArtifact, owner: str
    ) -> IngestResult:
        # 1. Filter — 质量门槛
        quality = art.quality_score()
        if quality < self.MIN_QUALITY_THRESHOLD:
            return IngestResult(
                status=IngestStatus.FILTERED_LOW_QUALITY,
                message=f"质量分数 {quality:.2f} < {self.MIN_QUALITY_THRESHOLD}",
                details={"quality_score": quality},
            )

        # 2. 幂等检查
        content_key = art.content_key
        try:
            if self._idempotent_check and self._idempotent_check(content_key):
                return IngestResult(
                    status=IngestStatus.DUPLICATE,
                    artifact_id=content_key,
                    message="已存在，跳过",
                )
        except Exception:
            pass  # 幂等检查失败不阻断，降级为继续

        # 3. Store — 按渠道分发到对应存储
        errors: list[str] = []

        # 3a. KnowledgeRegistry — 所有渠道都注册 KnowledgeUnit
        stored_unit_id = self._store_knowledge_unit(art, owner, errors)

        # 3b. BeliefStore — 只给 experience 渠道 + 高置信度 web/llm
        if self._should_make_belief(art):
            self._store_belief(art, errors)

        if errors:
            logger.warning("Ingest had errors for %s: %s", content_key, errors)

        return IngestResult(
            status=IngestStatus.STORED,
            artifact_id=stored_unit_id or content_key,
            message=f"stored (quality={quality:.2f})",
            details={
                "quality_score": quality,
                "errors": errors,
                "channel": art.channel.value,
            },
        )

    # ── Store helpers ────────────────────────────────────────────────────

    def _store_knowledge_unit(
        self, art: IngestArtifact, owner: str, errors: list[str]
    ) -> str:
        """尝试注册 KnowledgeUnit 到 KnowledgeRegistry.

        返回 unit_id（失败则返回 content_key 作为 fallback id）.
        """
        fallback_id = art.content_key

        if self._registry is None:
            return fallback_id

        try:
            from ocos.knowledge.store.registry import AccessScope
            from ocos.knowledge.store.ontology import (
                KnowledgeUnit, KnowledgeLevel, KnowledgeStatus,
            )

            level = self._infer_knowledge_level(art)
            # KnowledgeUnit 只有 8 个字段: unit_id/level/status/content/
            # source/version/parent_id/timestamp —— 没有 title/confidence/
            # tags/metadata 等
            unit = KnowledgeUnit(
                unit_id=art.content_key,
                level=level,
                status=KnowledgeStatus.CANDIDATE,
                content={
                    "statement": art.content[:500],
                    "confidence": float(art.confidence),
                    "domain": art.knowledge_type or art.channel.value,
                    "channel": art.channel.value,
                    "source_url": art.source_url or "",
                    "tags": list(art.tags or {art.channel.value}),
                },
                source=art.source_url or art.channel.value,
                version=1,
                parent_id="",
                timestamp=art.created_at,
            )
            ok, msg = self._registry.register(
                unit, owner=owner,
                scope=AccessScope.PROTECTED,
                tags=set(art.tags),
            )
            if ok:
                return unit.unit_id
            errors.append(f"registry.register failed: {msg}")
        except ImportError as e:
            errors.append(f"KnowledgeUnit import failed: {e}")
        except Exception as e:
            errors.append(f"KnowledgeUnit store error: {e}")

        return fallback_id

    def _store_belief(self, art: IngestArtifact, errors: list[str]) -> None:
        """把 experience / high-confidence knowledge 也沉淀成 Belief.

        Belief 是记忆层的"主题归纳" — 和 KnowledgeUnit 的"事实单元"互补.
        """
        if self._belief_store is None:
            return

        try:
            from ocos.memory.belief.store import Belief, BeliefStatus
            import hashlib

            topic = art.title or art.tags[0] if art.tags else art.channel.value
            belief_id = "BLF-" + hashlib.sha1(topic.encode()).hexdigest()[:12]

            existing = None
            try:
                existing = self._belief_store.get(belief_id)
            except Exception:
                pass

            if existing is None:
                belief = Belief(
                    id=belief_id,
                    statement=f"主题「{topic}」相关经历持续出现（渠道: {art.channel.value}）",
                    confidence=art.confidence,
                    evidence_ids=(),
                    scope={"channel": art.channel.value, "topic": topic},
                    status=BeliefStatus.ACTIVE,
                    created_at=art.created_at,
                    last_updated=art.created_at,
                )
                self._belief_store.save(belief)
            else:
                # 已有 belief → 增强置信度
                new_conf = min(
                    1.0, existing.confidence + art.confidence * 0.1
                )
                enhanced = Belief(
                    id=existing.id,
                    statement=existing.statement,
                    confidence=new_conf,
                    evidence_ids=existing.evidence_ids,
                    scope=existing.scope,
                    status=existing.status,
                    created_at=existing.created_at,
                    last_updated=datetime.now(timezone.utc),
                )
                self._belief_store.save(enhanced)
        except Exception as e:
            errors.append(f"Belief store error: {e}")

    def _should_make_belief(self, art: IngestArtifact) -> bool:
        """哪些输入应该也写 BeliefStore？"""
        # Experience 渠道全部应该沉淀
        if art.channel == SourceChannel.EXPERIENCE:
            return True
        # Web/LLM 渠道 → 高置信度（≥0.7）且有 title/tag 的也值得
        if art.confidence >= 0.7 and (art.title or art.tags):
            return True
        return False

    def _infer_knowledge_level(self, art: IngestArtifact) -> "KnowledgeLevel":
        """根据渠道和置信度推断 KnowledgeLevel (OBSERVATION→POLICY)."""
        from ocos.knowledge.store.ontology import KnowledgeLevel

        if art.channel == SourceChannel.EXPERIENCE:
            return KnowledgeLevel.OBSERVATION   # 自己的经验 = 底层观测
        if art.channel in (SourceChannel.WEB_RESEARCH, SourceChannel.LLM_QA):
            return KnowledgeLevel.EVIDENCE       # 外部搜索/LLM问答 = 证据层
        if art.confidence >= 0.8:
            return KnowledgeLevel.PRINCIPLE      # 高置信度 = 原则
        if art.confidence >= 0.5:
            return KnowledgeLevel.PATTERN        # 中等 = 模式
        return KnowledgeLevel.OBSERVATION        # 低 = 观测

    # ── 状态查询 ────────────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    # ── 建议 3: Gap 闭环 ──────────────────────────────────────────

    def resolve_gap(
        self,
        gap_id: str,
        knowledge_ids: list[str],
    ) -> None:
        """回写 PredictionGapTracker — 这批摄入知识是否缩小了 gap.

        闭环: PredictionGapTracker.emit_gap_hypothesis → EpistemicDrive.prioritize_by_gap
             → 定向探索 → UnifiedIngestor.ingest → resolve_gap 回写

        当前简化: 只是在 knowledge 表记录 gap 关联 (用于反查),
        未来版本可以让 PredictionGapTracker 根据摄入反馈动态更新 gap.
        """
        try:
            if not gap_id or not knowledge_ids:
                return
            # 写 marker 表
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS gap_resolutions ("
                "gap_id TEXT, knowledge_id TEXT, resolved_at TEXT)"
            )
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            for kid in knowledge_ids:
                conn.execute(
                    "INSERT INTO gap_resolutions VALUES (?,?,?)",
                    (gap_id, kid, now),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("resolve_gap failed: %s", e)


__all__ = [
    "UnifiedIngestor",
    "IngestArtifact",
    "IngestResult",
    "IngestStatus",
    "SourceChannel",
]
