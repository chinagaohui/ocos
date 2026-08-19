"""Phase 28 — ExecutionContract: 执行契约。

定义 Agent 执行的输入/输出/超时/重试策略/降级。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class ExecutionContract:
    """Agent 执行契约 — 不可变。"""
    contract_id: str
    task_id: str
    agent_id: str
    input_spec: dict = field(default_factory=dict)       # 输入格式定义
    output_spec: dict = field(default_factory=dict)      # 输出格式定义
    timeout_seconds: int = 300
    retry_policy: str = "retry_3x"                       # no_retry|retry_3x|retry_with_fallback
    fallback_agent_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.contract_id:
            raise ValueError("contract_id must not be empty")
        if not self.task_id:
            raise ValueError("task_id must not be empty")
        if not self.agent_id:
            raise ValueError("agent_id must not be empty")
        if self.timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds > 0, got {self.timeout_seconds}")
        if self.retry_policy not in ("no_retry", "retry_3x", "retry_with_fallback"):
            raise ValueError(f"invalid retry_policy: {self.retry_policy}")
        if self.retry_policy == "retry_with_fallback" and self.fallback_agent_id is None:
            raise ValueError("retry_with_fallback requires fallback_agent_id")

    @classmethod
    def create(
        cls,
        task_id: str,
        agent_id: str,
        input_spec: dict | None = None,
        output_spec: dict | None = None,
        timeout_seconds: int = 300,
        retry_policy: str = "retry_3x",
        fallback_agent_id: str | None = None,
    ) -> ExecutionContract:
        return cls(
            contract_id=f"CONTRACT-{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            agent_id=agent_id,
            input_spec=input_spec or {},
            output_spec=output_spec or {},
            timeout_seconds=timeout_seconds,
            retry_policy=retry_policy,
            fallback_agent_id=fallback_agent_id,
        )

    def validate_output_schema(self, output: dict) -> tuple[bool, str]:
        """验证输出是否符合 output_spec schema。"""
        if not self.output_spec:
            return True, "no output_spec defined"
        missing = [k for k in self.output_spec if k not in output]
        if missing:
            return False, f"missing output fields: {missing}"
        return True, "ok"
