"""Phase 48: Personal Intelligence Maturity — 个人智能成熟度。

不是增加新器官，而是让 OCOS 成为真正属于某一个人的长期智能。

核心维度:
    - Cognitive Signature: 用户认知特征
    - Consistency: 长期一致性
    - Meta-Cognition: 元认知——"我为什么这样判断？"
    - Goal Coordination: 长期目标协调（不创造目标）
    - Personalization: 个性化适配

核心边界:
    PM48-01: Personalization != Overfitting
    PM48-02: Meta-cognition != Self-doubt
    PM48-03: Goal Coordination != Goal Creation
    PM48-04: Consistency != Rigidity
"""

from ocos.personal_intelligence.pi_types import (
    RiskTolerance,
    ExplanationDepth,
    InteractionStyle,
    DomainPriority,
    CognitiveSignature,
    ConsistencyMetrics,
    DecisionRationale,
    GoalStatus,
    LongTermGoal,
    MaturityLevel,
)
from ocos.personal_intelligence.cognitive_signature import CognitiveSignatureEngine
from ocos.personal_intelligence.consistency_monitor import ConsistencyMonitor
from ocos.personal_intelligence.meta_cognition import MetaCognitionEngine
from ocos.personal_intelligence.goal_coordinator import GoalCoordinator
from ocos.personal_intelligence.personalization_engine import PersonalizationEngine
from ocos.personal_intelligence.maturity_metrics import (
    MaturityReport, calculate_maturity,
)

__all__ = [
    # Types
    "RiskTolerance", "ExplanationDepth", "InteractionStyle",
    "DomainPriority", "CognitiveSignature", "ConsistencyMetrics",
    "DecisionRationale", "GoalStatus", "LongTermGoal", "MaturityLevel",
    # Engines
    "CognitiveSignatureEngine", "ConsistencyMonitor",
    "MetaCognitionEngine", "GoalCoordinator",
    "PersonalizationEngine",
    # Metrics
    "MaturityReport", "calculate_maturity",
]
