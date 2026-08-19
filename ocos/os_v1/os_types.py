"""Phase 50: Personal Cognitive OS v1.0 — Types.

从架构完成到运行验证的最后一步。

核心概念:
    - UserIntent: 统一入口 — 用户意图的单一表示
    - OSResponse: 统一出口 — 经过全栈处理的响应
    - CapabilityProvider: 能力接入规范
    - FreezeManifest: v1.0 冻结清单
    - DriftReport: 长期漂移检测报告
    - MemoryHealthReport: 记忆质量评估

核心边界:
    OS50-01: Interface ≠ Brain — UI 路由，不决策
    OS50-02: Benchmark ≠ Training — 度量，不优化
    OS50-03: Drift Detection ≠ Correction — 检测，不自动修复
    OS50-04: Memory Growth ≠ Accumulation — 质量优先
    OS50-05: Freeze ≠ Dead — ABI 稳定，实现可演化
    OS50-06: Capability ≠ Identity — 工具是提供者，不是自我
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# User Intent
# ═══════════════════════════════════════════════════════════════════════════════


class IntentDomain(Enum):
    """用户意图的领域分类。"""
    WRITING = "writing"
    CODING = "coding"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    PLANNING = "planning"
    MANAGEMENT = "management"
    LEARNING = "learning"
    GENERAL = "general"


class IntentComplexity(Enum):
    """意图复杂度。"""
    SIMPLE = "simple"       # 单步操作
    MODERATE = "moderate"   # 需要思考链
    COMPLEX = "complex"     # 多步分解
    PROJECT = "project"     # 长期项目


@dataclass
class UserIntent:
    """统一用户意图 — 单一入口。

    OS50-01: 意图只描述用户要什么，不预设如何做。
    """
    intent_id: str = ""
    raw_text: str = ""
    domain: IntentDomain = IntentDomain.GENERAL
    complexity: IntentComplexity = IntentComplexity.SIMPLE
    context_tags: list[str] = field(default_factory=list)
    priority: float = 0.5          # [0,1] 优先级


# ═══════════════════════════════════════════════════════════════════════════════
# OS Response
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OSResponse:
    """统一响应 — 全栈处理后的输出。

    包含:
        - result: 最终输出
        - reasoning: 决策链
        - meta: 元信息
        - signature: 用户认知特征标记
    """
    intent_id: str = ""
    result: str = ""
    reasoning_chain: list[str] = field(default_factory=list)
    confidence: float = 0.5
    user_signature_applied: bool = False
    decision_path: str = ""         # Phase 43 决策路径
    wisdom_used: list[str] = field(default_factory=list)
    tick_id: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Capability Provider (能力接入规范)
# ═══════════════════════════════════════════════════════════════════════════════


class CapabilityStatus(Enum):
    """能力状态。"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class CapabilityProvider:
    """能力提供者 — 外部工具的接入描述。

    OS50-06: 提供者是工具，不是 OCOS 的一部分。
    """
    name: str = ""
    domain: str = ""                # coding / writing / analysis / ...
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    version: str = "0.0.0"
    health_check_url: str = ""
    description: str = ""


@dataclass
class CapabilityResult:
    """能力调用结果。"""
    provider: str = ""
    success: bool = False
    output: str = ""
    error: str = ""
    duration_ticks: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Drift Report (漂移检测)
# ═══════════════════════════════════════════════════════════════════════════════


class DriftSeverity(Enum):
    """漂移严重度。"""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


@dataclass
class DriftSignal:
    """单个漂移信号。"""
    dimension: str = ""             # risk_tolerance / decision_style / interaction / ...
    previous_value: str = ""
    current_value: str = ""
    severity: DriftSeverity = DriftSeverity.NONE
    description: str = ""


@dataclass
class DriftReport:
    """漂移检测报告。

    OS50-03: 只报告，不自动纠正。
    """
    report_id: str = ""
    tick_id: int = 0
    signals: list[DriftSignal] = field(default_factory=list)
    overall_severity: DriftSeverity = DriftSeverity.NONE
    is_significant: bool = False
    recommendation: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Memory Health (记忆质量)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class MemoryHealthReport:
    """记忆健康报告。

    OS50-04: 度量质量，不度量数量。
    """
    tick_id: int = 0
    total_experiences: int = 0
    high_quality_count: int = 0      # importance >= 0.7
    stale_count: int = 0             # 从未被引用的
    aging_count: int = 0             # 正在老化的
    archived_count: int = 0          # 已归档的
    quality_score: float = 0.0       # [0,1] 综合质量分
    growth_trend: str = "stable"     # stable / improving / declining


# ═══════════════════════════════════════════════════════════════════════════════
# Freeze Manifest (v1.0 冻结)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FreezeManifest:
    """v1.0 冻结清单。

    OS50-05: ABI 稳定，实现继续演化 (Phase 47)。
    """
    version: str = "1.0.0"
    frozen_at_tick: int = 0
    abi_modules: list[str] = field(default_factory=list)
    constitution_ref: str = "constitution.yaml"
    memory_protocol: str = "v1"
    capability_sdk: str = "v1"
    extension_sdk: str = "v1"
    test_suite: str = "full-regression"
    signatures: list[str] = field(default_factory=list)  # 各模块签名


__all__ = [
    "IntentDomain", "IntentComplexity", "UserIntent",
    "OSResponse",
    "CapabilityStatus", "CapabilityProvider", "CapabilityResult",
    "DriftSeverity", "DriftSignal", "DriftReport",
    "MemoryHealthReport",
    "FreezeManifest",
]
