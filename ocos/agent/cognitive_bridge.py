"""CognitiveBridge — 认知桥接层。

Phase 22: Subject Emergence

职责:
  - 将 MasterAgent 的显式指令路由到正确的引擎
  - 纯同步包装器，不包含任何自动选择/优化逻辑
  - 所有 cognitive 参数由 MasterAgent 显式提供

设计约束 (Phase Isolation — Article 0):
  - 不包含 Capability Selection 逻辑
  - 不包含 Skill Discovery 逻辑
  - 不包含 Process Optimization 逻辑
  - 仅接受显式 strategy/operation 字符串并透传到引擎
  - 不导入 SkillGraph、CapabilitySelector、EpisodicMemory、SelfModel

Engine 无 Goal/Decision 创建权:
  - Bridge 只是消息路由，不能创建 Goal 或修改 Agent 状态
  - 所有 Goal 创建由 ControlLoop 负责

Bridge Transparency Rule (Phase 22 Constitution):
  Bridge shall translate, never decide.
  可以: 路由 (route)、参数转换 (transform)、ABI 适配 (adapt)
  不能: 推理 (reason)、决策 (decide)、修改 Goal、修改 Identity、修改 Memory、修改 Constitution
  所有决策权属于 MasterAgent — 此约束保持到 Phase 27
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.models.process import TransformProcess, ProcessType
from ocos.kernel.abi import Observation


@dataclass
class BridgeResult:
    """标准化的引擎调用结果。

    统一包装所有引擎的 RuntimeResult，提供一致的接口。
    """

    success: bool
    message: str
    trace_id: str = ""
    process_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_observation(self, source: str = "cognitive_bridge") -> Observation:
        """转换为 Observation 供后续阶段使用。"""
        return Observation(
            source=source,
            content={
                "bridge_result": self.success,
                "message": self.message,
                "trace_id": self.trace_id,
                "process_id": self.process_id,
                "data": self.data,
            },
        )


class CognitiveBridge:
    """认知桥接层 — MasterAgent 与 Engine 之间的显式路由。

    用法:
        bridge = CognitiveBridge(
            reasoning_engine=reasoning_engine,
            planning_engine=planning_engine,
            decision_engine=decision_engine,
            reflection_engine=reflection_engine,
            learning_engine=learning_engine,
        )
        result = bridge.reason(operation="deduction", premises={"inputs": [...]})
    """

    def __init__(
        self,
        reasoning_engine: Any = None,
        planning_engine: Any = None,
        decision_engine: Any = None,
        reflection_engine: Any = None,
        learning_engine: Any = None,
    ) -> None:
        self._reasoning = reasoning_engine
        self._planning = planning_engine
        self._decision = decision_engine
        self._reflection = reflection_engine
        self._learning = learning_engine

    # ── 推理桥接 ────────────────────────────────────────────────────

    def reason(
        self,
        operation: str = "deduction",
        premises: Optional[dict[str, Any]] = None,
        confidence: float = 0.9,
    ) -> BridgeResult:
        """调用 ReasoningEngine 执行推理。

        Args:
            operation: 推理操作名称 (deduction, induction, abduction, analogy,
                       analysis, synthesis, comparison, evaluation)
            premises: 推理前提数据
            confidence: 置信度
        """
        if self._reasoning is None:
            return BridgeResult(
                success=False,
                message="ReasoningEngine not available",
                errors=["no reasoning engine configured"],
            )

        try:
            process = TransformProcess(
                process_type=ProcessType.REASONING,
                confidence=confidence,
                metadata={"operation": operation},
            )
            engine_result = self._reasoning.execute(
                process=process,
                operation=operation,
                premises=premises,
            )
            return BridgeResult(
                success=engine_result.success,
                message=engine_result.message,
                trace_id=getattr(engine_result, "trace_id", ""),
                process_id=getattr(engine_result, "process_id", ""),
                data={
                    "steps": getattr(engine_result, "steps", 0),
                    "output_addresses": getattr(
                        engine_result, "output_addresses", ()
                    ),
                },
            )
        except Exception as e:
            return BridgeResult(
                success=False,
                message=f"Reasoning failed: {e}",
                errors=[str(e)],
            )

    # ── 规划桥接 ────────────────────────────────────────────────────

    def plan(
        self,
        strategy: str = "top_down",
        inputs: Optional[dict[str, Any]] = None,
    ) -> BridgeResult:
        """调用 PlanningEngine 执行规划。

        Args:
            strategy: 规划策略 (top_down, bottom_up, means_end,
                      case_based, iterative, parallel)
            inputs: 规划输入 (goal, constraints 等)
        """
        if self._planning is None:
            return BridgeResult(
                success=False,
                message="PlanningEngine not available",
                errors=["no planning engine configured"],
            )

        try:
            process = TransformProcess(
                process_type=ProcessType.PLANNING,
                metadata={"strategy": strategy},
            )
            engine_result = self._planning.execute(
                process=process,
                strategy=strategy,
                inputs=inputs,
            )
            return BridgeResult(
                success=engine_result.success,
                message=engine_result.message,
                trace_id=getattr(engine_result, "trace_id", ""),
                process_id=getattr(engine_result, "process_id", ""),
                data={
                    "step_count": getattr(engine_result, "step_count", 0),
                    "output_addresses": getattr(
                        engine_result, "output_addresses", ()
                    ),
                },
            )
        except Exception as e:
            return BridgeResult(
                success=False,
                message=f"Planning failed: {e}",
                errors=[str(e)],
            )

    # ── 决策桥接 ────────────────────────────────────────────────────

    def decide(
        self,
        strategy: str = "scoring",
        options: Optional[list[dict[str, Any]]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> BridgeResult:
        """调用 DecisionMakingEngine 执行决策。

        Args:
            strategy: 决策策略 (scoring, ranking, majority,
                      satisficing, opportunity_cost, pareto)
            options: 候选选项列表
            context: 决策上下文 (weights, threshold 等)
        """
        if self._decision is None:
            return BridgeResult(
                success=False,
                message="DecisionMakingEngine not available",
                errors=["no decision engine configured"],
            )

        try:
            process = TransformProcess(
                process_type=ProcessType.DECISION,
                metadata={"strategy": strategy},
            )
            engine_result = self._decision.execute(
                process=process,
                strategy=strategy,
                options_data=options,
                context=context,
            )
            return BridgeResult(
                success=engine_result.success,
                message=engine_result.message,
                trace_id=getattr(engine_result, "trace_id", ""),
                process_id=getattr(engine_result, "process_id", ""),
                data={
                    "selected_option_id": getattr(
                        engine_result, "selected_option_id", ""
                    ),
                    "option_count": getattr(engine_result, "option_count", 0),
                },
            )
        except Exception as e:
            return BridgeResult(
                success=False,
                message=f"Decision failed: {e}",
                errors=[str(e)],
            )

    # ── 反思桥接 ────────────────────────────────────────────────────

    def reflect(
        self,
        subject_type: str = "action_result",
        subject_id: str = "",
        strategy: str = "standard",
    ) -> BridgeResult:
        """调用 ReflectionEngine 执行反思。

        Args:
            subject_type: 反思对象类型
            subject_id: 反思对象 ID
            strategy: 反思策略 (standard, deep, quick, comparative)
        """
        if self._reflection is None:
            return BridgeResult(
                success=False,
                message="ReflectionEngine not available",
                errors=["no reflection engine configured"],
            )

        try:
            # ReflectionEngine 有三种 execute 签名，尝试标准方式
            engine_result = self._reflection.execute(
                subject_type=subject_type,
                subject_id=subject_id,
                strategy=strategy,
            )
            return BridgeResult(
                success=getattr(engine_result, "success", True),
                message=getattr(engine_result, "message", ""),
                trace_id=getattr(engine_result, "trace_id", ""),
                data={
                    "insight_count": len(
                        getattr(engine_result, "insights", [])
                    ),
                },
            )
        except TypeError:
            # 回退：创建 Process 调用
            try:
                process = TransformProcess(
                    process_type=ProcessType.PLANNING,
                    metadata={
                        "subject_type": subject_type,
                        "subject_id": subject_id,
                        "strategy": strategy,
                    },
                )
                engine_result = self._reflection.execute(
                    process=process,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    strategy=strategy,
                )
                return BridgeResult(
                    success=getattr(engine_result, "success", True),
                    message=getattr(engine_result, "message", ""),
                    trace_id=getattr(engine_result, "trace_id", ""),
                )
            except Exception as e:
                return BridgeResult(
                    success=False,
                    message=f"Reflection failed: {e}",
                    errors=[str(e)],
                )
        except Exception as e:
            return BridgeResult(
                success=False,
                message=f"Reflection failed: {e}",
                errors=[str(e)],
            )

    # ── 学习桥接 ────────────────────────────────────────────────────

    def learn(
        self,
        model: Any = None,
        examples: Optional[list[Any]] = None,
        strategy: str = "supervised",
    ) -> BridgeResult:
        """调用 LearningEngine 执行学习。

        Args:
            model: 当前模型（可选）
            examples: 训练样本
            strategy: 学习策略 (supervised, reinforcement,
                      pattern_discovery, transfer)
        """
        if self._learning is None:
            return BridgeResult(
                success=False,
                message="LearningEngine not available",
                errors=["no learning engine configured"],
            )

        try:
            engine_result = self._learning.execute(
                model=model,
                examples=examples or [],
                strategy=strategy,
            )
            return BridgeResult(
                success=getattr(engine_result, "success", True),
                message=getattr(engine_result, "message", ""),
                trace_id=getattr(engine_result, "trace_id", ""),
                data={
                    "patterns_learned": len(
                        getattr(engine_result, "new_patterns", [])
                    ),
                },
            )
        except TypeError:
            try:
                process = TransformProcess(
                    process_type=ProcessType.PLANNING,
                    metadata={"strategy": strategy},
                )
                engine_result = self._learning.execute(
                    process=process,
                    model=model,
                    examples=examples or [],
                    strategy=strategy,
                )
                return BridgeResult(
                    success=getattr(engine_result, "success", True),
                    message=getattr(engine_result, "message", ""),
                    trace_id=getattr(engine_result, "trace_id", ""),
                )
            except Exception as e:
                return BridgeResult(
                    success=False,
                    message=f"Learning failed: {e}",
                    errors=[str(e)],
                )
        except Exception as e:
            return BridgeResult(
                success=False,
                message=f"Learning failed: {e}",
                errors=[str(e)],
            )
