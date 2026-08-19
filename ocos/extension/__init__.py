"""Phase 44: Cognitive Extension Governance — 认知扩展治理。

让 OCOS 能够审核并吸收经过批准的新认知组件。

不是安装插件 — 而是认知器官整合。

完整生命周期:
    DISCOVERED → ANALYZING → ANALYZED → VALIDATING → VALIDATED
    → APPROVED → INTEGRATING → ACTIVE → [DEGRADED | ISOLATED] → FROZEN

核心边界:
    CG44-01: Extension ≠ Self Identity    — 我拥有能力 ≠ 我是这个能力
    CG44-02: Discovery ≠ Acceptance        — 发现 → 审核 → 批准 → 接入
    CG44-03: Integration ≠ Trust           — UNKNOWN → VERIFIED → TRUSTED
    CG44-04: Repair ≠ Self-Rewrite         — 维护自身，不能重新定义自身
"""

from ocos.extension.extension_types import (
    ExtensionState,
    ExtensionType,
    TrustLevel,
    ExtensionCandidate,
    ImpactLayer,
    AnalysisReport,
    CompatibilityReport,
    SandboxResult,
    IntegrationRecord,
    HealthStatus,
    HealthReport,
    EvolutionEntry,
)
from ocos.extension.discovery_engine import DiscoveryEngine
from ocos.extension.analyzer import Analyzer
from ocos.extension.compatibility_checker import (
    CompatibilityChecker,
    FORBIDDEN_ACTIONS,
    FORBIDDEN_LAYER_ACCESS,
)
from ocos.extension.sandbox_runner import SandboxRunner
from ocos.extension.approval_engine import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalEngine,
)
from ocos.extension.integration_engine import IntegrationEngine
from ocos.extension.diagnosis_engine import DiagnosisEngine
from ocos.extension.repair_engine import (
    RepairAction,
    RepairActionForbidden,
    RepairEngine,
)
from ocos.extension.evolution_memory import EvolutionMemory

__all__ = [
    # Types
    "ExtensionState", "ExtensionType", "TrustLevel",
    "ExtensionCandidate", "ImpactLayer",
    "AnalysisReport", "CompatibilityReport", "SandboxResult",
    "IntegrationRecord", "HealthStatus", "HealthReport", "EvolutionEntry",
    # Engines
    "DiscoveryEngine", "Analyzer", "CompatibilityChecker",
    "SandboxRunner",
    "ApprovalDecision", "ApprovalRequest", "ApprovalEngine",
    "IntegrationEngine", "DiagnosisEngine",
    "RepairAction", "RepairActionForbidden", "RepairEngine",
    "EvolutionMemory",
    # Governance constants
    "FORBIDDEN_ACTIONS", "FORBIDDEN_LAYER_ACCESS",
]
