"""Phase 50: Personal Cognitive OS v1.0 — Reality Validation.

从架构完成到运行验证。

核心组件:
    - PersonalCognitiveOS: 统一认知操作系统入口
    - CognitiveDriftDetector: 长期漂移检测
    - MemoryGrowthValidator: 记忆质量验证
    - CapabilityEcosystem: 能力生态适配器
    - OSFreeze: v1.0 ABI 冻结

核心边界:
    OS50-01: Interface ≠ Brain
    OS50-02: Benchmark ≠ Training
    OS50-03: Drift Detection ≠ Correction
    OS50-04: Memory Growth ≠ Accumulation
    OS50-05: Freeze ≠ Dead
    OS50-06: Capability ≠ Identity
"""

from ocos.os_v1.os_types import (
    IntentDomain, IntentComplexity, UserIntent,
    OSResponse,
    CapabilityStatus, CapabilityProvider, CapabilityResult,
    DriftSeverity, DriftSignal, DriftReport,
    MemoryHealthReport,
    FreezeManifest,
)
from ocos.os_v1.personal_os import PersonalCognitiveOS
from ocos.os_v1.cognitive_drift import DriftBaseline, CognitiveDriftDetector
from ocos.os_v1.memory_validation import MemoryGrowthValidator
from ocos.os_v1.capability_adapters import (
    CodexAdapter, OpenTaleAdapter, BrowserAdapter,
    AnalysisAdapter, CapabilityEcosystem,
)
from ocos.os_v1.freeze import (
    ABI_MODULES, CONSTITUTION_PRINCIPLES,
    MEMORY_PROTOCOL, CAPABILITY_SDK, EXTENSION_SDK,
    OSFreeze,
)

__all__ = [
    # Types
    "IntentDomain", "IntentComplexity", "UserIntent", "OSResponse",
    "CapabilityStatus", "CapabilityProvider", "CapabilityResult",
    "DriftSeverity", "DriftSignal", "DriftReport",
    "MemoryHealthReport", "FreezeManifest",
    # Core
    "PersonalCognitiveOS",
    "CognitiveDriftDetector", "DriftBaseline",
    "MemoryGrowthValidator",
    "CodexAdapter", "OpenTaleAdapter", "BrowserAdapter",
    "AnalysisAdapter", "CapabilityEcosystem",
    "OSFreeze",
    # Specs
    "ABI_MODULES", "CONSTITUTION_PRINCIPLES",
    "MEMORY_PROTOCOL", "CAPABILITY_SDK", "EXTENSION_SDK",
]
