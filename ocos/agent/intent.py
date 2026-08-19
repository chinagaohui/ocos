"""Intent — 意图提取。

Intent 是 Agent 对输入的理解 —— "用户想让我做什么？"
"""

from __future__ import annotations

import re
from typing import Any


class Intent:
    """意图。

    解析输入文本，提取意图类型和参数。
    Phase 23 将接入 Capability Selector 进行更复杂的意图映射。
    """

    KNOWN_INTENTS: dict[str, list[str]] = {
        "create": ["create", "write", "make", "generate", "build", "new"],
        "analyze": ["analyze", "review", "check", "inspect", "examine", "audit"],
        "search": ["search", "find", "lookup", "query", "retrieve", "get"],
        "modify": ["modify", "update", "change", "edit", "patch", "fix"],
        "delete": ["delete", "remove", "clear", "erase", "destroy"],
        "learn": ["learn", "study", "understand", "explain", "teach"],
        "plan": ["plan", "schedule", "organize", "arrange", "prepare"],
        "reflect": ["reflect", "review", "think", "consider", "evaluate"],
    }

    def __init__(self) -> None:
        self._current: dict[str, Any] = {
            "type": "unknown",
            "description": "",
            "confidence": 0.0,
        }

    def extract(self, text: str) -> dict[str, Any]:
        """从输入文本提取意图。"""
        text_lower = text.lower()

        best_type = "unknown"
        best_score = 0

        for intent_type, keywords in self.KNOWN_INTENTS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_type = intent_type

        confidence = min(best_score / 3.0, 1.0) if best_score > 0 else 0.0

        self._current = {
            "type": best_type,
            "description": text[:100],
            "confidence": confidence,
            "keywords_found": sum(1 for kw_list in self.KNOWN_INTENTS.values()
                                  for kw in kw_list if kw in text_lower),
            "original_length": len(text),
        }
        return self._current

    def get_intent_type(self) -> str:
        return self._current.get("type", "unknown")

    def get_intent_description(self) -> str:
        return self._current.get("description", "")

    def get_confidence(self) -> float:
        return self._current.get("confidence", 0.0)

    def reset(self) -> None:
        self._current = {"type": "unknown", "description": "", "confidence": 0.0}
