"""Phase 28 — FallbackHandler: 执行失败降级。

策略:
  1. retry_3x: 同 agent 重试最多 3 次
  2. retry_with_fallback: 重试失败后切换 fallback agent
  3. no_retry: 直接失败
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.agent_orchestration.registry import AgentDescriptor


@dataclass
class FallbackResult:
    """降级执行结果。"""
    success: bool
    agent_id: str
    attempt: int
    error: str | None = None
    fallback_used: bool = False


class FallbackHandler:
    """降级处理器。"""

    def __init__(self) -> None:
        self._fallback_log: list[FallbackResult] = []

    def execute_with_policy(
        self,
        agent_fn,
        primary_agent: AgentDescriptor,
        fallback_agent: AgentDescriptor | None,
        retry_policy: str,
    ) -> FallbackResult:
        """按重试策略执行 agent_fn。

        Args:
            agent_fn: callable(agent_id) → (success, result)
            primary_agent: 主 Agent
            fallback_agent: 备选 Agent (retry_with_fallback 需要)
            retry_policy: no_retry|retry_3x|retry_with_fallback
        """
        if retry_policy == "no_retry":
            ok, err = agent_fn(primary_agent.agent_id)
            result = FallbackResult(
                success=ok, agent_id=primary_agent.agent_id,
                attempt=1, error=err,
            )
            self._fallback_log.append(result)
            return result

        if retry_policy == "retry_3x":
            for attempt in range(1, 4):
                ok, err = agent_fn(primary_agent.agent_id)
                if ok:
                    result = FallbackResult(
                        success=True, agent_id=primary_agent.agent_id,
                        attempt=attempt,
                    )
                    self._fallback_log.append(result)
                    return result
            result = FallbackResult(
                success=False, agent_id=primary_agent.agent_id,
                attempt=3, error=err,
            )
            self._fallback_log.append(result)
            return result

        # retry_with_fallback
        for attempt in range(1, 4):
            ok, err = agent_fn(primary_agent.agent_id)
            if ok:
                result = FallbackResult(
                    success=True, agent_id=primary_agent.agent_id,
                    attempt=attempt,
                )
                self._fallback_log.append(result)
                return result

        # 主 agent 3 次失败 → 降级
        if fallback_agent is not None:
            ok, err = agent_fn(fallback_agent.agent_id)
            result = FallbackResult(
                success=ok, agent_id=fallback_agent.agent_id,
                attempt=4, error=err if not ok else None,
                fallback_used=True,
            )
            self._fallback_log.append(result)
            return result

        result = FallbackResult(
            success=False, agent_id=primary_agent.agent_id,
            attempt=3, error="all retries exhausted, no fallback available",
        )
        self._fallback_log.append(result)
        return result

    @property
    def log(self) -> list[FallbackResult]:
        return list(self._fallback_log)
