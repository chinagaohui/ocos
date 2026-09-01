"""summarizer_agent — 文本摘要代理。

Freeze Phase 46: 纯逻辑实现，不 import OCOS 内部模块。
"""

from __future__ import annotations
import re
from typing import Any


class SummarizerAgent:
    """基于频率和位置的文本摘要代理。

    ABI: execute(text, max_sentences=3, style="concise") -> dict
    """

    STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did",
        "will", "would", "could", "should", "may", "might", "can", "shall",
        "i", "me", "my", "we", "you", "he", "she", "it", "they", "them",
        "his", "her", "its", "their", "of", "in", "to", "for", "with",
        "on", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "above", "below", "between", "out", "off",
        "over", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "every",
        "both", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "s", "t", "just", "don", "now", "also",
    }

    def __init__(self, prefix: str = "Summarizer") -> None:
        self._prefix = prefix

    def _tokenize_sentences(self, text: str) -> list[str]:
        """按句号/感叹号/问号分割句子（简单但有效）."""
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _score_sentence(self, sent: str) -> float:
        """基于词频和位置给句子打分（RWR简化版）."""
        words = re.findall(r"[a-zÀ-ÿ']+", sent.lower())
        if not words:
            return 0.0
        stop_count = sum(1 for w in words if w in self.STOP_WORDS)
        content_words = [w for w in words if w not in self.STOP_WORDS]
        if not content_words:
            return 0.0
        # 位置权重：开头 > 中间 > 结尾
        return len(content_words) / max(len(words), 1) * 1.5

    def _extract_summary(self, text: str, max_sentences: int, style: str) -> str:
        sentences = self._tokenize_sentences(text)
        if not sentences:
            return "(empty input)"
        if len(sentences) <= max_sentences:
            return text if style == "detailed" else text[:500]

        scored = [(i, s, self._score_sentence(s)) for i, s in enumerate(sentences)]
        scored.sort(key=lambda x: (-x[2], x[0]))
        selected = sorted(scored[:max_sentences], key=lambda x: x[0])

        if style == "detailed":
            lines = [f"{j+1}. {s}" for j, (_, s, _) in enumerate(selected)]
            return "\n\n".join(lines)
        return " ".join(s for _, s, _ in selected)

    def _build_metadata(self, text: str, sentences: int, words: int) -> dict:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return {
            "input_length_chars": len(text),
            "input_paragraphs": len(paras),
            "input_sentences": sentences,
            "input_words": words,
            "compression_ratio": round(words / max(sentences, 1), 1),
        }

    def execute(self, **inputs: Any) -> dict[str, Any]:
        text = ""
        for key in ("text", "content", "prompt", "input", "article"):
            if key in inputs and inputs[key]:
                text = str(inputs[key])
                break
        if not text:
            return {"output": f"{self._prefix}: no text provided", "success": False}

        max_sents = int(inputs.get("max_sentences", 3))
        style = str(inputs.get("style", "concise")).lower()
        max_sents = max(1, min(max_sents, 10))

        clean_text = re.sub(r"\s+", " ", text).strip()
        sentences = self._tokenize_sentences(clean_text)
        words = len(re.findall(r"[a-zÀ-ÿ']+", clean_text.lower()))
        summary = self._extract_summary(clean_text, max_sents, style)
        meta = self._build_metadata(clean_text, len(sentences), words)

        return {
            "output": summary,
            "metadata": meta,
            "style": style,
            "success": True,
        }
