"""Phase 60: Action Dispatcher — routes OCOS decisions to concrete actions.

Connects autonomous loop decisions to:
  - OpenTale bridge (Phase 59) — drive chapter writing
  - Web feeder (Phase 59) — search fresh data
  - Internal operations — reflection, memory consolidation, health check
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from datetime import datetime, timezone
from enum import Enum, auto


class ActionType(Enum):
    """Types of actions OCOS can dispatch."""
    WRITE_CHAPTER = auto()        # Drive OpenTale to write a chapter
    SEARCH_WEB = auto()           # Feed fresh data via web search
    CONSOLIDATE_MEMORY = auto()   # Internal memory consolidation
    HEALTH_CHECK = auto()         # Self-diagnostic
    FEEDBACK_PROCESS = auto()     # Process OpenTale chapter output
    REFLECT = auto()              # Self-reflection
    NOOP = auto()                 # Do nothing
    RUN_COMMAND = auto()          # PW-4.1: 沙盒命令（黑白名单，ASK 审批后执行）
    HTTP_FETCH = auto()           # PW-4.1: 白名单 URL 抓取（ASK 审批后执行）
    QUERY_DB = auto()             # P2-1: 只读 SQLite 查询（系统自检/数据分析）


@dataclass
class DispatchedAction:
    """A concrete action dispatched by OCOS."""
    action_type: ActionType
    target: str = ""              # e.g., "open_tale", "web_search", "memory"
    payload: dict[str, Any] = field(default_factory=dict)
    dispatched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "pending"       # pending | executing | done | failed
    result: Any = None


@dataclass
class ActionDispatcher:
    """Routes OCOS cognitive decisions to concrete external actions.

    Acts as the bridge between OCOS's abstract decisions and
    concrete operations (OpenTale, web search, memory, etc.).
    """

    # Registered handlers
    _handlers: dict[ActionType, Callable] = field(default_factory=dict)
    _custom_handlers: dict[str, Callable] = field(default_factory=dict)  # UX-D: 字符串键
    _history: list[DispatchedAction] = field(default_factory=list)
    _cooldown_until: Optional[datetime] = None

    def register_custom_handler(self, name: str, handler: Callable) -> None:
        """UX-D: 注册字符串键的自定义 handler（非 ActionType 枚举，如 self_upgrade）。"""
        self._custom_handlers[name] = handler

    def register_handler(self, action_type: ActionType, handler: Callable) -> None:
        """Register a handler for a specific action type."""
        self._handlers[action_type] = handler

    def dispatch(self, action_type: ActionType, target: str = "",
                 payload: Optional[dict] = None) -> DispatchedAction:
        """Dispatch an action to its registered handler.

        Returns the DispatchedAction with result.
        """
        action = DispatchedAction(
            action_type=action_type,
            target=target,
            payload=payload or {},
        )

        handler = self._handlers.get(action_type)
        if handler is None:
            action.status = "failed"
            action.result = f"No handler registered for {action_type}"
            self._history.append(action)
            return action

        try:
            action.status = "executing"
            result = handler(action)
            action.status = "done"
            action.result = result
        except Exception as e:
            action.status = "failed"
            action.result = str(e)

        self._history.append(action)
        # Keep last 500 actions
        if len(self._history) > 500:
            self._history = self._history[-250:]
        return action

    def interpret_decision(self, decision_proposal: str,
                           attention_focus: str = "") -> list[DispatchedAction]:
        """Interpret an OCOS decision proposal into concrete actions.

        Simple keyword-based interpretation. In production, this could
        use an LLM for more nuanced interpretation.
        """
        actions: list[DispatchedAction] = []

        proposal_lower = decision_proposal.lower()
        focus_lower = attention_focus.lower()

        # Check for writing-related decisions
        writing_keywords = ["write", "chapter", "novel", "scene", "draft", "generate"]
        if any(kw in proposal_lower for kw in writing_keywords):
            actions.append(DispatchedAction(
                action_type=ActionType.WRITE_CHAPTER,
                target="open_tale",
                payload={"prompt": decision_proposal[:500]},
            ))

        # Check for research needs
        research_keywords = ["search", "research", "find", "learn", "explore", "study"]
        if any(kw in proposal_lower for kw in research_keywords):
            actions.append(DispatchedAction(
                action_type=ActionType.SEARCH_WEB,
                target="web_search",
                payload={"query": decision_proposal[:200]},
            ))

        # Check for reflection
        reflect_keywords = ["reflect", "review", "analyze", "evaluate", "assess"]
        if any(kw in proposal_lower for kw in reflect_keywords):
            actions.append(DispatchedAction(
                action_type=ActionType.REFLECT,
                target="self",
                payload={"topic": decision_proposal[:200]},
            ))

        # Default: NOOP if nothing matches
        if not actions:
            actions.append(DispatchedAction(
                action_type=ActionType.NOOP,
                target="",
                payload={"reason": "no matching handler"},
            ))

        return actions

    def dispatch_by_name(self, action_type_name: str,
                         payload: Optional[dict] = None):
        """AUD-F12: 按名称派发（待批动作审批后回放）。

        未知 ActionType 或无注册 handler → None（调用方诚实记 blocked）。
        UX-D: 自定义字符串 handler（如 self_upgrade）同样可触达 —
        返回带 .status/.result 的轻量结果对象。
        """
        if action_type_name in self._custom_handlers:
            from types import SimpleNamespace
            action = SimpleNamespace(
                action_type=action_type_name, target="custom",
                payload=payload or {}, status="executing", result=None)
            try:
                action.result = self._custom_handlers[action_type_name](action)
                action.status = "done"
            except Exception as e:
                action.status = "failed"
                action.result = str(e)
            self._history.append(action)
            return action
        try:
            at = ActionType[action_type_name]
        except KeyError:
            return None
        if at not in self._handlers:
            return None
        return self.dispatch(at, payload=payload or {})

    @property
    def recent_actions(self) -> list[DispatchedAction]:
        return self._history[-20:]

    def action_summary(self) -> dict:
        """Summary of dispatched actions."""
        types = {}
        for a in self._history:
            t = a.action_type.name
            types[t] = types.get(t, 0) + 1
        return {
            "total_actions": len(self._history),
            "by_type": types,
            "last_action": self._history[-1].action_type.name if self._history else "none",
            "last_status": self._history[-1].status if self._history else "none",
        }
