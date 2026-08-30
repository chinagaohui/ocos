"""Phase 43: Personal Decision Intelligence — 个人决策智能。

Decision Intelligence 回答: "在当前情境下，我应该如何选择？"

接线状态（AUD-F13 选项 A, 2026-08-30）: 本组件链由 GAP-P1-1 接入
cognitive_loop/decision_pipeline（真实调用, decision_pipeline.py:73-114），
但该循环当前无生产消费者（备用引擎定位，见 cognitive_loop/__init__）。
生产 tick 决策 = AgentRuntime + DecisionBridge。组件本身完整可用。

输入:  Goal + Self Model + Personal Wisdom + World Model + Current Context
输出:  Decision Proposal (不是自动执行)

决策流水线:
    Context → Options → Risk Analysis → Value Evaluation → Decision Proposal
        ↓
    Human / Governance Approval
        ↓
    Capability Selection → Permission → Execution (Phase 45)

核心边界:
    D43-01: Decision ≠ Goal       — 分析世界不能产生目标
    D43-02: Decision ≠ Execution  — 必须经过 Capability→Permission→Execution
    D43-03: Wisdom ≠ Rule         — 过去经验形成倾向，不是"永远这样做"
"""

from ocos.decision.decision_types import (
    DecisionContext,
    OptionType,
    DecisionOption,
    RiskCategory,
    RiskLevel,
    RiskAssessment,
    ValueDimension,
    ValueEvaluation,
    DecisionState,
    DecisionProposal,
    DecisionTrace,
    DecisionResult,
)
from ocos.decision.context_builder import ContextBuilder
from ocos.decision.option_generator import OptionGenerator
from ocos.decision.risk_engine import RiskEngine
from ocos.decision.value_model import ValueModel
from ocos.decision.decision_trace import DecisionTracer
from ocos.decision.decision_validator import (
    Violation,
    DecisionValidationResult,
    DecisionValidator,
)

__all__ = [
    # Core Types
    "DecisionContext",
    "OptionType",
    "DecisionOption",
    "RiskCategory",
    "RiskLevel",
    "RiskAssessment",
    "ValueDimension",
    "ValueEvaluation",
    "DecisionState",
    "DecisionProposal",
    "DecisionTrace",
    "DecisionResult",
    # Pipeline
    "ContextBuilder",
    "OptionGenerator",
    "RiskEngine",
    "ValueModel",
    "DecisionTracer",
    # Governance
    "Violation",
    "DecisionValidationResult",
    "DecisionValidator",
]
