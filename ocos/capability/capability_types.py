"""Phase 45: Capability Types — 能力神经系统核心类型。

Capability Nervous System 回答: "身体如何使用这个器官？"

不是"工具调用"——而是 OCOS 控制身体的神经系统。

核心链路:
    Decision → Capability Selection → Registry → Adapter → Permission → Execution → Result → Understanding → Memory

核心边界:
    CNS45-01: Capability ≠ Authority        — 能力只是执行接口
    CNS45-02: Selector ≠ Decision            — 能力选择不替代决策
    CNS45-03: Agent ≠ Cognitive Entity       — 外部 Agent 是能力提供者，不是认知主体
    CNS45-04: Execution ≠ Learning           — Result → Interpretation → Validation → Memory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 能力类型
# ═══════════════════════════════════════════════════════════════════════════════


class CapabilityType(Enum):
    """能力类型——对应外部能力种类。"""
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DEBUGGING = "debugging"
    BROWSER = "browser"
    FILE_OPERATION = "file_operation"
    DATA_ANALYSIS = "data_analysis"
    API_CALL = "api_call"
    DOCUMENT_GENERATION = "document_generation"
    SEARCH = "search"
    DEPLOYMENT = "deployment"
    CUSTOM_AGENT = "custom_agent"

    @property
    def category(self) -> str:
        """能力大类。"""
        cats = {
            "code": ["code_generation", "code_review", "testing", "debugging"],
            "io": ["browser", "file_operation", "api_call", "search"],
            "analysis": ["data_analysis"],
            "output": ["document_generation"],
            "ops": ["deployment"],
        }
        for cat, types in cats.items():
            if self.value in types:
                return cat
        return "agent"


class CapabilityState(Enum):
    """能力生命周期状态。"""
    REGISTERED = "registered"    # 已注册（来自 Phase 44 批准）
    AVAILABLE = "available"      # 可用
    BUSY = "busy"                # 繁忙（执行中）
    DEGRADED = "degraded"        # 降级
    UNAVAILABLE = "unavailable"  # 不可用
    DEPRECATED = "deprecated"    # 已弃用


class ExecutorKind(Enum):
    """能力执行者类别。"""
    EXTERNAL_AGENT = "external_agent"  # Codex / OpenClaw / OpenTale
    LOCAL_FUNCTION = "local_function"  # 本地函数
    HTTP_SERVICE = "http_service"      # HTTP API
    SUBPROCESS = "subprocess"          # 子进程
    PLUGIN = "plugin"                  # 插件


# ═══════════════════════════════════════════════════════════════════════════════
# 能力档案
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Capability:
    """能力档案——描述一个可调用的执行接口。

    注意: Capability ≠ Agent。外部 Agent 是此能力背后的提供者。
    """

    capability_id: str
    name: str
    cap_type: CapabilityType
    executor_kind: ExecutorKind = ExecutorKind.EXTERNAL_AGENT
    provider: str = ""             # Codex / OpenClaw / OpenTale / local
    endpoint: str = ""             # 调用地址或函数路径
    description: str = ""
    input_schema: str = ""         # 输入格式
    output_schema: str = ""        # 输出格式
    tags: list[str] = field(default_factory=list)
    state: CapabilityState = CapabilityState.REGISTERED
    trust_level: str = "UNKNOWN"   # 从 Phase 44 继承
    performance_score: float = 0.5  # 历史成功率 [0, 1]
    cost_estimate: float = 0.0     # 预估成本
    max_concurrency: int = 1       # 最大并发

    @property
    def is_callable(self) -> bool:
        return self.state in (CapabilityState.AVAILABLE, CapabilityState.BUSY)

    @property
    def is_external_agent(self) -> bool:
        return self.executor_kind == ExecutorKind.EXTERNAL_AGENT


# ═══════════════════════════════════════════════════════════════════════════════
# 能力选择
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CapabilityMatch:
    """能力匹配结果——Selector 的输出。"""
    capability: Capability
    match_score: float      # [0, 1] 匹配度
    reason: str = ""


@dataclass(frozen=True)
class SelectionResult:
    """选择结果——Selector 的完整输出。"""
    matches: list[CapabilityMatch] = field(default_factory=list)
    selected: Capability | None = None

    @property
    def has_match(self) -> bool:
        return self.selected is not None

    @property
    def best_match(self) -> CapabilityMatch | None:
        if self.matches:
            return self.matches[0]
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 执行
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExecutionRequest:
    """执行请求——从 Router → Adapter → Permission → External Agent。"""
    request_id: str
    capability_id: str
    input_payload: str = ""       # 输入载荷
    context: str = ""             # 附加上下文
    tick_id: int = 0


class ExecutionStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"


@dataclass(frozen=True)
class RawResult:
    """原始执行结果——从 External Agent 返回的原始输出。

    注意 CNS45-04: 此结果不能直接成为 Knowledge/Memory。
    """
    request_id: str
    capability_id: str
    raw_output: str = ""
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    error_message: str = ""
    latency_ticks: int = 0
    tick_id: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 结果理解
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class InterpretedResult:
    """经过理解的结果——经过 OCOS 处理后。

    不同于 RawResult:
        - 结构化理解
        - 置信度评估
        - 验证标记
        - 可写入 Experience
    """

    request_id: str
    capability_id: str
    summary: str = ""            # 人类可读摘要
    structured_data: str = ""    # 结构化数据
    confidence: float = 0.0      # OCOS 对此结果的理解置信度
    is_valid: bool = False       # 是否通过验证
    validation_note: str = ""
    tick_id: int = 0


__all__ = [
    "CapabilityType",
    "CapabilityState",
    "ExecutorKind",
    "Capability",
    "CapabilityMatch",
    "SelectionResult",
    "ExecutionRequest",
    "ExecutionStatus",
    "RawResult",
    "InterpretedResult",
]
