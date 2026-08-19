"""OCOS HTTP API — 请求/响应模型。

Pydantic 模型定义，确保 API 层的类型安全。
与 Kernel 数据模型（dataclass）独立——API 层自己的序列化格式。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── 枚举 ────────────────────────────────────────────────────────


class GoalDomainAPI(str, Enum):
    writing = "writing"
    analysis = "analysis"
    research = "research"
    development = "development"


class GoalStatusAPI(str, Enum):
    pending = "pending"
    active = "active"
    planning = "planning"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    abandoned = "abandoned"


# ── 请求模型 ────────────────────────────────────────────────────


class GoalCreateRequest(BaseModel):
    """POST /ocos/goal — 创建新目标。"""

    goal: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="目标描述",
        examples=["帮我写一本科幻小说"],
    )
    domain: GoalDomainAPI = Field(
        default=GoalDomainAPI.writing,
        description="目标域",
    )
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="优先级 (1=最低, 5=最高)",
    )
    constraints: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="约束条件列表",
    )


class PlanRequest(BaseModel):
    """POST /ocos/plan — 请求规划。"""

    goal: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="目标描述",
    )
    domain: GoalDomainAPI = Field(
        default=GoalDomainAPI.writing,
        description="目标域",
    )


class MemoryQueryRequest(BaseModel):
    """POST /ocos/memory/query — 记忆查询。"""

    query: str = Field(
        default="",
        description="搜索关键词",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="返回条数",
    )


class BeliefQueryRequest(BaseModel):
    """POST /ocos/belief/query — 信念查询。"""

    domain: Optional[str] = Field(
        default=None,
        description="信念域过滤器",
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="最低置信度",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )


# ── 响应模型 ────────────────────────────────────────────────────


class APIResponse(BaseModel):
    """通用 API 响应包装。"""

    success: bool
    message: str
    data: Optional[dict] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class GoalResponse(BaseModel):
    """Goal 创建/查询响应。"""

    goal_id: str
    status: GoalStatusAPI
    domain: GoalDomainAPI
    priority: int
    caller: str
    created_at: str


class PlanResponse(BaseModel):
    """规划响应。"""

    goal_id: str
    status: GoalStatusAPI
    plan_steps: list[dict] = Field(default_factory=list)
    note: str = ""


class MemoryResponse(BaseModel):
    """记忆查询响应。"""

    query: str
    results: list[dict] = Field(default_factory=list)
    total: int = 0
    note: str = ""


class BeliefResponse(BaseModel):
    """信念查询响应。"""

    beliefs: list[dict] = Field(default_factory=list)
    total: int = 0
    counts_by_status: dict[str, int] = Field(default_factory=dict)
    note: str = ""


class SelfStatusResponse(BaseModel):
    """SelfModel 状态响应。"""

    session_id: str
    model_version: str = "N/A"
    capabilities: list[str] = Field(default_factory=list)
    maturity: dict = Field(default_factory=dict)
    statement: str = ""
    note: str = ""


class TraceResponse(BaseModel):
    """DecisionTrace 响应。"""

    trace_id: str
    steps: list[dict] = Field(default_factory=list)
    note: str = ""


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = "ok"
    version: str = "1.1"
    layer: str = "cognitive_interface"
