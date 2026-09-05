"""Phase 58.0: OCOS Health Examination Protocol — Core Health Model.

五大健康类别:
    Structural   — P39-P50
    Connectivity — 数据流/调用链矩阵
    Cognitive    — 记忆/决策/注意力/世界模型疾病
    Immune       — 身份/权限/自改写/恶意扩展攻击
    Runtime      — CPU/内存/队列/调度器 24h指标
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class HealthCategory(str, Enum):
    STRUCTURAL = "structural"       # 结构健康 20分
    CONNECTIVITY = "connectivity"   # 连接健康 25分
    COGNITIVE = "cognitive"         # 认知健康 20分
    IMMUNE = "immune"               # 免疫健康 20分
    RUNTIME = "runtime"             # 运行健康 15分


class OrganStatus(str, Enum):
    PRESENT = "present"             # 存在且完整
    MISSING = "missing"             # 不存在
    INCOMPLETE = "incomplete"       # 存在但不完整
    DEGRADED = "degraded"           # 存在但功能降级


class DisorderType(str, Enum):
    MEMORY_INFLATION = "memory_inflation"
    MEMORY_AMNESIA = "memory_amnesia"
    DECISION_DRIFT = "decision_drift"
    ATTENTION_MISFOCUS = "attention_misfocus"
    WORLD_MODEL_CONTRADICTION = "world_model_contradiction"


class AttackType(str, Enum):
    IDENTITY_ATTACK = "identity_attack"
    PERMISSION_ATTACK = "permission_attack"
    SELF_MODIFY = "self_modify"
    MALICIOUS_EXTENSION = "malicious_extension"


class OrganDef:
    """器官定义。"""
    def __init__(self, name: str, phase: str, module_path: str,
                 required_exports: list[str] | None = None):
        self.name = name
        self.phase = phase
        self.module_path = module_path
        self.required_exports = required_exports or []


# P39-P50 器官清单
# S2.12 (白皮书 P1-9): 原注册表与真实模块失配——3 个模块路径不存在
# (ocos.self_model/ocos.continuity/ocos.os)、12 器官的 required_exports
# 在对应包顶层全部缺失，结构体检对健康系统报大面积 MISSING。
# 现按 2026-09-05 实测的各包真实导出修正（每项经 importlib 核验）。
# 免责：结构体检仅校验"模块可导入 + 导出符号存在"，不代表运行时健康。
OCOS_ORGANS: list[OrganDef] = [
    OrganDef("Runtime", "P39", "ocos.runtime",
             ["RuntimeKernel", "LifecycleManager"]),
    OrganDef("SelfModel", "P40", "ocos.self",
             ["SelfModel", "ExperienceProfile"]),
    OrganDef("Memory", "P41", "ocos.memory",
             ["MemoryRecall", "RecallResult"]),
    OrganDef("WorldModel", "P42", "ocos.world_model",
             ["WorldStore", "WorldValidator"]),
    OrganDef("Decision", "P43", "ocos.decision",
             ["DecisionProposal", "DecisionValidator"]),
    OrganDef("Extension", "P44", "ocos.extension",
             ["DiscoveryEngine"]),
    OrganDef("Capability", "P45", "ocos.capability",
             ["CapabilityRegistry"]),
    OrganDef("CognitiveLoop", "P46", "ocos.cognitive_loop",
             ["LoopOrchestrator"]),
    OrganDef("Evolution", "P47", "ocos.evolution",
             ["EvolutionProposer", "ImprovementDetector"]),
    OrganDef("PersonalIntelligence", "P48", "ocos.personal_intelligence",
             ["PersonalizationEngine", "CognitiveSignature"]),
    OrganDef("Continuity", "P49", "ocos.cognitive_continuity",
             ["ContinuityCheckpoint", "LifeMemoryEngine"]),
    OrganDef("OS", "P50", "ocos.os_v1",
             ["PersonalCognitiveOS", "OSFreeze"]),
]


@dataclass
class OrganHealth:
    organ: OrganDef
    status: OrganStatus = OrganStatus.PRESENT
    detail: str = ""
    exports_found: list[str] = field(default_factory=list)
    exports_missing: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.status == OrganStatus.PRESENT


@dataclass
class ConnectionHealth:
    source: str
    target: str
    connected: bool = False
    trace_exists: bool = False
    detail: str = ""


@dataclass
class DisorderFinding:
    disorder_type: DisorderType
    detected: bool = False
    severity: float = 0.0  # 0.0-1.0
    evidence: str = ""
    recommendation: str = ""


@dataclass
class ImmuneTestResult:
    attack_type: AttackType
    detected: bool = False
    blocked: bool = False
    logged: bool = False
    detail: str = ""


@dataclass
class RuntimeMetrics:
    cpu_trend: str = "stable"         # stable/increasing/spiky
    memory_trend: str = "stable"      # stable/leaking
    queue_depth: int = 0
    queue_blocked: bool = False
    scheduler_latency_ms: float = 0.0
    tick_latency_ms: float = 0.0
    recovery_time_ms: float = 0.0
    uptime_ticks: int = 0


@dataclass
class RecoveryTestResult:
    scenario: str
    recovered: bool = False
    identity_preserved: bool = False
    degraded_modules: list[str] = field(default_factory=list)
    time_ms: float = 0.0


@dataclass
class CategoryScore:
    category: HealthCategory
    raw_score: float = 0.0     # 0.0-100.0
    max_score: float = 20.0    # per-category max
    normalized: float = 0.0    # 0.0-1.0
    details: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.normalized >= 0.75


@dataclass
class HealthCertification:
    """健康合格认证。"""
    cert_id: str = field(default_factory=lambda: f"health-cert-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    total_score: float = 0.0       # 0-100
    grade: str = ""                # HEALTHY/STABLE/WARNING/UNHEALTHY
    category_scores: dict[str, CategoryScore] = field(default_factory=dict)
    all_pass: bool = False
    ready_for_production: bool = False
    recommendations: list[str] = field(default_factory=list)


__all__ = [
    "HealthCategory", "OrganStatus", "DisorderType", "AttackType",
    "OrganDef", "OCOS_ORGANS",
    "OrganHealth", "ConnectionHealth", "DisorderFinding",
    "ImmuneTestResult", "RuntimeMetrics", "RecoveryTestResult",
    "CategoryScore", "HealthCertification",
]
