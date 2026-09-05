"""Phase 24.1 — ExperienceBuilder。

Trace → ExperienceCandidate 构建器。

Phase 24 的第一件事: 识别"一段完整经历"。

设计原则:
  - COMPLETE 保留，INCOMPLETE 也保留（不丢弃）
  - 所有 Candidate 不可变（frozen dataclass）
  - Self 字段从构建时开始扫描
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ocos.memory.experience.models import (
    TraceBundle,
    ExperienceCandidate,
    ExperienceStatus,
    ExperienceSource,
)
from ocos.memory.experience.validator import ExperienceValidator
from ocos.memory.experience.lessons import LessonsLearned


class ExperienceBuilder:
    """Trace → ExperienceCandidate 构建器。"""

    def __init__(self) -> None:
        self._candidates: list[ExperienceCandidate] = []

    # ── 构建 ───────────────────────────────────────────────────────────────

    def build(
        self,
        trace_bundle: TraceBundle,
        source: ExperienceSource,
        context: dict,
    ) -> ExperienceCandidate:
        """从 Trace 构建 ExperienceCandidate。

        五要素齐全 → COMPLETE
        五要素缺失 → INCOMPLETE（保留，不丢弃）
        """
        # 1. Validator 检查 Self 字段
        violations = ExperienceValidator.validate_trace_bundle(trace_bundle)

        # 2. 检查五要素是否齐全
        complete, missing = ExperienceValidator.required_fields_present(
            trace_bundle
        )

        # 3. 创建 Candidate
        status = (
            ExperienceStatus.COMPLETE if complete
            else ExperienceStatus.INCOMPLETE
        )
        candidate = ExperienceCandidate.create(
            trace_bundle=trace_bundle,
            source=source,
            context=context,
            status=status,
        )

        # 4. 记录不完整原因 / Self 违规（供调试）
        if not complete:
            object.__setattr__(
                candidate,
                "rejection_reason",
                f"missing: {', '.join(missing)}",
            )
        if violations:
            existing = candidate.rejection_reason or ""
            suffix = f"; self_violations: {', '.join(violations)}"
            object.__setattr__(
                candidate,
                "rejection_reason",
                existing + suffix,
            )
            # S2.3 (白皮书 P2, Boundary 门): 严格模式下 Self 污染候选
            # 置 REJECTED —— SignificanceGate 对非 COMPLETE 一律 FAIL，
            # 从而真正阻断入库。默认（false）保持原行为仅记录。
            import os as _os
            # S3.13: 默认严格（true）——Self 污染候选入库被阻断；
            # OCOS_EXPERIENCE_BOUNDARY_STRICT=false 可回退旧行为
            if _os.environ.get(
                    "OCOS_EXPERIENCE_BOUNDARY_STRICT", "true"
            ).strip().lower() != "false":
                object.__setattr__(
                    candidate, "status", ExperienceStatus.REJECTED)

        # 5. 存储
        self._candidates.append(candidate)
        return candidate

    # ── 封存 ───────────────────────────────────────────────────────────────

    def seal(self, candidate_id: str) -> Optional[ExperienceCandidate]:
        """封存 Candidate: 锁定 sealed_at 时间戳。

        封存后不再允许修改（frozen dataclass 的语义补充）。
        """
        for i, c in enumerate(self._candidates):
            if c.id == candidate_id:
                sealed = ExperienceCandidate(
                    id=c.id,
                    trace_bundle=c.trace_bundle,
                    status=c.status,
                    source=c.source,
                    context=c.context,
                    completeness_score=c.completeness_score,
                    created_at=c.created_at,
                    sealed_at=datetime.now(),
                    significance_score=c.significance_score,
                    boundary_passed=c.boundary_passed,
                    rejection_reason=c.rejection_reason,
                )
                self._candidates[i] = sealed
                return sealed
        return None

    # ── 检索 ───────────────────────────────────────────────────────────────

    def get_complete(self) -> list[ExperienceCandidate]:
        """获取所有 COMPLETE Candidate。"""
        return [c for c in self._candidates
                if c.status == ExperienceStatus.COMPLETE]

    def get_incomplete(self) -> list[ExperienceCandidate]:
        """获取所有 INCOMPLETE Candidate（供后续补充）。"""
        return [c for c in self._candidates
                if c.status == ExperienceStatus.INCOMPLETE]

    def get_by_id(self, candidate_id: str) -> Optional[ExperienceCandidate]:
        """按 ID 检索 Candidate。"""
        for c in self._candidates:
            if c.id == candidate_id:
                return c
        return None

    def count(self) -> int:
        """Candidate 总数。"""
        return len(self._candidates)

    def clear(self) -> None:
        """清空所有 Candidate。"""
        self._candidates.clear()

    # ── Lessons Synthesis ──────────────────────────────────────────────────

    def _synthesize_lessons(
        self,
        candidates: Optional[list[ExperienceCandidate]] = None,
    ) -> list[LessonsLearned]:
        """从 COMPLETE ExperienceCandidate 综合跨经验教训。

        Phase 21: 基于规则的归纳合成器。
        未来可升级为 LLM 驱动的 LessonsSynthesizer。

        Args:
            candidates: 经验候选列表；None 则使用 get_complete()

        Returns:
            LessonsLearned 列表（空列表无异常）
        """
        from ocos.memory.experience.lessons import LessonsSynthesizer

        source = candidates or self.get_complete()
        if len(source) < 2:
            return []

        synthesizer = LessonsSynthesizer()
        return synthesizer.synthesize(source)
