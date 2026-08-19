"""Phase 22-D — ExecutiveController: 意图理解 → 策略制定 → 能力选择。

MetaController 重命名为 ExecutiveController，新增三阶段职责链:
  Stage 1: 意图理解 (Intent Understanding) — 解析 agent.intent
  Stage 2: 策略制定 (Strategy Formulation) — 制定执行策略
  Stage 3: 能力选择 (Capability Selection) — 选择所需引擎

保持原有 MetaController 的监控/熔断功能不变（零行为变更）。
旧类 MetaController 保留为别名，供过渡期使用。
"""

from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 数据类 ───────────────────────────────────────────────────────────────────


@dataclass
class CycleRecord:
    """一次认知循环的记录。"""
    cycle_id: int
    start_time: float
    end_time: Optional[float] = None
    phases: list[str] = field(default_factory=list)
    result: Optional[str] = None


@dataclass
class IntentAnalysis:
    """意图分析结果。"""
    intent_type: str = ""
    confidence: float = 0.0
    urgency: float = 0.0
    required_capabilities: list[str] = field(default_factory=list)


@dataclass
class Strategy:
    """执行策略。"""
    name: str = ""
    steps: list[str] = field(default_factory=list)
    estimated_cycles: int = 1
    fallback_strategy: Optional[str] = None


@dataclass
class CapabilityPlan:
    """能力选择计划。"""
    engines: list[str] = field(default_factory=list)
    dispatch_order: list[str] = field(default_factory=list)
    per_step: dict[str, list[str]] = field(default_factory=dict)


# ── ExecutiveController ──────────────────────────────────────────────────────


class ExecutiveController:
    """执行控制器 — 三阶段职责链 + 监控熔断。

    Stage 1: Intent Understanding — 解析意图
    Stage 2: Strategy Formulation — 制定策略
    Stage 3: Capability Selection — 能力选择

    监控: 死循环检测、震荡检测、超时检测。
    """

    def __init__(
        self,
        max_cycles: int = 50,
        oscillation_threshold: int = 5,
        timeout_seconds: float = 30.0,
    ):
        self._max_cycles = max_cycles
        self._oscillation_threshold = oscillation_threshold
        self._timeout_seconds = timeout_seconds
        self._cycle_count: int = 0
        self._cycles: deque[CycleRecord] = deque(maxlen=100)
        self._current_cycle: Optional[CycleRecord] = None
        self._deadlock_detected: bool = False
        self._last_action: Optional[str] = None
        self._same_action_count: int = 0
        self._lock = threading.RLock()

        # Phase 22-D: 三阶段缓存
        self._last_intent: Optional[IntentAnalysis] = None
        self._last_strategy: Optional[Strategy] = None
        self._last_capability_plan: Optional[CapabilityPlan] = None

    # ── Stage 1: Intent Understanding ────────────────────────────────────

    def analyze_intent(self, intent: Any) -> IntentAnalysis:
        """意图理解 — 解析 agent 当前意图。

        Args:
            intent: Intent 对象（需有 get_intent_type() / get_confidence()）

        Returns:
            IntentAnalysis
        """
        try:
            intent_type = (
                intent.get_intent_type()
                if hasattr(intent, "get_intent_type")
                else str(intent)
            )
            confidence = (
                intent.get_confidence()
                if hasattr(intent, "get_confidence")
                else 0.5
            )
        except Exception:
            intent_type = "unknown"
            confidence = 0.3

        urgency = 1.0 if intent_type in ("execute", "command") else 0.5

        # 推断所需能力
        required = self._infer_capabilities(intent_type)

        analysis = IntentAnalysis(
            intent_type=intent_type,
            confidence=confidence,
            urgency=urgency,
            required_capabilities=required,
        )
        self._last_intent = analysis
        return analysis

    @staticmethod
    def _infer_capabilities(intent_type: str) -> list[str]:
        """从 intent_type 推断所需能力。"""
        _map = {
            "write": ["writing_engine"],
            "generate": ["writing_engine"],
            "plan": ["planning_engine"],
            "think": ["reasoning_engine"],
            "reason": ["reasoning_engine"],
            "execute": ["execution_engine"],
            "observe": ["observation_engine"],
            "learn": ["learning_engine"],
        }
        return _map.get(intent_type.lower(), [])

    # ── Stage 2: Strategy Formulation ────────────────────────────────────

    def formulate_strategy(self, intent: IntentAnalysis) -> Strategy:
        """策略制定 — 根据意图分析制定执行策略。

        Args:
            intent: 意图分析结果

        Returns:
            Strategy
        """
        if intent.intent_type in ("execute", "command"):
            strategy = Strategy(
                name="direct_execution",
                steps=["validate", "dispatch", "observe_result"],
                estimated_cycles=1,
            )
        elif intent.required_capabilities:
            strategy = Strategy(
                name="capability_chain",
                steps=["activate"] + intent.required_capabilities + ["collect"],
                estimated_cycles=len(intent.required_capabilities) + 1,
                fallback_strategy="direct_act",
            )
        elif intent.intent_type == "unknown":
            strategy = Strategy(
                name="observation_only",
                steps=["observe", "classify"],
                estimated_cycles=1,
                fallback_strategy="idle",
            )
        else:
            strategy = Strategy(
                name="standard_loop",
                steps=["observe", "think", "decide", "act", "reflect", "learn"],
                estimated_cycles=1,
            )

        self._last_strategy = strategy
        return strategy

    # ── Stage 3: Capability Selection ────────────────────────────────────

    def select_capabilities(
        self,
        intent: IntentAnalysis,
        strategy: Strategy,
        available_engines: Optional[list[str]] = None,
    ) -> CapabilityPlan:
        """能力选择 — 选择需要调度的引擎。

        Args:
            intent: 意图分析
            strategy: 策略
            available_engines: 可用引擎列表

        Returns:
            CapabilityPlan
        """
        engines = intent.required_capabilities[:]
        if available_engines:
            engines = [e for e in engines if e in available_engines]

        plan = CapabilityPlan(
            engines=engines,
            dispatch_order=engines,
            per_step={
                step: engines for step in strategy.steps
            } if engines else {},
        )
        self._last_capability_plan = plan
        return plan

    def execute_chain(self, agent: Any) -> dict[str, Any]:
        """执行完整三阶段职责链。

        Args:
            agent: MasterAgent（需有 intent 属性）

        Returns:
            {intent, strategy, capability_plan}
        """
        intent = self.analyze_intent(agent.intent if hasattr(agent, "intent") else None)
        strategy = self.formulate_strategy(intent)
        available = (
            agent.engine_bridge.get_available_engines()
            if hasattr(agent, "engine_bridge") and hasattr(agent.engine_bridge, "get_available_engines")
            else None
        )
        capability_plan = self.select_capabilities(intent, strategy, available)

        return {
            "intent": intent.intent_type,
            "confidence": intent.confidence,
            "urgency": intent.urgency,
            "strategy": strategy.name,
            "steps": strategy.steps,
            "engines": capability_plan.engines,
        }

    # ── 监控/熔断 (MetaController 原有功能, 零行为变更) ──────────────────

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def begin_cycle(self) -> int:
        with self._lock:
            self._cycle_count += 1
            self._current_cycle = CycleRecord(
                cycle_id=self._cycle_count,
                start_time=time.time(),
            )
            return self._cycle_count

    def record_phase(self, phase: str) -> None:
        with self._lock:
            if self._current_cycle:
                self._current_cycle.phases.append(phase)

    def end_cycle(self, result: str = "completed") -> None:
        with self._lock:
            if self._current_cycle:
                self._current_cycle.end_time = time.time()
                self._current_cycle.result = result
                self._cycles.append(self._current_cycle)
                self._current_cycle = None

    def check_deadlock(self, current_action: str) -> bool:
        with self._lock:
            if current_action == self._last_action:
                self._same_action_count += 1
                if self._same_action_count >= 5:
                    self._deadlock_detected = True
                    return True
            else:
                self._same_action_count = 1
                self._last_action = current_action
            return False

    def check_oscillation(self, recent_states: list[str]) -> bool:
        if len(recent_states) < 4:
            return False
        with self._lock:
            for i in range(len(recent_states) - 3):
                if (recent_states[i] == recent_states[i + 2]
                        and recent_states[i + 1] == recent_states[i + 3]
                        and recent_states[i] != recent_states[i + 1]):
                    return True
            return False

    def check_timeout(self) -> bool:
        with self._lock:
            if self._current_cycle:
                elapsed = time.time() - self._current_cycle.start_time
                return elapsed > self._timeout_seconds
            return False

    def is_blocked(self) -> bool:
        return (self._deadlock_detected
                or self.check_timeout()
                or self._cycle_count >= self._max_cycles)

    def reset(self) -> None:
        with self._lock:
            self._cycle_count = 0
            self._cycles.clear()
            self._current_cycle = None
            self._deadlock_detected = False
            self._last_action = None
            self._same_action_count = 0

    def get_stats(self) -> dict:
        with self._lock:
            avg_duration = 0.0
            if self._cycles:
                durations = []
                for c in self._cycles:
                    if c.end_time:
                        durations.append(c.end_time - c.start_time)
                if durations:
                    avg_duration = sum(durations) / len(durations)

            return {
                "cycle_count": self._cycle_count,
                "deadlock_detected": self._deadlock_detected,
                "same_action_count": self._same_action_count,
                "avg_cycle_duration": round(avg_duration, 3),
                "is_blocked": self.is_blocked(),
            }


# ── 向后兼容别名 ─────────────────────────────────────────────────────────────

MetaController = ExecutiveController  # 旧名称别名，零行为变更
