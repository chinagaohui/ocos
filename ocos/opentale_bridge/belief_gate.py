"""belief_gate.py — I7 BeliefGate：信念进入 Reasoning 前的治理检查（A2 设计落地）。

接口（OPT_A_I7_GO_PRECONDITION_AUDIT §A2）：
    evaluate(belief, context) -> GateVerdict
        PASS       : 信念可进入 reasoning 上下文
        STRIP      : 剥离未证实断言（仅保留 observation 级事实）
        REJECT     : 不可进入（来源不合规 / 影响 Decision 权威语义）
        ESCALATE   : 转人工复核（高影响信念）

硬约束（继承 I7_BELIEF_AUDIT 冻结）：
    Belief → Decision         DENY（不直接构造决策）
    Belief → Mutation         DENY
    Belief → Event/Observation/Artifact 写  DENY（Belief ≠ 事实）

实现原则：Gate 只输出"治理后信念文本"（注入 reasoning 上下文，影响认知"看什么"），
不提供任何写接口、不触 Decision 构造（文本注入由调用方拼接，且调用方本身无写权）。
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class GateVerdict(enum.Enum):
    PASS = "pass"              # 可进入 reasoning 上下文
    STRIP = "strip"            # 剥离未证实断言后进入
    REJECT = "reject"          # 不可进入
    ESCALATE = "escalate"      # 转人工复核


class BeliefSource(enum.Enum):
    """信念来源（对齐 ocos.agent.belief_system.BeliefSource 语义）。"""
    OBSERVATION = "observation"      # 直接观察（可信）
    INFERENCE = "inference"          # 推理得出（可剥离）
    TESTIMONY = "testimony"          # 外部输入（默认拒绝）
    CONSOLIDATION = "consolidation"  # 记忆巩固（可信）
    REFLECTION = "reflection"        # 自我反思（可剥离）


@dataclass(frozen=True)
class GateResult:
    verdict: GateVerdict
    statement: str            # 治理后语句（REJECT 时为空）
    reason: str = ""
    escalate_to: str = ""


class BeliefGate:
    """信念治理门（I7，2026-08-20 实现）。

    只读治理：输入 belief，输出治理后文本；零写接口（硬约束由结构保证）。
    """

    # 高影响触发人工（ESCALATE）：信念影响决策权威语义时转人工
    ESCALATE_KEYWORDS = ("必须", "禁止", "永远", "唯一", "绝不可")

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self.confidence_threshold = confidence_threshold

    # ── 治理判定 ──

    def evaluate(self, belief, context: dict | None = None) -> GateResult:
        """治理检查：来源合规 → 置信度 → 影响 → 输出可入上下文文本。"""
        context = context or {}
        source = getattr(belief, "source", None)
        statement = str(getattr(belief, "statement", "") or "")
        confidence = float(getattr(belief, "confidence", 0.0) or 0.0)

        if not statement:
            return GateResult(GateVerdict.REJECT, "", reason="空信念")
        if isinstance(source, enum.Enum):
            source = source.value

        # Gate 1: 来源合规（TESTIMONY 外部输入默认拒绝——禁 LLM 直注路径）
        if source == BeliefSource.TESTIMONY.value or source == "TESTIMONY":
            return GateResult(GateVerdict.REJECT, "", reason="来源不合规（外部输入）")

        # Gate 2: 置信度阈值
        if confidence < self.confidence_threshold:
            return GateResult(GateVerdict.REJECT, "", reason=f"置信度不足 ({confidence:.2f}<{self.confidence_threshold})")

        # Gate 3: 高影响 → 人工复核（ESCALATE）
        if any(k in statement for k in self.ESCAPE_IF_ANY()):
            return GateResult(GateVerdict.ESCALATE, statement,
                              reason="高影响信念，转人工复核", escalate_to="human")

        # Gate 4: 推理/反思类来源 → STRIP（仅保留 observation 级事实核心）
        if source in (BeliefSource.INFERENCE.value, BeliefSource.REFLECTION.value):
            stripped = self._strip_inference(statement)
            if not stripped:
                return GateResult(GateVerdict.REJECT, "", reason="剥离后无观察级事实")
            return GateResult(GateVerdict.STRIP, stripped, reason="推理断言已剥离")

        # Gate 5: 直接观察/巩固 → PASS
        return GateResult(GateVerdict.PASS, statement, reason="来源可信+置信达标")

    # ── 辅助 ──

    def ESCAPE_IF_ANY(self) -> list[str]:
        return self.ESCALATE_KEYWORDS

    @staticmethod
    def _strip_inference(statement: str) -> str:
        """剥离推理性断言：截断到第一个因果/推断标记。"""
        import re
        cut = re.split(r"(因为|所以|因此|表明|说明|意味着|推断|推测|可能|也许)", statement)
        return (cut[0] or "").strip()[:80]

    def gate_held_beliefs(self, beliefs: list) -> list[GateResult]:
        """批量治理：对 held beliefs 逐条 evaluate，返回非 REJECT 结果（供注入 reasoning 上下文）。"""
        return [r for b in beliefs if (r := self.evaluate(b)).verdict != GateVerdict.REJECT]
