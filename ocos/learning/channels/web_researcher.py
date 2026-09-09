"""WebResearcher — 网络搜索调研渠道.

通过 SearchOps（白名单安全边界）调 DuckDuckGo Instant Answer API
获取网络公开信息，产出 ResearchArtifact → 喂给 UnifiedIngestor.

这是 OCOS "缺口学习" 的主渠道 — EpistemicDrive 发现知识缺口后
通过 motivation 生成 SELF goal，再由这个渠道调研填补.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.learning.unified_ingestor import IngestArtifact, SourceChannel

logger = logging.getLogger(__name__)


@dataclass
class ResearchArtifact:
    """Web 搜索调研结果."""

    topic: str
    findings: list[dict[str, Any]] = field(default_factory=list)  # [{title, body, url}]
    sources: list[str] = field(default_factory=list)  # URL 列表
    summary: str = ""  # 可选摘要（空则从 findings 拼）
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_ingest_artifacts(self) -> list[IngestArtifact]:
        """转成 UnifiedIngestor 可消费的 IngestArtifact 列表.

        - 每个有 body 的 finding → 一个 IngestArtifact
        - 如果有 summary → 额外生成一个综合 IngestArtifact
        """
        arts: list[IngestArtifact] = []

        for f in self.findings:
            body = f.get("body") or f.get("text") or ""
            if not body or len(body.strip()) < 10:
                continue
            arts.append(IngestArtifact(
                channel=SourceChannel.WEB_RESEARCH,
                content=body.strip()[:500],
                title=f.get("title", "")[:100],
                source_url=f.get("url", "") or f.get("source", ""),
                confidence=self.confidence,
                tags=["web", "research", self.topic[:30]],
                knowledge_type="fact",
                metadata={"topic": self.topic, **self.metadata},
            ))

        if self.summary and len(self.summary.strip()) >= 20:
            arts.append(IngestArtifact(
                channel=SourceChannel.WEB_RESEARCH,
                content=self.summary.strip()[:500],
                title=f"「{self.topic}」调研综合摘要",
                confidence=self.confidence + 0.1,  # 摘要更可信
                tags=["web", "research", "summary", self.topic[:30]],
                knowledge_type="concept",
                metadata={"topic": self.topic, "is_summary": True},
            ))

        return arts


class WebResearcher:
    """网络搜索调研.

    依赖 SearchOps（可选）— 没注入时返回空结果（优雅降级）.
    不做 LLM 调用 — 只调 DuckDuckGo API 拿结构化 JSON.
    """

    DUCKDUCKGO_IA_URL = "https://api.duckduckgo.com/"
    DEFAULT_MAX_RESULTS = 5

    def __init__(
        self,
        search_ops: Optional[Any] = None,
        max_results: int = DEFAULT_MAX_RESULTS,
    ):
        self._ops = search_ops
        self._max_results = max_results

    def research(self, topic: str) -> ResearchArtifact:
        """对一个 topic 做网络调研.

        Args:
            topic: 调研主题（如 "Python asyncio vs threading"）

        Returns:
            ResearchArtifact — 可能 findings 为空（搜索失败）
        """
        artifact = ResearchArtifact(topic=topic)

        if self._ops is None:
            artifact.metadata["error"] = "SearchOps not configured"
            return artifact

        try:
            from ocos.operations.search_ops import SearchQuery

            # DuckDuckGo Instant Answer API
            query = SearchQuery(
                query=topic,
                url=self.DUCKDUCKGO_IA_URL,
                params={
                    "q": topic,
                    "format": "json",
                    "no_html": "1",
                    "no_redirect": "1",
                    "skip_disambig": "1",
                },
                max_results=self._max_results,
            )
            result = self._ops.search(query)

            if not result.success:
                artifact.metadata["error"] = result.error or "search failed"
                return artifact

            for r in (result.results or [])[: self._max_results]:
                artifact.findings.append({
                    "title": r.get("title", ""),
                    "body": r.get("body", ""),
                    "url": r.get("url", ""),
                })
                if r.get("url"):
                    artifact.sources.append(r["url"])

            artifact.confidence = min(
                1.0, 0.5 + 0.1 * len(artifact.findings)
            )
            # 自动生成简易摘要（拼接前 N 个 finding 的 body 首句）
            parts = []
            for f in artifact.findings[:3]:
                body = f.get("body", "")
                if body:
                    first_sentence = body.split(".")[0][:150]
                    if first_sentence:
                        parts.append(first_sentence)
            artifact.summary = " ".join(parts) if parts else ""

        except Exception as e:
            logger.warning("WebResearcher error for '%s': %s", topic, e)
            artifact.metadata["error"] = str(e)

        return artifact
