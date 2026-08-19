"""Phase 26: Result Understanding Layer。

Freeze §4.4 #9 — 完整的 Agent 输出后处理管道。

管道流程:
  1. validate()    — StatementValidator 禁令扫描
  2. structure()   — 从原始输出提取结构化指标（quality_score, duration, outcome）
  3. learn()       — 写入 CapabilityExperienceMemory + 更新 KnowledgeGraph

集成到 AgentRuntime 的 Tick Step 9 (result_ingest) 和 Step 10 (learning_consolidation)。

Phase 24-B 的 `ResultUnderstanding` + `ExaminationResult` 保持不变（向后兼容）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.constitution.statement_validator import StatementValidator, ValidationResult
from ocos.logging import get_logger

logger = get_logger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Phase 24-B compat: ResultUnderstanding + ExaminationResult (unchanged)
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ResultUnderstanding:
    """Phase 24-B compat: Agent 输出后处理器 — 强制 StatementValidator 扫描。"""

    validator: StatementValidator = field(default_factory=StatementValidator)
    block_on_violation: bool = False

    def examine(self, output: Any) -> ExaminationResult:
        results: dict[str, ValidationResult] = {}
        self._scan(output, "", results)
        all_clean = all(r.clean for r in results.values())
        return ExaminationResult(
            passed=all_clean,
            field_results=results,
            blocked=(not all_clean and self.block_on_violation),
        )

    def _scan(self, obj: Any, prefix: str, results: dict[str, ValidationResult]) -> None:
        if isinstance(obj, str):
            results[prefix or "output"] = self.validator.validate(obj)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, str):
                    results[key] = self.validator.validate(v)
                elif isinstance(v, (dict, list)):
                    self._scan(v, key, results)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                key = f"{prefix}[{i}]"
                if isinstance(v, str):
                    results[key] = self.validator.validate(v)
                elif isinstance(v, (dict, list)):
                    self._scan(v, key, results)


@dataclass(frozen=True)
class ExaminationResult:
    passed: bool
    field_results: dict[str, ValidationResult]
    blocked: bool = False

    def summary(self) -> str:
        if self.passed:
            return "ExaminationResult: ALL CLEAN"
        fields = [f"{k}: {v.summary()}" for k, v in self.field_results.items() if v.has_violations]
        return "ExaminationResult: VIOLATIONS\n" + "\n".join(fields)


# ══════════════════════════════════════════════════════════════════════════════
# Phase 26: ResultUnderstandingLayer — full pipeline
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class StructuredResult:
    """结构化结果 — validate → structure 的中间产物。"""
    capability_id: str
    provider_id: str
    outcome: str = "unknown"         # success / failure / partial
    quality_score: float = 0.5       # 0.0 ~ 1.0
    duration_ms: float = 0.0
    user_satisfaction: float = 0.5   # 0.0 ~ 1.0
    task_type: str = ""
    content_summary: str = ""        # 提取的简短摘要
    raw_output: str = ""

    @property
    def is_success(self) -> bool:
        return "success" in self.outcome.lower()


@dataclass
class ProcessedResult:
    """完整管道输出 — validate → structure → learn 的最终产物。

    Phase 37: 增加 cognitive_feedback 字段 (§1.2 Provenance Chain)。
    """
    validated: bool                  # 是否通过 StatementValidator
    structured: StructuredResult     # 结构化指标
    experience_stored: bool          # 是否已写入 ExperienceMemory
    kg_updated: bool                 # 是否已更新 KnowledgeGraph
    cognitive_feedback: Any = None   # Phase 37: CognitiveFeedback (frozen)
    validation_details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    result_id: str = ""              # Phase 37 §1.4: source_result_id
    timestamp: float = field(default_factory=time.time)


class ResultUnderstandingLayer:
    """Phase 26: 完整的 Agent 输出后处理管道。

    用法:
        layer = ResultUnderstandingLayer(experience=mem, kg=kg)

        # 在 Agent 执行完成后:
        processed = layer.process_result(
            output="code generated: ...",
            capability_id="code_generation",
            provider_id="codex",
        )

    管道自动完成：
      1. StatementValidator 扫描 → validated
      2. 提取结构化指标 → structured
      3. 写入 ExperienceMemory → experience_stored
      4. 更新 KnowledgeGraph → kg_updated
    """

    def __init__(
        self,
        *,
        experience: Any = None,       # CapabilityExperienceMemory (optional)
        kg: Any = None,               # KnowledgeGraph (optional)
        validator: Optional[StatementValidator] = None,
        auto_learn: bool = True,      # 是否自动调用 learn()
        block_on_violation: bool = False,
    ):
        self._experience = experience
        self._kg = kg
        self._validator = validator or StatementValidator()
        self._auto_learn = auto_learn
        self._block_on_violation = block_on_violation

    # ── 1. validate ────────────────────────────────────────────────────────

    def validate(self, output: Any) -> ExaminationResult:
        """Phase 24-B compat: StatementValidator 扫描."""
        ru = ResultUnderstanding(validator=self._validator, block_on_violation=self._block_on_violation)
        return ru.examine(output)

    # ── 2. structure ───────────────────────────────────────────────────────

    def structure(
        self,
        output: Any,
        *,
        capability_id: str = "unknown",
        provider_id: str = "unknown",
        task_type: str = "",
        outcome: str = "unknown",
        quality_score: Optional[float] = None,
        duration_ms: float = 0.0,
        user_satisfaction: Optional[float] = None,
    ) -> StructuredResult:
        """从原始输出提取结构化指标.

        如果 quality_score / user_satisfaction 未显式传入，
        尝试从 output dict 中自动提取（key heuristic）。
        """
        raw_str = self._to_string(output)

        # Auto-extract quality score if not provided
        if quality_score is None and isinstance(output, dict):
            quality_score = self._extract_numeric(output, {"quality_score", "quality", "score", "confidence"})
        if quality_score is None:
            quality_score = 0.5

        if user_satisfaction is None and isinstance(output, dict):
            user_satisfaction = self._extract_numeric(output, {"satisfaction", "user_satisfaction", "rating"})
        if user_satisfaction is None:
            user_satisfaction = 0.5

        # Clamp
        quality_score = max(0.0, min(1.0, quality_score))
        user_satisfaction = max(0.0, min(1.0, user_satisfaction))

        # Content summary: first 200 chars of raw output
        content_summary = raw_str[:200] if len(raw_str) > 200 else raw_str

        return StructuredResult(
            capability_id=capability_id,
            provider_id=provider_id,
            outcome=outcome,
            quality_score=quality_score,
            duration_ms=duration_ms,
            user_satisfaction=user_satisfaction,
            task_type=task_type or capability_id,
            content_summary=content_summary.strip(),
            raw_output=raw_str,
        )

    # ── 3. learn ───────────────────────────────────────────────────────────

    def learn(self, structured: StructuredResult) -> dict[str, bool]:
        """将结构化结果写入 ExperienceMemory 和 KnowledgeGraph.

        Returns:
            {"experience_stored": bool, "kg_updated": bool}
        """
        result = {"experience_stored": False, "kg_updated": False}

        # 写入 ExperienceMemory
        if self._experience is not None:
            try:
                from ocos.capability.knowledge_graph import ExperienceNode

                exp_node = ExperienceNode(
                    experience_id=f"exp-{structured.capability_id}-{structured.provider_id}-{int(time.time()*1000)}",
                    task_type=structured.task_type,
                    capability_id=structured.capability_id,
                    provider_id=structured.provider_id,
                    outcome=structured.outcome,
                    quality_score=structured.quality_score,
                    duration_ms=int(structured.duration_ms),
                    user_satisfaction=structured.user_satisfaction,
                )
                self._experience.save(exp_node)
                result["experience_stored"] = True
                logger.debug("experience stored: %s", exp_node.experience_id)
            except Exception as e:
                logger.error("failed to store experience: %s", e)

        # 更新 KnowledgeGraph
        if self._kg is not None:
            try:
                from ocos.capability.knowledge_graph import ExperienceNode, EdgeType

                exp_node = ExperienceNode(
                    experience_id=f"exp-{structured.capability_id}-{structured.provider_id}-{int(time.time()*1000)}",
                    task_type=structured.task_type,
                    capability_id=structured.capability_id,
                    provider_id=structured.provider_id,
                    outcome=structured.outcome,
                    quality_score=structured.quality_score,
                    duration_ms=int(structured.duration_ms),
                    user_satisfaction=structured.user_satisfaction,
                )
                self._kg.add_experience(exp_node)
                self._kg.add_edge(exp_node.experience_id, EdgeType.INSTANCE_OF, structured.capability_id)
                self._kg.add_edge(exp_node.experience_id, EdgeType.PROVIDED_BY, structured.provider_id)
                result["kg_updated"] = True
                logger.debug("KG updated with experience: %s", exp_node.experience_id)
            except Exception as e:
                logger.error("failed to update KG: %s", e)

        return result

    # ── 4. pipeline ────────────────────────────────────────────────────────

    def process_result(
        self,
        output: Any,
        *,
        capability_id: str = "unknown",
        provider_id: str = "unknown",
        task_type: str = "",
        outcome: str = "unknown",
        quality_score: Optional[float] = None,
        duration_ms: float = 0.0,
        user_satisfaction: Optional[float] = None,
    ) -> ProcessedResult:
        """完整的 验证→结构化→学习 管道。

        Args:
            output: Agent 原始输出（str / dict）
            capability_id: 使用的能力 ID
            provider_id: 提供能力的 Provider ID
            task_type: 任务类型（默认 = capability_id）
            outcome: 结果状态
            quality_score: 质量评分（可选，尝试自动提取）
            duration_ms: 执行耗时
            user_satisfaction: 用户满意度（可选，尝试自动提取）

        Returns:
            ProcessedResult with all pipeline outcomes
        """
        errors: list[str] = []

        # 1. Validate
        examination = self.validate(output)
        validated = examination.passed
        if not validated:
            errors.append(examination.summary())

        # 2. Structure
        structured = self.structure(
            output,
            capability_id=capability_id,
            provider_id=provider_id,
            task_type=task_type,
            outcome=outcome,
            quality_score=quality_score,
            duration_ms=duration_ms,
            user_satisfaction=user_satisfaction,
        )

        # 2.5 Phase 37: Generate CognitiveFeedback (§1.2 Provenance Chain)
        cognitive_feedback = self._generate_feedback(
            structured,
            validated=validated,
        )

        # 3. Learn
        learn_result = {"experience_stored": False, "kg_updated": False}
        if self._auto_learn:
            learn_result = self.learn(structured)

        return ProcessedResult(
            validated=validated,
            structured=structured,
            experience_stored=learn_result["experience_stored"],
            kg_updated=learn_result["kg_updated"],
            cognitive_feedback=cognitive_feedback,
            validation_details={"examination": examination},
            errors=errors,
            result_id=getattr(cognitive_feedback, "feedback_id", ""),
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _generate_feedback(
        self,
        structured: StructuredResult,
        *,
        validated: bool = True,
        outcome_evaluator: Any = None,
    ) -> "CognitiveFeedback":
        """Phase 37 §1.2: 生成 CognitiveFeedback — Validator → Evaluator → Feedback。

        从 validated StructuredResult 创建 frozen CognitiveFeedback。
        注意：必须在 Validator 通过后才调用（即使 failed 也可记录，但标记 status）。
        """
        import uuid
        from ocos.contracts.feedback_abi import (
            CognitiveFeedback, ExpectedOutcome, ActualOutcome, FeedbackState,
        )
        from ocos.capability.outcome_evaluation import OutcomeEvaluator

        feedback_id = f"fb-{uuid.uuid4().hex[:12]}"
        result_id = f"result-{uuid.uuid4().hex[:12]}"

        # 构造 CognitiveFeedback
        expected = ExpectedOutcome(
            predicted_success_prob=structured.quality_score,
            estimated_duration_ms=float(structured.duration_ms),
            estimated_quality=structured.quality_score,
        )

        actual = ActualOutcome(
            success=structured.is_success,
            quality_score=structured.quality_score,
            duration_ms=float(structured.duration_ms),
            user_alignment=structured.user_satisfaction,
        )

        feedback = CognitiveFeedback(
            feedback_id=feedback_id,
            source_result_id=result_id,
            evaluator_version=OutcomeEvaluator.VERSION,
            capability_id=structured.capability_id,
            provider_id=structured.provider_id,
            expected=expected,
            actual=actual,
            state=FeedbackState.TEMPORARY,
        )

        # 执行 OutcomeEvaluation（§2）
        try:
            evaluator = outcome_evaluator or OutcomeEvaluator()
            evaluation = evaluator.evaluate(feedback)
        except Exception:
            from ocos.contracts.feedback_abi import OutcomeEvaluation
            evaluation = OutcomeEvaluation(score=0.0)

        # 使用 object.__setattr__ 绕过 frozen
        object.__setattr__(feedback, "evaluation", evaluation)

        return feedback

    @staticmethod
    def _to_string(obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            # Try to extract a meaningful text field
            for key in ("output", "result", "text", "content", "message", "response"):
                v = obj.get(key)
                if isinstance(v, str) and v.strip():
                    return v
            return str(obj)
        if isinstance(obj, (list, tuple)):
            return "\n".join(ResultUnderstandingLayer._to_string(i) for i in obj)
        return str(obj)

    @staticmethod
    def _extract_numeric(data: dict, keys: set[str]) -> Optional[float]:
        for key in keys:
            v = data.get(key)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return float(v)
            if isinstance(v, str):
                try:
                    return float(v)
                except ValueError:
                    continue
        return None
