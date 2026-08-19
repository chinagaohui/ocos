"""Phase 57: Living System Verification.

OCOS 活体系统验证层 — 不是增加新器官，而是系统级证明。

六大验收标准:
    LV57-01: 全链路闭环 — Intent → Memory 100% 可追踪
    LV57-02: 长期运行 — 无 identity 漂移 / memory 污染 / permission 突破
    LV57-03: 故障恢复 — 注入故障后系统继续运行
    LV57-04: 能力真实性 — 注册 ≠ 执行
    LV57-05: 演化安全 — 任何 self-rewrite 被拒绝
    LV57-06: 人格连续性 — Day N snapshot 仍是同一个 OCOS

组件:
    SimulationEngine      — 认知生命模拟 (1000+ tick)
    CognitiveTraceAudit   — 全链路因果追踪审计
    FailureInjector       — 故障注入与免疫压力测试
    LongevityTest         — 长期运行稳定性
    BenchmarkRunner       — 真实任务基准 (Benchmark A/B/C)
    HealthReportGenerator — 统一健康报告 (ALIVE/DEGRADED/UNSTABLE/DEAD)
    VerificationManifest  — 验证清单 (20 条目)

Phases 39-56 构建了 OCOS 的身体器官;
Phase 57 证明这具身体真的活着。
"""

from ocos.living_verification.simulation_engine import (
    SimulationEngine, SimulationProfile, TraceStep, SimPhase,
)
from ocos.living_verification.cognitive_trace_audit import (
    CognitiveTraceAudit, TraceAuditReport, ChainLink, CausalValidation,
)
from ocos.living_verification.failure_injector import (
    FailureInjector, InjectionReport, InjectionBatchReport,
    InjectionType, InjectionResult,
)
from ocos.living_verification.longevity_test import (
    LongevityTest, LongevityCheckpoint, LongevityMetrics,
)
from ocos.living_verification.benchmark_runner import (
    BenchmarkRunner, BenchmarkReport, BenchmarkTask, BenchmarkSuite,
    BenchmarkCategory, BenchmarkVerdict,
)
from ocos.living_verification.health_report import (
    HealthReportGenerator, LivingSystemHealth, HealthDimension, SystemGrade,
)
from ocos.living_verification.verification_manifest import (
    VerificationManifest, ManifestItem, ManifestStatus, create_full_manifest,
)


__all__ = [
    "SimulationEngine", "SimulationProfile", "TraceStep", "SimPhase",
    "CognitiveTraceAudit", "TraceAuditReport", "ChainLink", "CausalValidation",
    "FailureInjector", "InjectionReport", "InjectionBatchReport",
    "InjectionType", "InjectionResult",
    "LongevityTest", "LongevityCheckpoint", "LongevityMetrics",
    "BenchmarkRunner", "BenchmarkReport", "BenchmarkTask", "BenchmarkSuite",
    "BenchmarkCategory", "BenchmarkVerdict",
    "HealthReportGenerator", "LivingSystemHealth", "HealthDimension", "SystemGrade",
    "VerificationManifest", "ManifestItem", "ManifestStatus", "create_full_manifest",
]
