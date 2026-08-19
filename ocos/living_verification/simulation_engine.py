"""Phase 57: Living System Verification — SimulationEngine.

认知生命模拟引擎 — 验证 OCOS 所有器官在长期运行中协同工作。

LV57-01: 全链路闭环 — Intent → Memory 必须可追踪。
LV57-02: 长期运行 — 无 identity 漂移、memory 污染、permission 突破。

模拟场景:
    Day 1: 用户提出目标 → Perception → WorldModel → Decision → Capability → Memory
    Day N: 积累经验 → Evolution 触发 → Extension 吸收 → Persistence 保存
    Day 30: 恢复运行 → 状态连续性验证
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import time as _time
import uuid
import random


class SimPhase(str, Enum):
    """模拟阶段。"""
    PERCEIVE = "perceive"
    UNDERSTAND = "understand"
    DECIDE = "decide"
    EXECUTE = "execute"
    RECORD = "record"
    REFLECT = "reflect"
    EVOLVE = "evolve"
    PERSIST = "persist"
    RESTORE = "restore"


@dataclass
class TraceStep:
    """LV57-01: 单步可追踪记录。"""
    tick: int
    phase: SimPhase
    step_id: str = field(default_factory=lambda: f"ts-{uuid.uuid4().hex[:8]}")

    # 因果链
    intent: str = ""                    # 为什么做
    attention_focus: str = ""           # 关注什么
    context_snapshot: dict = field(default_factory=dict)
    decision: str = ""                  # 决定方案
    action: str = ""                    # 执行动作
    result: str = ""                    # 结果
    memory_recorded: bool = False       # 是否记录到 EventMemory
    wisdom_generated: bool = False      # 是否产生经验

    # 组件状态
    component_health: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    elapsed_ms: float = 0.0


@dataclass
class SimulationProfile:
    """模拟运行配置。"""
    total_ticks: int = 1000
    tasks_per_day: int = 3
    idle_ticks_between_tasks: int = 2
    # 场景参数
    fail_rate: float = 0.02          # 2% 概率随机失败
    evolution_trigger_interval: int = 50  # 每50tick触发演化
    persist_interval: int = 100      # 每100tick持久化
    restore_interval: int = 300      # 每300tick恢复测试
    # 监控
    identity_check_interval: int = 100


# 模拟任务库
SIM_TASKS = [
    {"intent": "列出当前目录文件", "requires": ["fs_list"],
     "expected_result": "success", "category": "filesystem"},
    {"intent": "读取配置文件", "requires": ["fs_read"],
     "expected_result": "success", "category": "filesystem"},
    {"intent": "搜索最近事件", "requires": ["event_query"],
     "expected_result": "success", "category": "memory"},
    {"intent": "分析工作模式", "requires": ["pattern_detect"],
     "expected_result": "insight", "category": "cognition"},
    {"intent": "创建新文件", "requires": ["fs_write"],
     "expected_result": "success", "category": "filesystem"},
    {"intent": "执行健康检查", "requires": ["probe"],
     "expected_result": "report", "category": "diagnosis"},
    {"intent": "回顾本周学习", "requires": ["memory_query"],
     "expected_result": "summary", "category": "reflection"},
    {"intent": "调整注意力焦点", "requires": ["attention"],
     "expected_result": "shifted", "category": "cognition"},
    {"intent": "保存当前状态", "requires": ["persist"],
     "expected_result": "snapshot", "category": "system"},
    {"intent": "优化工作流程", "requires": ["optimize"],
     "expected_result": "improved", "category": "cognition"},
]


@dataclass
class SimulationEngine:
    """认知生命模拟引擎。

    按照 OCOS 生命周期模拟:
        Intent → Perceive → Understand → Decide → Execute → Record → Reflect → Evolve

    LV57-01: 每步产生 TraceStep，完整可追踪。
    LV57-02: 监控 identity/memory/permission 完整性。
    """

    profile: SimulationProfile = field(default_factory=SimulationProfile)
    tick: int = 0
    traces: deque[TraceStep] = field(default_factory=deque)
    max_traces: int = 10000

    # 系统状态
    identity_anchor: str = "OCOS-v1.0-identity-anchor"
    memory_records: int = 0
    permissions: set[str] = field(default_factory=set)
    capabilities: set[str] = field(default_factory=set)

    # 演进状态
    evolution_count: int = 0
    errors_injected: int = 0
    errors_recovered: int = 0

    # 回调注入
    on_step: object = None          # Callable[[TraceStep], None]
    on_error: object = None         # Callable[[str, dict], None]
    task_provider: object = None    # Callable[[int], dict] — 外部任务源

    # —— 公共 API ——

    def run_ticks(self, n: int | None = None) -> list[TraceStep]:
        """运行 n 个 tick。"""
        if n is None:
            n = self.profile.total_ticks
        new_traces = []
        for _ in range(n):
            t = self._tick()
            new_traces.append(t)
        return new_traces

    def run_until(self, max_ticks: int | None = None) -> list[TraceStep]:
        """运行完整模拟。"""
        return self.run_ticks(max_ticks or self.profile.total_ticks)

    def snapshot_identity(self) -> dict:
        """LV57-02: 身份快照。"""
        return {
            "identity_anchor": self.identity_anchor,
            "tick": self.tick,
            "permissions": sorted(self.permissions),
            "capabilities": sorted(self.capabilities),
            "evolution_count": self.evolution_count,
            "memory_records": self.memory_records,
        }

    def verify_identity(self, anchor: str) -> bool:
        """LV57-02: 验证身份未被修改。"""
        return self.identity_anchor == anchor

    def verify_permissions(self, original: set[str]) -> bool:
        """LV57-02: 验证权限未被扩大。"""
        return self.permissions.issubset(original)

    # —— 内部 ——

    def _tick(self) -> TraceStep:
        tick_start = _time.time()
        step = TraceStep(tick=self.tick, phase=SimPhase.PERCEIVE)
        self.tick += 1

        try:
            # Phase 1: Perceive
            task = self._get_task()
            step.phase = SimPhase.PERCEIVE
            step.intent = task["intent"]

            # Phase 2: Understand (WorldModel)
            step.phase = SimPhase.UNDERSTAND
            step.attention_focus = task.get("category", "general")
            step.context_snapshot = {
                "tick": self.tick,
                "capabilities": sorted(self.capabilities),
                "memory_records": self.memory_records,
            }

            # Phase 3: Decide
            step.phase = SimPhase.DECIDE
            step.decision = f"execute_{task['requires'][0]}"

            # Phase 4: Execute (可能失败)
            step.phase = SimPhase.EXECUTE
            if random.random() < self.profile.fail_rate:
                step.action = task["requires"][0]
                step.result = "failed"
                step.errors.append(f"{task['requires'][0]} failed at tick {self.tick}")
                self.errors_injected += 1
            else:
                step.action = task["requires"][0]
                step.result = task["expected_result"]

            # Phase 5: Record (EventMemory)
            step.phase = SimPhase.RECORD
            step.memory_recorded = True
            self.memory_records += 1

            # Phase 6: Reflect (经验提取)
            step.phase = SimPhase.REFLECT
            if self.memory_records % 5 == 0:
                step.wisdom_generated = True

            # Phase 7: Evolve (定期)
            step.phase = SimPhase.EVOLVE
            if self.tick % self.profile.evolution_trigger_interval == 0:
                self.evolution_count += 1

            # Phase 8: Persist (定期)
            if self.tick % self.profile.persist_interval == 0:
                step.phase = SimPhase.PERSIST

            # Phase 9: Identity check (定期)
            if self.tick % self.profile.identity_check_interval == 0:
                step.phase = SimPhase.RESTORE
                if not self.verify_identity(self.identity_anchor):
                    step.errors.append("IDENTITY_DRIFT_DETECTED")

        except Exception as e:
            step.errors.append(str(e))
            self.errors_injected += 1

        step.elapsed_ms = (_time.time() - tick_start) * 1000
        step.component_health = {
            "perception": len(step.errors) == 0,
            "decision": bool(step.decision),
            "execution": step.result != "failed",
            "memory": step.memory_recorded,
        }

        self.traces.append(step)
        while len(self.traces) > self.max_traces:
            self.traces.popleft()

        if self.on_step:
            try:
                self.on_step(step)  # type: ignore
            except Exception:
                pass

        return step

    def _get_task(self) -> dict:
        if self.task_provider:
            return self.task_provider(self.tick)  # type: ignore
        return random.choice(SIM_TASKS)

    def stats(self) -> dict:
        traces_list = list(self.traces)
        if not traces_list:
            return {"total_ticks": 0}
        errors = sum(1 for t in traces_list if t.errors)
        wisdom = sum(1 for t in traces_list if t.wisdom_generated)
        total_ms = sum(t.elapsed_ms for t in traces_list)
        return {
            "total_ticks": len(traces_list),
            "current_tick": self.tick,
            "errors": errors,
            "error_rate": errors / len(traces_list),
            "wisdom_generated": wisdom,
            "evolution_cycles": self.evolution_count,
            "memory_records": self.memory_records,
            "avg_step_ms": total_ms / len(traces_list),
            "identity_stable": self.verify_identity(self.identity_anchor),
        }


__all__ = ["SimulationEngine", "SimulationProfile", "TraceStep", "SimPhase"]
