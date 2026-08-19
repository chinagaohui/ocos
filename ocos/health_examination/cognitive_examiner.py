"""Phase 58.0: CognitiveExaminer — 认知健康检查。

检测四种认知疾病:
    1. Memory Disorder (记忆膨胀 / 遗忘异常)
    2. Decision Disorder (决策漂移)
    3. Attention Disorder (注意错位)
    4. World Model Disorder (矛盾/孤立/错误关系)

数据来源: SimulationEngine stats, TraceStep logs, Memory records
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field

from ocos.health_examination.health_model import (
    HealthCategory, CategoryScore, DisorderFinding, DisorderType,
)


@dataclass
class MemorySnapshot:
    """记忆快照（用于检测膨胀/遗忘）。"""
    event_count: int = 0
    wisdom_count: int = 0
    duplicate_rate: float = 0.0      # 重复率
    retrieval_latency_ms: float = 0.0
    important_events: list[str] = field(default_factory=list)


@dataclass
class DecisionSnapshot:
    """决策快照（用于检测漂移）。"""
    problem: str = ""
    chosen_option: str = ""
    risk_level: str = ""
    timestamp: float = 0.0


@dataclass
class WorldSnapshot:
    """世界模型快照（用于检测矛盾）。"""
    entity_count: int = 0
    relation_count: int = 0
    orphan_entities: int = 0          # 孤立实体
    contradiction_count: int = 0      # 矛盾关系


@dataclass
class CognitiveExaminer:
    """认知疾病检测器。"""

    # 阈值
    max_event_growth_rate: float = 2.0       # 单次检查最大增长率
    max_duplicate_rate: float = 0.3           # 最大重复率
    min_important_event_retention: int = 5    # 重要事件最低保留数
    max_decision_divergence: float = 0.3      # 最大决策分歧
    max_orphan_rate: float = 0.2              # 最大孤立实体率

    # 历史快照（用于趋势检测）
    memory_history: list[MemorySnapshot] = field(default_factory=list)
    decision_history: list[DecisionSnapshot] = field(default_factory=list)

    def examine_memory(self, current: MemorySnapshot) -> DisorderFinding:
        """检测记忆疾病。"""
        findings: list[str] = []
        severity = 0.0

        # 1. 记忆膨胀: 与上次快照对比增长率
        if self.memory_history:
            last = self.memory_history[-1]
            if last.event_count > 0:
                growth = (current.event_count - last.event_count) / last.event_count
                if growth > self.max_event_growth_rate:
                    findings.append(f"memory inflation: {growth:.1%} growth")
                    severity = max(severity, min(growth / self.max_event_growth_rate - 1.0, 1.0))

        # 2. 重复率过高
        if current.duplicate_rate > self.max_duplicate_rate:
            findings.append(f"high duplicate rate: {current.duplicate_rate:.1%}")
            severity = max(severity, current.duplicate_rate / self.max_duplicate_rate - 1.0)

        # 3. 遗忘: 重要事件丢失
        if current.important_events:
            if len(current.important_events) < self.min_important_event_retention:
                findings.append(f"important event amnesia: only {len(current.important_events)} retained")

        self.memory_history.append(current)
        detected = len(findings) > 0

        return DisorderFinding(
            disorder_type=DisorderType.MEMORY_INFLATION if "inflation" in str(findings)
                          else DisorderType.MEMORY_AMNESIA,
            detected=detected,
            severity=min(severity, 1.0),
            evidence="; ".join(findings) if findings else "healthy memory",
            recommendation="prune stale events" if "inflation" in str(findings)
                          else "review retention policy" if "amnesia" in str(findings)
                          else "",
        )

    def examine_decision(self, current: DecisionSnapshot) -> DisorderFinding:
        """检测决策漂移。

        同类问题、同样上下文下，决策发生无理由改变 → 漂移。
        """
        if not self.decision_history:
            self.decision_history.append(current)
            return DisorderFinding(
                disorder_type=DisorderType.DECISION_DRIFT,
                detected=False,
                severity=0.0,
                evidence="baseline established",
            )

        last = self.decision_history[-1]
        drifted = False
        evidence = ""

        # 同一类问题但不同决策 → 漂移
        if (current.problem and last.problem
                and current.problem[:20] == last.problem[:20]
                and current.chosen_option
                and last.chosen_option
                and current.chosen_option != last.chosen_option):
            # 如果不是因为风险变化导致，就是漂移
            if current.risk_level == last.risk_level:
                drifted = True
                evidence = (f"decision drift: '{last.problem[:30]}...' "
                           f"switched from '{last.chosen_option}' to '{current.chosen_option}'")

        self.decision_history.append(current)

        return DisorderFinding(
            disorder_type=DisorderType.DECISION_DRIFT,
            detected=drifted,
            severity=0.5 if drifted else 0.0,
            evidence=evidence or "decision stable",
            recommendation="review decision consistency" if drifted else "",
        )

    def examine_attention(self, focus_goals: list[str],
                          current_context: str) -> DisorderFinding:
        """检测注意错位。

        目标与当前上下文不符 → 注意错位。
        """
        # 简单检测: 焦点目标是否与当前上下文相关
        # 如果所有焦点目标都不包含当前上下文的任何关键词 → 错位
        context_words = set(current_context.lower().split())

        alignment = 0.0
        for goal in focus_goals:
            goal_words = set(goal.lower().split())
            overlap = context_words & goal_words
            if overlap:
                alignment += len(overlap) / max(len(goal_words), 1)

        misaligned = alignment < 0.1 if focus_goals else False

        return DisorderFinding(
            disorder_type=DisorderType.ATTENTION_MISFOCUS,
            detected=misaligned,
            severity=0.7 if misaligned else 0.0,
            evidence=(f"attention misaligned: context='{current_context[:50]}' "
                     f"vs goals={focus_goals[:3]}" if misaligned
                     else "attention aligned"),
            recommendation="realign goals with context" if misaligned else "",
        )

    def examine_world_model(self, snapshot: WorldSnapshot) -> DisorderFinding:
        """检测世界模型疾病。"""
        findings: list[str] = []
        severity = 0.0

        # 1. 孤立实体率
        if snapshot.entity_count > 0:
            orphan_rate = snapshot.orphan_entities / snapshot.entity_count
            if orphan_rate > self.max_orphan_rate:
                findings.append(f"orphan entities: {orphan_rate:.1%}")
                severity = max(severity, orphan_rate - self.max_orphan_rate)

        # 2. 矛盾关系
        if snapshot.contradiction_count > 0:
            findings.append(f"contradictions: {snapshot.contradiction_count}")
            severity = max(severity, min(snapshot.contradiction_count / 10.0, 1.0))

        detected = len(findings) > 0

        return DisorderFinding(
            disorder_type=DisorderType.WORLD_MODEL_CONTRADICTION,
            detected=detected,
            severity=severity,
            evidence="; ".join(findings) if findings else "world model healthy",
            recommendation="resolve contradictions" if detected else "",
        )

    def full_examination(self,
                         memory: MemorySnapshot | None = None,
                         decision: DecisionSnapshot | None = None,
                         attention_goals: list[str] | None = None,
                         attention_context: str = "",
                         world: WorldSnapshot | None = None,
                         ) -> CategoryScore:
        """执行完整认知健康检查。"""
        findings: dict[str, DisorderFinding] = {}

        if memory:
            findings["memory"] = self.examine_memory(memory)
        if decision:
            findings["decision"] = self.examine_decision(decision)
        if attention_goals:
            findings["attention"] = self.examine_attention(
                attention_goals, attention_context)
        if world:
            findings["world"] = self.examine_world_model(world)

        if not findings:
            return CategoryScore(
                category=HealthCategory.COGNITIVE,
                raw_score=20.0, max_score=20.0, normalized=1.0,
                details={"status": "no data — assumed healthy"},
            )

        # 评分: 无疾病=满分, 每个疾病扣分
        disorders = sum(1 for f in findings.values() if f.detected)
        max_disorders = len(findings)
        score = max(0, 20.0 * (1 - disorders / max_disorders)) if max_disorders > 0 else 20.0

        warnings = []
        for name, f in findings.items():
            if f.detected:
                warnings.append(f"{name}: {f.evidence}")

        return CategoryScore(
            category=HealthCategory.COGNITIVE,
            raw_score=score,
            max_score=20.0,
            normalized=score / 20.0,
            details={
                "findings": {name: {
                    "detected": f.detected,
                    "severity": f.severity,
                    "evidence": f.evidence,
                } for name, f in findings.items()},
            },
            warnings=warnings,
        )


__all__ = ["CognitiveExaminer", "MemorySnapshot", "DecisionSnapshot", "WorldSnapshot"]
