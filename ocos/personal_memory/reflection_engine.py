"""Phase 41: ReflectionEngine — 从经历中发现智慧模式。

不是 Phase 19 的通用反思引擎（那个是对任意 subject 调用 reflect_fn）。
这是 Phase 41 专用的经验→智慧反射引擎。

职责:
    1. 从 ExperienceProfile 读取成功/失败模式
    2. 调用 PatternInterpreter 解释为候选智慧
    3. 调用 WisdomValidator 验证
    4. 产出 WisdomItem 存入 WisdomStore
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import ExperiencePattern
from ocos.self.experience_profile import ExperienceProfile
from ocos.personal_memory.pattern_interpreter import PatternInterpreter
from ocos.personal_memory.wisdom_validator import WisdomValidator, ValidationResult
from ocos.personal_memory.wisdom_store import WisdomStore
from ocos.personal_memory.wisdom_types import WisdomItem, WisdomEvidence, WisdomState


@dataclass
class ReflectionResult:
    """一次反射的结果。"""

    wisdom_candidates: list[WisdomItem] = field(default_factory=list)
    validation_results: list[ValidationResult] = field(default_factory=list)
    new_patterns_discovered: int = 0
    patterns_rejected: int = 0
    wisdom_confirmed: int = 0
    wisdom_rejected: int = 0


@dataclass
class ReflectionEngine:
    """Phase 41 个人记忆反射引擎。

    不是通用的"反思任何东西"引擎 — 这是专门从 ExperienceProfile
    中提取个人智慧的引擎。

    流程:
        ExperienceProfile.patterns → group by category
        → PatternInterpreter.interpret() → Candidate Wisdom
        → WisdomValidator.validate() → Confirmed Wisdom
        → WisdomStore.add_wisdom()
    """

    interpreter: PatternInterpreter = field(default_factory=PatternInterpreter)
    validator: WisdomValidator = field(default_factory=WisdomValidator)
    store: Optional[WisdomStore] = None

    _last_reflection_tick: int = 0

    # ── 核心方法 ──

    def reflect(
        self,
        profile: ExperienceProfile,
        user_id: str,
        current_tick: int,
    ) -> ReflectionResult:
        """对当前 ExperienceProfile 进行反思，产出智慧。

        Args:
            profile: 当前 SelfModel 的 ExperienceProfile。
            user_id: 当前用户 ID。
            current_tick: 当前 tick。

        Returns:
            ReflectionResult: 反思结果。
        """
        result = ReflectionResult()
        result.new_patterns_discovered = len(profile.successful_patterns) + len(profile.failure_patterns)

        # 1. 处理成功模式
        result = self._process_category(
            profile.successful_patterns,
            user_id,
            current_tick,
            result,
        )

        # 2. 处理失败模式
        result = self._process_category(
            profile.failure_patterns,
            user_id,
            current_tick,
            result,
        )

        self._last_reflection_tick = current_tick
        return result

    def _process_category(
        self,
        patterns: list[ExperiencePattern],
        user_id: str,
        current_tick: int,
        result: ReflectionResult,
    ) -> ReflectionResult:
        """处理一类模式（成功或失败）。"""
        if not patterns:
            return result

        # 解释为候选智慧
        interpretations = self.interpreter.interpret(patterns, current_tick)

        for interp in interpretations:
            if interp.rejected:
                result.patterns_rejected += 1
                continue

            candidate = interp.candidate_wisdom
            if candidate is None:
                continue

            # 验证
            validation = self.validator.validate_and_promote(candidate, current_tick)

            result.wisdom_candidates.append(candidate)
            result.validation_results.append(validation)

            if validation.passed:
                result.wisdom_confirmed += 1
                # 存入 store
                if self.store is not None:
                    self.store.add_wisdom(user_id, candidate)
            else:
                result.wisdom_rejected += 1

        return result

    # ── 针对性场景查询 ──

    def query_wisdom_for_domain(
        self,
        user_id: str,
        domain: str,
        conditions: tuple[str, ...] = (),
    ) -> list[WisdomItem]:
        """查询适用于特定领域的已确认智慧。"""
        if self.store is None:
            return []
        return self.store.applicable_to(user_id, domain, conditions)

    @property
    def last_reflection_tick(self) -> int:
        return self._last_reflection_tick


__all__ = ["ReflectionEngine", "ReflectionResult"]
