"""LLMTutor — LLM 知识库问答渠道.

当用户对话中 OCOS 不知道答案时（EpistemicDrive 不确定性高），
或作为主动学习的一环，通过 TextGenerator 向 LLM 提问并把
回答沉淀成 KnowledgeUnit.

和 WebResearcher 的区别:
    - WebResearcher = 搜网络拿"已公开的信息"
    - LLMTutor     = 向 LLM 求"推理/解释/方法论"（需要 LLM 能力）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.learning.unified_ingestor import IngestArtifact, SourceChannel

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    question: str
    answer: str = ""
    confidence: float = 0.5  # LLM 回答的可信程度（从 metadata 推断）
    sources: list[str] = field(default_factory=list)  # LLM 可能返回的来源引用
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""

    def to_ingest_artifacts(self) -> list[IngestArtifact]:
        if not self.success or not self.answer.strip():
            return []
        return [IngestArtifact(
            channel=SourceChannel.LLM_QA,
            content=self.answer.strip()[:500],
            title=f"Q: {self.question[:80]}",
            confidence=self.confidence,
            tags=["llm_qa", self.question[:30]],
            knowledge_type="concept",
            metadata={
                "question": self.question,
                "sources": self.sources,
                **self.metadata,
            },
        )]


class LLMTutor:
    """LLM 知识库问答.

    依赖 TextGenerator（可选）— 没注入时返回空结果.
    """

    def __init__(
        self,
        text_generator: Optional[Any] = None,
        system_prompt: str = "",
    ):
        self._generator = text_generator
        self._system_prompt = system_prompt or (
            "你是一个知识库问答器。回答要准确、结构化、并引用可验证的知识来源。"
            "如果不确定，请明确说不知道，不要编造。"
        )

    def ask(self, question: str, *, context_knowledge: str = "") -> QAResult:
        """向 LLM 提问.

        Args:
            question: 要问的问题
            context_knowledge: 可选的上下文知识（帮助 LLM 更准确回答）

        Returns:
            QAResult
        """
        result = QAResult(question=question)

        if self._generator is None:
            result.success = False
            result.error = "TextGenerator not configured"
            return result

        try:
            # 构造 prompt
            user_parts = []
            if context_knowledge:
                user_parts.append(f"参考知识:\n{context_knowledge[:400]}")
            user_parts.append(f"问题: {question}")
            user_parts.append("请给出结构化回答（要点列表 + 置信度）。")
            user_prompt = "\n\n".join(user_parts)

            # 调 TextGenerator.generate
            if hasattr(self._generator, "generate"):
                response = self._generator.generate(
                    system_prompt=self._system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=800,
                )
            elif hasattr(self._generator, "async_generate"):
                import asyncio
                response = asyncio.run(
                    self._generator.async_generate(
                        system_prompt=self._system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=800,
                    )
                )
            else:
                result.success = False
                result.error = "TextGenerator has no generate method"
                return result

            # 解析响应
            if isinstance(response, str):
                result.answer = response
                result.confidence = 0.6  # 默认中等
            elif hasattr(response, "text"):
                result.answer = response.text or ""
                result.confidence = 0.6
            elif isinstance(response, dict):
                result.answer = response.get("text", response.get("content", ""))
                result.confidence = response.get("confidence", 0.6)
                result.sources = response.get("sources", []) or []

            if not result.answer.strip():
                result.success = False
                result.error = "Empty response"

        except Exception as e:
            logger.warning("LLMTutor error on '%s': %s", question, e)
            result.success = False
            result.error = str(e)

        return result
