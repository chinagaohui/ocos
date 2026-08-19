"""Phase 45: ResultInterpreter — 结果解释器。

核心边界 CNS45-04: Execution ≠ Learning

执行结果不能直接成为知识。
必须: Result → Interpretation → Validation → Memory

这个模块确保:
    - Agent 输出被 OCOS 理解（不是盲目信任）
    - 结构化理解后评估置信度
    - 验证通过后才能写入 Experience/Memory
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    ExecutionStatus, RawResult, InterpretedResult,
)


@dataclass
class ResultInterpreter:
    """结果解释器。

    将 External Agent 的原始输出转化为 OCOS 可理解的结构化结果。

    约束:
        - 不直接信任 Agent 输出
        - 必须评估置信度
        - 必须标记验证状态
        - 未验证的结果不能进入 Memory
    """

    # 可疑输出模式（需降低置信度）
    _SUSPICIOUS_PATTERNS: list[str] = field(default_factory=lambda: [
        "I am", "我决定", "建议修改", "should modify",
        "delete all", "remove everything",
        "bypass", "绕过",
    ])

    def interpret(self, raw: RawResult) -> InterpretedResult:
        """将原始结果解释为结构化结果。"""

        if raw.status != ExecutionStatus.SUCCESS:
            return InterpretedResult(
                request_id=raw.request_id,
                capability_id=raw.capability_id,
                summary=raw.error_message or "Execution failed",
                confidence=0.0,
                is_valid=False,
                validation_note=f"Execution status: {raw.status.value}",
                tick_id=raw.tick_id,
            )

        # 分析原始输出
        summary = self._summarize(raw.raw_output)
        confidence = self._assess_confidence(raw.raw_output)
        is_valid = confidence >= 0.5

        return InterpretedResult(
            request_id=raw.request_id,
            capability_id=raw.capability_id,
            summary=summary,
            confidence=confidence,
            is_valid=is_valid,
            validation_note="Passed validation" if is_valid else "Low confidence - requires review",
            tick_id=raw.tick_id,
        )

    def _summarize(self, raw_output: str) -> str:
        """生成人类可读摘要。"""
        if not raw_output:
            return "(empty output)"
        return raw_output[:500].strip()

    def _assess_confidence(self, raw_output: str) -> float:
        """评估对 Agent 输出的置信度。"""
        base = 0.7  # 基础信任

        # 检查可疑模式
        for pattern in self._SUSPICIOUS_PATTERNS:
            if pattern.lower() in raw_output.lower():
                base -= 0.3

        # 空输出 = 低置信度
        if not raw_output.strip():
            return 0.0

        # 太短的输出 = 低置信度
        if len(raw_output.strip()) < 10:
            base -= 0.2

        return max(0.0, min(1.0, round(base, 2)))

    def validate(self, interpreted: InterpretedResult) -> bool:
        """验证解释后的结果是否可以写入 Memory。"""
        return interpreted.is_valid and interpreted.confidence >= 0.5


__all__ = ["ResultInterpreter"]
