"""Phase 58.0: OCOS Health Examination Protocol.

OCOS v1.0 全身系统生产前健康审计。

五大体检:
    StructuralExaminer   — P39-P50 结构完整
    ConnectivityExaminer — 神经连接矩阵
    CognitiveExaminer    — 认知疾病检测
    ImmuneExaminer       — 免疫攻击测试
    RuntimeExaminer      — 运行时健康
    RecoveryExaminer     — 恢复能力

100分健康评分:
    90-100  HEALTHY
    75-90   STABLE
    60-75   WARNING
    <60     UNHEALTHY

核心概念:
    不是开发阶段，不是功能扩展。
    是对 OCOS v1.0 全身系统的健康审计。
    先证明健康，再证明长寿，最后让它工作。
"""

from ocos.health_examination.health_model import (
    HealthCategory, OrganStatus, DisorderType, AttackType,
    OrganDef, OCOS_ORGANS,
    OrganHealth, ConnectionHealth, DisorderFinding,
    ImmuneTestResult, RuntimeMetrics, RecoveryTestResult,
    CategoryScore, HealthCertification,
)
from ocos.health_examination.structural_examiner import StructuralExaminer
from ocos.health_examination.connectivity_examiner import ConnectivityExaminer, CONNECTIVITY_PAIRS
from ocos.health_examination.cognitive_examiner import (
    CognitiveExaminer, MemorySnapshot, DecisionSnapshot, WorldSnapshot,
)
from ocos.health_examination.immune_examiner import ImmuneExaminer
from ocos.health_examination.runtime_examiner import RuntimeExaminer
from ocos.health_examination.recovery_examiner import RecoveryExaminer, RecoveryState
from ocos.health_examination.health_scorer import HealthScorer
from ocos.health_examination.health_protocol import (
    HealthProtocol, HealthProtocolReport, quick_health_check,
)


__all__ = [
    # Types
    "HealthCategory", "OrganStatus", "DisorderType", "AttackType",
    "OrganDef", "OCOS_ORGANS",
    "OrganHealth", "ConnectionHealth", "DisorderFinding",
    "ImmuneTestResult", "RuntimeMetrics", "RecoveryTestResult",
    "CategoryScore", "HealthCertification",
    # Examiners
    "StructuralExaminer",
    "ConnectivityExaminer", "CONNECTIVITY_PAIRS",
    "CognitiveExaminer", "MemorySnapshot", "DecisionSnapshot", "WorldSnapshot",
    "ImmuneExaminer",
    "RuntimeExaminer",
    "RecoveryExaminer", "RecoveryState",
    # Scoring
    "HealthScorer",
    # Protocol
    "HealthProtocol", "HealthProtocolReport", "quick_health_check",
]
