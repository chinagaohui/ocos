"""DecisionLoop — 感知→推理→决策→执行→观察→反射闭环。

将 MasterAgent 的生命周期方法组织为一个完整的决策循环。
"""

from __future__ import annotations

from typing import Any, Optional

from ocos.agent.master_agent import MasterAgent
from ocos.agent.capability_selector import CapabilitySelector
from ocos.agent.executive_controller import ExecutiveController as MetaController  # 22-D 过渡
from ocos.models.process import ProcessType


class DecisionLoop:
    """决策循环。

    完整闭环：感知 → 推理 → 决策 → 执行 → 观察 → 反射

    当提供 engine_bridge 时，执行阶段会调用真实引擎。
    否则回退到 agent.act() 的 stub 行为。
    """

    def __init__(
        self,
        agent: MasterAgent,
        selector: CapabilitySelector,
        controller: MetaController,
        engine_bridge: Any = None,  # EngineBridge, late import to avoid cycle
    ):
        self.agent = agent
        self.selector = selector
        self.controller = controller
        self._engine_bridge = engine_bridge
        self._result_log: list[dict[str, Any]] = []

    def execute_single(self) -> dict[str, Any]:
        """执行一次完整决策循环。"""
        # 1. 感知 (Perceive)
        self.controller.begin_cycle()
        self.controller.record_phase("perceive")
        observation = self.agent.observe()
        intent_type = self.agent.intent.get_intent_type()

        # 2. 推理 (Reason)
        self.controller.record_phase("reason")
        thought = self.agent.think()

        # 3. 选择能力 (Select)
        self.controller.record_phase("select")
        engine_sequence = self.selector.map(intent_type)

        # 4. 决策 (Decide)
        self.controller.record_phase("decide")
        decision = self.agent.decide()

        # 5. 执行 (Execute)
        self.controller.record_phase("execute")
        engine_results: list[dict[str, Any]] = []

        # 使用引擎桥执行（如果有）否则回退到 agent.act()
        if self._engine_bridge is not None and engine_sequence:
            for eng in engine_sequence:
                adapter = self._engine_bridge.get_adapter(eng)
                if adapter is not None:
                    # 根据 intent_type 推断 ProcessType
                    pt = (
                        ProcessType.PLANNING
                        if intent_type in ("plan", "create")
                        else ProcessType.REASONING
                    )
                    eng_result = adapter.execute(pt, inputs={"intent": intent_type})
                    engine_results.append({eng: eng_result})
                else:
                    engine_results.append({eng: {"success": False, "message": "not_registered"}})

        # 执行 agent.act()（即使用了引擎也保留，用于副作用）
        action_result = self.agent.act()

        # 将引擎结果注入 action_result
        if engine_results:
            action_result["engine_results"] = engine_results

        # 死锁检测
        if self.controller.check_deadlock(action_result.get("type", "unknown")):
            self._log_result("deadlock_detected", intent_type, engine_sequence)
            self.controller.end_cycle("deadlock")
            return {"status": "deadlock", "action": action_result}

        # 6. 观察结果 (Observe Result)
        self.controller.record_phase("observe_result")
        self.agent.reflect()

        # 7. 反射 (Reflect)
        self.controller.record_phase("reflect")
        self.agent.learn()

        self.controller.end_cycle("completed")
        result = {
            "status": "completed",
            "cycle": self.controller.cycle_count,
            "intent": intent_type,
            "engine_sequence": engine_sequence,
            "action_result": action_result,
        }
        self._log_result(result["status"], intent_type, engine_sequence)
        return result

    def execute_n(self, n: int = 5) -> list[dict[str, Any]]:
        """连续执行 N 次决策循环。

        当 MetaController 检测到阻塞时自动停止。
        """
        results = []
        for _ in range(n):
            if self.controller.is_blocked():
                break
            result = self.execute_single()
            results.append(result)
            if result["status"] in ("error", "deadlock", "shutdown"):
                break
        return results

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._result_log[-limit:]

    def _log_result(self, status: str, intent: str, sequence: list[str]) -> None:
        self._result_log.append({
            "cycle": self.controller.cycle_count,
            "status": status,
            "intent": intent,
            "sequence": sequence,
        })

    def reset(self) -> None:
        self._result_log.clear()
        self.controller.reset()
