# ARCHIVED（收敛裁决 P2，2026-09-08）— LifeCycleOrchestrator 已 MERGE 入 daemon，非生产代码。
# 依据: docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md R3。

"""LifeCycleOrchestrator — 生命周期编排器。

自动运行 Master Agent 的完整生命周期：
  BOOT → WAKE → OBSERVE → THINK → DECIDE → ACT → REFLECT → LEARN
  ↓                                              ↑
  └── SLEEP → DREAM → (WAKE) → OBSERVE ──────────┘

编排器负责：
- 循环顺序保证（REFLECT 必须在 ACT 之后，等等）
- 注意力疲劳检测 → 自动进入 SLEEP
- 心跳 Tick（同步注意力时间）
"""

from __future__ import annotations

import logging
from enum import Enum, auto
from typing import Any, Optional

from ocos.agent.state import AgentState, AgentStatus
from ocos.agent.master_agent import MasterAgent

logger = logging.getLogger(__name__)


class TickResult(Enum):
    """单次 Tick 的结果。"""
    CYCLE_COMPLETE = auto()      # 完成一个完整认知循环
    SLEEP_NEEDED = auto()        # 疲劳度过高，建议进入 SLEEP
    SLEEP_CYCLE_DONE = auto()    # SLEEP→DREAM→WAKE 完成
    ERROR = auto()               # 循环中出现错误
    SHUTDOWN = auto()            # Agent 已关闭


class LifeCycleOrchestrator:
    """生命周期编排器。

    以 tick() 为单位驱动 Agent 的认知循环。
    """

    def __init__(self, agent: MasterAgent, tick_seconds: float = 1.0):
        self.agent = agent
        self.tick_seconds = tick_seconds
        self._cycle_count: int = 0
        self._phase: str = "idle"

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def boot(self) -> None:
        """启动 Agent（BOOT 阶段）。"""
        self.agent.boot()
        self._phase = "ready"

    def shutdown(self) -> None:
        """安全关闭。"""
        self.agent.shutdown()
        self._phase = "shutdown"

    def tick(self) -> TickResult:
        """执行一个 Tick。

        根据当前 Agent 状态执行对应的生命周期阶段。
        """
        status = self.agent.state.status

        try:
            if status == AgentStatus.IDLE:
                return self._tick_idle()
            elif status == AgentStatus.THINKING:
                self.agent.think()
                return TickResult.CYCLE_COMPLETE
            elif status == AgentStatus.SLEEP:
                return self._tick_sleep()
            elif status == AgentStatus.DREAM:
                self.agent.wake()
                return TickResult.SLEEP_CYCLE_DONE
            elif status == AgentStatus.SHUTDOWN:
                return TickResult.SHUTDOWN
            else:
                # 中间状态（DECIDING/ACTING/REFLECTING/LEARNING）通常由
                # MasterAgent 内部方法自动推进，编排器不干预
                return TickResult.CYCLE_COMPLETE

        except Exception:
            return TickResult.ERROR

    # ── S2.13 (白皮书 P1-10): 注意力接口兼容层 ────────────────────────
    # 生产注入的 CognitiveAttentionController 无 needs_sleep/reset
    # （ fatigue 属性 + reset_fatigue()），旧 Attention（agent/attention.py）
    # 才有 needs_sleep/tick/reset。此前 _tick_idle/_tick_sleep 无守卫直调
    # → AttributeError 被 tick() 吞为 TickResult.ERROR（"疲劳自动睡眠"
    # 生产路径从未运转）。现按能力探测适配，并在无能力时 warning 留痕。

    def _attention_fatigued(self) -> bool:
        """注意力疲劳判定：优先 needs_sleep()，回退 fatigue 属性阈值。"""
        attention = self.agent.attention
        if hasattr(attention, "needs_sleep"):
            try:
                return bool(attention.needs_sleep())
            except Exception as e:
                logger.warning("attention.needs_sleep failed: %s", e)
                return False
        fatigue = getattr(attention, "fatigue", None)
        if callable(fatigue):
            fatigue = fatigue()
        if isinstance(fatigue, (int, float)):
            return fatigue > 0.9
        logger.warning(
            "attention 对象无疲劳判定能力（needs_sleep/fatigue 均缺失）"
            " — 跳过疲劳检查")
        return False

    def _attention_reset(self) -> None:
        """注意力重置：优先 reset()，回退 reset_fatigue()。"""
        attention = self.agent.attention
        if hasattr(attention, "reset"):
            try:
                attention.reset()
                return
            except Exception as e:
                logger.warning("attention.reset failed: %s", e)
                return
        if hasattr(attention, "reset_fatigue"):
            try:
                attention.reset_fatigue()
                return
            except Exception as e:
                logger.warning("attention.reset_fatigue failed: %s", e)

    def _attention_tick(self) -> None:
        """注意力 tick（带守卫；无 tick 能力时跳过）。"""
        attention = self.agent.attention
        if hasattr(attention, "tick"):
            try:
                attention.tick(self.tick_seconds)
            except Exception as e:
                logger.warning("attention.tick failed: %s", e)

    def _tick_idle(self) -> TickResult:
        """IDLE 状态下执行完整认知循环。"""
        # 检查注意力疲劳（S2.13: 兼容层）
        if self._attention_fatigued():
            self.agent.sleep()
            return TickResult.SLEEP_NEEDED

        # 更新注意力 Tick（S2.13: 兼容层）
        self._attention_tick()

        # 执行认知循环
        self.agent.observe()
        self.agent.think()
        self.agent.decide()
        self.agent.act()
        self.agent.reflect()
        self.agent.learn()

        # P2-D: 空闲期主动输出（防御式降级，绝不抛）
        try:
            self.agent.maybe_proactive_output()
        except Exception:
            pass

        self._cycle_count += 1
        self._phase = "cognition"
        return TickResult.CYCLE_COMPLETE

    def _tick_sleep(self) -> TickResult:
        """SLEEP 状态下执行睡眠周期。"""
        # 模拟睡眠时间（重置注意力 — S2.13: 兼容层）
        self._attention_reset()
        self.agent.dream()
        return TickResult.SLEEP_CYCLE_DONE

    def run_cycles(self, n: int = 1) -> list[TickResult]:
        """连续运行 N 个认知循环。"""
        results = []
        for _ in range(n):
            result = self.tick()
            results.append(result)
            if result in (TickResult.SLEEP_NEEDED, TickResult.ERROR, TickResult.SHUTDOWN):
                break
        return results

    def get_report(self) -> dict[str, Any]:
        """获取编排器状态报告。"""
        agent_report = self.agent.get_status_report()
        agent_report["cycle_count"] = self._cycle_count
        agent_report["phase"] = self._phase
        agent_report["attention_fatigue"] = self.agent.attention.fatigue
        agent_report["needs_sleep"] = self.agent.attention.needs_sleep()
        return agent_report
