"""Phase 47: Cognitive Evolution Governance — 认知进化治理。

回答最后一个核心问题:
    如何在保持自身稳定的情况下，持续变得更好？

不是"Self Evolution"——而是受治理的、信号驱动的改进。

完整进化闭环:
    Run → Detect → Propose → Analyze → Sandbox → Approve → Migrate → Monitor → Learn

核心边界:
    CE47-01: Evolution ≠ Autonomy  — 由信号触发，非自决
    CE47-02: Proposal ≠ Execution  — 需多层审批
    CE47-03: Migration ≠ Destruction — 快照 + 可回滚
    CE47-04: Evolution ≠ Identity Change — 禁止修改 identity/constitution/permission
"""

from ocos.evolution.evolution_types import (
    EvolutionState,
    EvolutionTrigger,
    EvolutionDomain,
    FORBIDDEN_DOMAINS,
    ImpactLevel,
    ImpactAssessment,
    EvolutionProposal,
    RollbackReason,
    RollbackRecord,
)
from ocos.evolution.improvement_detector import (
    DetectedSignal, ImprovementDetector,
)
from ocos.evolution.evolution_proposer import EvolutionProposer
from ocos.evolution.impact_analyzer import ImpactAnalyzer
from ocos.evolution.evolution_sandbox import (
    SandboxResult, SandboxReport, EvolutionSandbox,
)
from ocos.evolution.approval_engine import (
    ApprovalVerdict, ApprovalRecord, ApprovalEngine,
)
from ocos.evolution.migration_engine import (
    MigrationResult, MigrationEngine,
)
from ocos.evolution.rollback_engine import RollbackEngine
from ocos.evolution.evolution_memory import EvolutionMemory

__all__ = [
    # Types
    "EvolutionState",
    "EvolutionTrigger",
    "EvolutionDomain",
    "FORBIDDEN_DOMAINS",
    "ImpactLevel",
    "ImpactAssessment",
    "EvolutionProposal",
    "RollbackReason",
    "RollbackRecord",
    # Detection
    "DetectedSignal",
    "ImprovementDetector",
    # Proposal
    "EvolutionProposer",
    # Analysis & Sandbox
    "ImpactAnalyzer",
    "SandboxResult",
    "SandboxReport",
    "EvolutionSandbox",
    # Governance
    "ApprovalVerdict",
    "ApprovalRecord",
    "ApprovalEngine",
    # Execution
    "MigrationResult",
    "MigrationEngine",
    "RollbackEngine",
    # Memory
    "EvolutionMemory",
]
