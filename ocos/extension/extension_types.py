"""Phase 44: Extension Types — 认知扩展治理核心类型。

Cognitive Extension Governance 回答:
    "这个扩展是什么？是否符合自身结构？是否有价值？是否安全？是否应该接入？"

不是安装插件——而是认知器官整合。

生命周期:
    DISCOVERED → ANALYZING → VALIDATING → APPROVED → INTEGRATING → ACTIVE → FROZEN

核心边界:
    CG44-01: Extension ≠ Self Identity   — 我拥有能力 ≠ 我是这个能力
    CG44-02: Discovery ≠ Acceptance       — 发现 → 审核 → 批准 → 接入
    CG44-03: Integration ≠ Trust          — UNKNOWN → VERIFIED → TRUSTED
    CG44-04: Repair ≠ Self-Rewrite        — 维护自身，不能重新定义自身
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 扩展状态机
# ═══════════════════════════════════════════════════════════════════════════════


class ExtensionState(Enum):
    """扩展生命周期状态。"""
    DISCOVERED = "discovered"      # 已发现，待分析
    ANALYZING = "analyzing"        # 分析中
    ANALYZED = "analyzed"          # 分析完成
    VALIDATING = "validating"      # 沙箱验证中
    VALIDATED = "validated"        # 验证完成
    APPROVED = "approved"          # 已批准（等待集成）
    REJECTED = "rejected"          # 已拒绝
    INTEGRATING = "integrating"    # 集成中
    ACTIVE = "active"              # 活跃运行
    DEGRADED = "degraded"          # 降级运行
    ISOLATED = "isolated"          # 已隔离（出问题）
    FROZEN = "frozen"              # 已冻结（退役）

    @property
    def is_terminal(self) -> bool:
        return self in (ExtensionState.REJECTED, ExtensionState.FROZEN)

    @property
    def is_operational(self) -> bool:
        return self in (ExtensionState.ACTIVE, ExtensionState.DEGRADED)

    @property
    def is_pre_approval(self) -> bool:
        return self in (
            ExtensionState.DISCOVERED, ExtensionState.ANALYZING,
            ExtensionState.ANALYZED, ExtensionState.VALIDATING,
            ExtensionState.VALIDATED,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 扩展类型
# ═══════════════════════════════════════════════════════════════════════════════


class ExtensionType(Enum):
    """扩展类型——对应 OCOS 的认知层。"""
    PERCEPTION = "perception"        # 感知扩展 (audio/vision/sensors)
    MEMORY = "memory"                # 记忆扩展 (new storage backends)
    REASONING = "reasoning"          # 推理扩展 (new inference engines)
    CAPABILITY = "capability"        # 能力扩展 (tools/agents/APIs)
    COMMUNICATION = "communication"  # 通信扩展 (new channels)
    KNOWLEDGE = "knowledge"          # 知识扩展 (new domain models)
    META = "meta"                    # 元扩展 (monitoring/debugging)


class TrustLevel(Enum):
    """扩展信任等级。"""
    UNKNOWN = "unknown"      # 刚接入，未验证
    OBSERVING = "observing"  # 观察中
    VERIFIED = "verified"    # 经过验证
    TRUSTED = "trusted"      # 长期稳定
    DISTRUSTED = "distrusted"  # 不可信


# ═══════════════════════════════════════════════════════════════════════════════
# 扩展候选
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ExtensionCandidate:
    """扩展候选 — 发现新扩展时的原始信息。

    在 DISCOVERED 状态下创建。
    """

    candidate_id: str
    name: str
    extension_type: ExtensionType
    description: str = ""
    source_path: str = ""         # 文件路径或模块路径
    version: str = "0.0.0"
    declared_inputs: list[str] = field(default_factory=list)
    declared_outputs: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    discovered_tick: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# 分析报告
# ═══════════════════════════════════════════════════════════════════════════════


class ImpactLayer(Enum):
    """扩展影响的认知层。"""
    INPUT = "input"          # 感知/输入层
    PROCESSING = "processing"  # 处理层
    MEMORY = "memory"        # 记忆层
    DECISION = "decision"    # 决策层
    OUTPUT = "output"        # 输出/执行层
    META = "meta"            # 元层（监控/治理）


@dataclass(frozen=True)
class AnalysisReport:
    """分析报告 — 理解扩展是什么。

    输出:
        - 性质: 这是什么类型的扩展
        - 影响层: 它影响哪些认知层
        - 接口: 输入/输出格式
        - 依赖: 需要什么
    """

    candidate_id: str
    analysis_id: str
    extension_type: ExtensionType = ExtensionType.CAPABILITY
    summary: str = ""                    # 人类可读摘要
    impact_layers: list[ImpactLayer] = field(default_factory=list)
    input_schema: str = ""               # 输入结构描述
    output_schema: str = ""              # 输出结构描述
    dependencies: list[str] = field(default_factory=list)
    risks_identified: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 分析置信度


# ═══════════════════════════════════════════════════════════════════════════════
# 兼容性检查
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class CompatibilityReport:
    """兼容性报告 — 检查扩展与 OCOS 的兼容性。

    三个维度:
        - 架构兼容: 是否符合 7 层 Runtime 结构
        - ABI 兼容:    接口是否匹配
        - 治理兼容:    是否违反宪法约束
    """

    candidate_id: str
    report_id: str
    architecture_compatible: bool = True
    abi_compatible: bool = True
    governance_compatible: bool = True
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_fully_compatible(self) -> bool:
        return (self.architecture_compatible and
                self.abi_compatible and
                self.governance_compatible and
                len(self.issues) == 0)


# ═══════════════════════════════════════════════════════════════════════════════
# 沙箱验证
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SandboxResult:
    """沙箱验证结果。"""

    candidate_id: str
    passed: bool
    test_count: int = 0
    passed_count: int = 0
    errors: list[str] = field(default_factory=list)
    behavioral_notes: list[str] = field(default_factory=list)
    runtime_ticks: int = 0  # 沙箱运行时长


# ═══════════════════════════════════════════════════════════════════════════════
# 集成记录
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class IntegrationRecord:
    """集成记录 — 扩展正式接入后的连接信息。"""

    candidate_id: str
    integration_id: str
    connection_points: list[str] = field(default_factory=list)  # 接入点
    adapters_applied: list[str] = field(default_factory=list)    # 应用的适配器
    integrated_tick: int = 0
    trust_level: TrustLevel = TrustLevel.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# 扩展健康
# ═══════════════════════════════════════════════════════════════════════════════


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    FAILED = "failed"


@dataclass(frozen=True)
class HealthReport:
    """健康报告。"""

    candidate_id: str
    status: HealthStatus = HealthStatus.HEALTHY
    error_count: int = 0
    last_error: str = ""
    performance_score: float = 1.0  # [0, 1]
    cognitive_conflicts: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# 演化记录
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EvolutionEntry:
    """演化记忆条目 — 记录一个扩展的完整生命周期。"""

    candidate_id: str
    name: str
    state_history: list[tuple[ExtensionState, int]] = field(default_factory=list)
    integration_record: IntegrationRecord | None = None
    health_history: list[HealthReport] = field(default_factory=list)
    repair_events: list[str] = field(default_factory=list)
    frozen_tick: int | None = None
    frozen_reason: str = ""


__all__ = [
    "ExtensionState",
    "ExtensionType",
    "TrustLevel",
    "ExtensionCandidate",
    "ImpactLayer",
    "AnalysisReport",
    "CompatibilityReport",
    "SandboxResult",
    "IntegrationRecord",
    "HealthStatus",
    "HealthReport",
    "EvolutionEntry",
]
