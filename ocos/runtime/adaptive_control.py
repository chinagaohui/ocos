"""
B6 Adaptive Control — 运行时参数自适应调节器。

职责：
- 根据资源负载 + 风险等级动态调节运行时参数
- 自动响应 RESOURCE_EXHAUSTED / RESOURCE_RELEASED 事件
- 产出 Adaptation 记录并发射 ADAPTATION_APPLIED 事件
- 支持缓慢恢复（步进+时间间隔），防止参数抖动

调用权规则：
  auto_adapt() 只能由以下途径触发：
  1. Event Bus 事件回调（RESOURCE_EXHAUSTED / RESOURCE_RELEASED）
  2. Runtime Scheduler 在安全上下文中调用
  禁止任何 Engine 或 Plugin 直接调用 auto_adapt()。
  外部组件如需查询当前参数，通过 get_config() 只读接口即可。

与 B5 ResourceManager 的协作：
  AdaptiveController 持有对 ResourceManager 的引用，定期查询使用率
  作为 auto_adapt 的输入信号。resource_manager 是必选依赖。

与 B4 PolicyEngine 的协作：
  PolicyEngine 可选传入，用于获取当前风险等级（high / normal / low）
  作为 auto_adapt 的第二输入信号。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.logging import get_logger

def _publish_safe(event_bus, event) -> None:
    """S1.6 (白皮书 P1-7): EventBus 的真实 API 是 publish（非 emit）。

    兼容 None 注入与异构总线；发布失败降级为 debug 日志不阻断。
    """
    publish = getattr(event_bus, "publish", None)
    if publish is None:
        return
    try:
        publish(event)
    except Exception as exc:  # 事件发射失败不阻断主流程（BR-04: 留痕不静默）
        get_logger(__name__).debug("event publish failed: %s", exc)

logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class RuntimeParam(str, Enum):
    """受调节的运行时参数。"""
    SIMULATION_DEPTH = "simulation_depth"
    LEARNING_RATE = "learning_rate"
    ATTENTION_THRESHOLD = "attention_threshold"
    SCHEDULER_MAX_QUEUE = "scheduler_max_queue"
    RESOURCE_CPU_LIMIT = "resource_cpu_limit"
    RESOURCE_MEMORY_LIMIT = "resource_memory_limit"


# ── 默认配置 ────────────────────────────────────────────────────────────────

# 参数边界
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "simulation_depth": (1.0, 10.0),
    "learning_rate": (0.0, 1.0),
    "attention_threshold": (0.0, 1.0),
    "scheduler_max_queue": (10.0, 1000.0),
    "resource_cpu_limit": (1.0, 64.0),
    "resource_memory_limit": (128.0, 262144.0),
}

DEFAULT_CONFIG: dict[str, float] = {
    "simulation_depth": 5.0,
    "learning_rate": 0.3,
    "attention_threshold": 0.4,
    "scheduler_max_queue": 100.0,
    "resource_cpu_limit": 8.0,
    "resource_memory_limit": 16384.0,
}

# 缓慢恢复配置
RECOVERY_COOLDOWN_SECONDS: float = 30.0  # 恢复步进的最小间隔


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AdaptiveConfig:
    """当前活跃的运行时参数快照（冻结、可序列化）。"""
    simulation_depth: float = 5.0
    learning_rate: float = 0.3
    attention_threshold: float = 0.4
    scheduler_max_queue: float = 100.0
    resource_cpu_limit: float = 8.0
    resource_memory_limit: float = 16384.0
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, float]:
        return {
            "simulation_depth": self.simulation_depth,
            "learning_rate": self.learning_rate,
            "attention_threshold": self.attention_threshold,
            "scheduler_max_queue": self.scheduler_max_queue,
            "resource_cpu_limit": self.resource_cpu_limit,
            "resource_memory_limit": self.resource_memory_limit,
        }


@dataclass(frozen=True)
class Adaptation:
    """单次参数调整记录（冻结、可序列化）。

    记录：什么参数变了、从多少变到多少、原因、触发源。
    trigger_event_id 指向触发自动调节的原始事件 ID，
    允许 Audit / Debug 追溯"为什么系统突然降低了 Simulation Depth"。
    """
    param: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    reason: str = ""  # "resource_exhausted" | "quota_exceeded" | "risk_high" | "recovery"
    trigger_event_id: str = ""  # 触发此调节的原始 Event ID（可选）
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION


# ── Risk 等级（简化枚举，由 PolicyEngine 输出） ─────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


# ── 内部工具 ────────────────────────────────────────────────────────────────

def _clamp(name: str, value: float) -> float:
    bounds = PARAM_BOUNDS.get(name)
    if bounds is None:
        return value
    lo, hi = bounds
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _now_ts() -> float:
    return time.time()


# ── AdaptiveController ──────────────────────────────────────────────────────

class AdaptiveController:
    """运行时参数自适应调节器。

    调节策略（auto_adapt 内部逻辑）：

    资源紧张方向（降级）：
      MEMORY 使用 > 80%   → simulation_depth -= 2（最低 1）
      MEMORY 使用 > 90%   → scheduler_max_queue /= 2（最低 10）
      CPU 使用 > 80%       → attention_threshold += 0.1（上限 0.9）
      GPU 使用 > 80%       → learning_rate *= 0.5
      Risk >= HIGH         → learning_rate *= 0.3, attention_threshold += 0.2

    恢复方向（缓慢步进）：
      资源使用 < 50% 且距上次恢复 >= 30 秒
      → simulation_depth += 1（上限默认值）
      → attention_threshold -= 0.05（下限默认值）
      → scheduler_max_queue *= 1.5（上限默认值）
      → learning_rate += 0.05（上限默认值）
    """

    def __init__(
        self,
        resource_manager: Any,
        policy_engine: Any = None,
        event_bus: Any = None,
        initial_config: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Args:
            resource_manager: B5 ResourceManager 实例（必选）
            policy_engine:    B4 PolicyEngine 实例（可选，用于获取风险等级）
            event_bus:        EventBus 实例（可选）
            initial_config:   初始参数覆盖（缺省使用 DEFAULT_CONFIG）
        """
        self._resource_manager = resource_manager
        self._policy_engine: Any = policy_engine
        self._event_bus: Any = event_bus

        # 当前参数
        base = dict(DEFAULT_CONFIG)
        if initial_config:
            base.update(initial_config)
        self._config: dict[str, float] = base

        # 恢复计时器
        self._last_recovery_ts: float = 0.0

        # 变更历史（限最近 100 条）
        self._adaptation_history: list[Adaptation] = []
        self._max_history: int = 100

        # Event Bus 订阅
        self._subscription_ids: list[str] = []
        self._subscribe_resource_events()

        logger.debug(
            "AdaptiveController initialized: config=%s, rm=%s, pe=%s, eb=%s",
            self._config,
            type(self._resource_manager).__name__,
            type(self._policy_engine).__name__ if self._policy_engine else None,
            self._event_bus is not None,
        )

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def adaptation_count(self) -> int:
        return len(self._adaptation_history)

    @property
    def last_recovery_ts(self) -> float:
        return self._last_recovery_ts

    # ── 查询 ────────────────────────────────────────────────────────────────

    def get_config(self) -> AdaptiveConfig:
        """返回当前参数快照（只读，所有 Engine / Plugin 均可安全调用）。"""
        return AdaptiveConfig(
            simulation_depth=self._clamped("simulation_depth"),
            learning_rate=self._clamped("learning_rate"),
            attention_threshold=self._clamped("attention_threshold"),
            scheduler_max_queue=self._clamped("scheduler_max_queue"),
            resource_cpu_limit=self._clamped("resource_cpu_limit"),
            resource_memory_limit=self._clamped("resource_memory_limit"),
        )

    def get_adaptation_history(
        self,
        limit: int = 20,
    ) -> list[Adaptation]:
        """返回最近的 Adaptation 记录（供 Audit / Debug 查询）。"""
        return list(self._adaptation_history[-limit:])

    # ── 显式调节（安全上下文调用） ──────────────────────────────────────────

    def adapt(
        self,
        params: dict[str, float],
        reason: str = "manual",
        trigger_event_id: str = "",
    ) -> list[Adaptation]:
        """显式设置参数值。

        可由 Runtime Scheduler 或管理员在安全上下文中调用。
        参数值会自动 clamp 到合法范围。
        Returns: 实际发生变更的 Adaptation 列表。
        """
        logger.info("Adapt called: params=%s reason=%s trigger=%s",
                     params, reason, trigger_event_id)
        adaptations: list[Adaptation] = []
        for name, value in params.items():
            if name not in DEFAULT_CONFIG:
                continue
            old = self._config.get(name, 0.0)
            new = _clamp(name, value)
            if abs(new - old) < 0.001:
                continue  # 无实际变更
            self._config[name] = new
            adaptations.append(Adaptation(
                param=name,
                old_value=old,
                new_value=new,
                reason=reason,
                trigger_event_id=trigger_event_id,
            ))

        if adaptations:
            self._record_adaptations(adaptations)
        return adaptations

    # ── 自动调节（仅限 Event Bus / Runtime Scheduler 调用） ────────────────
    #
    # 调用权规则：
    #   auto_adapt() 只能由以下途径触发：
    #   1. Event Bus 事件回调（RESOURCE_EXHAUSTED / RESOURCE_RELEASED）
    #   2. Runtime Scheduler 在安全上下文中调用
    #   禁止任何 Engine 或 Plugin 直接调用 auto_adapt()。
    #   外部组件如需查询当前参数，通过 get_config() 只读接口即可。

    def auto_adapt(
        self,
        trigger_event_id: str = "",
    ) -> list[Adaptation]:
        """根据当前资源使用率和风险等级自动调节参数。

        逐级降级策略（compress 方向）：
          资源紧张 → 降低 Simulation Depth / 提高 Attention Threshold
          高风险    → 降低 Learning Rate / 提高 Attention Threshold

        缓慢恢复策略（recovery 方向）：
          资源充裕 → 步进恢复，每次恢复间隔 >= RECOVERY_COOLDOWN_SECONDS
        """
        logger.info("Auto-adapt triggered: trigger=%s", trigger_event_id)
        adaptations: list[Adaptation] = []

        # ── 输入：资源使用率 ──
        usages = self._resource_manager.get_usage()
        usage_map: dict[str, float] = {
            u.resource_type: (
                1.0 - u.available / u.total if u.total > 0 else 0.0
            )
            for u in usages
        }

        memory_pct = usage_map.get("memory", 0.0)
        cpu_pct = usage_map.get("cpu", 0.0)
        gpu_pct = usage_map.get("gpu", 0.0)

        # ── 输入：风险等级 ──
        risk = self._get_risk_level()

        # ── 降级方向 ──
        has_degrade = False
        if memory_pct > 0.9:
            a = self._step_down("scheduler_max_queue", factor=0.5, lower=10.0)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)
        if memory_pct > 0.8:
            a = self._step_down("simulation_depth", delta=-2.0, lower=1.0)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)
        if cpu_pct > 0.8:
            a = self._step_up("attention_threshold", delta=0.1, upper=0.9)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)
        if gpu_pct > 0.8:
            a = self._step_down("learning_rate", factor=0.5, lower=0.05)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            a = self._step_down("learning_rate", factor=0.3, lower=0.01)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)
            a = self._step_up("attention_threshold", delta=0.2, upper=0.95)
            adaptations.extend(a)
            has_degrade = has_degrade or bool(a)

        # ── 恢复方向（缓慢步进） ──
        # 仅在本次无降级时才恢复，防止降级后被恢复部分撤销
        if not has_degrade and memory_pct < 0.5 and cpu_pct < 0.5 and gpu_pct < 0.5:
            now = _now_ts()
            if now - self._last_recovery_ts >= RECOVERY_COOLDOWN_SECONDS:
                rec_adapts = self._try_recovery()
                if rec_adapts:
                    self._last_recovery_ts = now
                    adaptations.extend(rec_adapts)

        # 标记触发事件
        if adaptations and trigger_event_id:
            adaptations = [
                Adaptation(
                    param=a.param,
                    old_value=a.old_value,
                    new_value=a.new_value,
                    reason=a.reason,
                    trigger_event_id=trigger_event_id,
                    timestamp=a.timestamp,
                )
                for a in adaptations
            ]

        if adaptations:
            self._record_adaptations(adaptations)
        return adaptations

    # ── 动态注入 ────────────────────────────────────────────────────────────

    def set_policy_engine(self, policy_engine: Any) -> None:
        """动态注入 PolicyEngine 实例。"""
        self._policy_engine = policy_engine
        logger.info("PolicyEngine injected")

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """重置为默认配置，清空历史。"""
        self._config = dict(DEFAULT_CONFIG)
        self._last_recovery_ts = 0.0
        self._adaptation_history.clear()
        logger.info("AdaptiveController reset")

    # ── 内部：降级步进 ──────────────────────────────────────────────────────

    def _step_down(
        self,
        param: str,
        delta: float = 0.0,
        factor: float = 0.0,
        lower: float = 1.0,
        reason: str = "resource_exhausted",
    ) -> list[Adaptation]:
        """按差值或倍率降低参数值，clamp 到 lower 以上。"""
        old = self._config.get(param, 0.0)
        if delta != 0.0:
            new = old + delta
        elif factor != 0.0:
            new = old * factor
        else:
            return []
        new = _clamp(param, new)
        if new >= old:
            return []  # clamp 后没有实际降低
        self._config[param] = new
        logger.debug("Step down: param=%s old=%.4f new=%.4f reason=%s",
                      param, old, new, reason)
        return [Adaptation(
            param=param, old_value=old, new_value=new, reason=reason,
        )]

    def _step_up(
        self,
        param: str,
        delta: float = 0.0,
        upper: float = 1.0,
        reason: str = "resource_exhausted",
    ) -> list[Adaptation]:
        """按差值提高参数值，clamp 到 upper 以下。"""
        old = self._config.get(param, 0.0)
        new = old + delta
        new = _clamp(param, new)
        if new <= old:
            return []  # clamp 后没有实际提高
        self._config[param] = new
        logger.debug("Step up: param=%s old=%.4f new=%.4f reason=%s",
                      param, old, new, reason)
        return [Adaptation(
            param=param, old_value=old, new_value=new, reason=reason,
        )]

    # ── 内部：缓慢恢复 ──────────────────────────────────────────────────────

    def _try_recovery(self) -> list[Adaptation]:
        """尝试朝默认值恢复一个步长。"""
        logger.debug("Attempting recovery")
        adaptations: list[Adaptation] = []
        defaults = DEFAULT_CONFIG

        # simulation_depth → 默认值 5.0
        cur = self._clamped("simulation_depth")
        target = defaults["simulation_depth"]
        if cur < target:
            new = min(cur + 1.0, target)
            self._config["simulation_depth"] = new
            adaptations.append(Adaptation(
                param="simulation_depth",
                old_value=cur,
                new_value=new,
                reason="recovery",
            ))

        # attention_threshold → 默认值 0.4
        cur = self._clamped("attention_threshold")
        target = defaults["attention_threshold"]
        if cur > target:
            new = max(cur - 0.05, target)
            self._config["attention_threshold"] = new
            adaptations.append(Adaptation(
                param="attention_threshold",
                old_value=cur,
                new_value=new,
                reason="recovery",
            ))

        # scheduler_max_queue → 默认值 100
        cur = self._clamped("scheduler_max_queue")
        target = defaults["scheduler_max_queue"]
        if cur < target:
            new = min(cur * 1.5, target)
            self._config["scheduler_max_queue"] = new
            adaptations.append(Adaptation(
                param="scheduler_max_queue",
                old_value=cur,
                new_value=new,
                reason="recovery",
            ))

        # learning_rate → 默认值 0.3
        cur = self._clamped("learning_rate")
        target = defaults["learning_rate"]
        if cur < target:
            new = min(cur + 0.05, target)
            self._config["learning_rate"] = new
            adaptations.append(Adaptation(
                param="learning_rate",
                old_value=cur,
                new_value=new,
                reason="recovery",
            ))

        return adaptations

    # ── 内部：风险等级 ──────────────────────────────────────────────────────

    def _get_risk_level(self) -> RiskLevel:
        """从 PolicyEngine 获取当前风险等级。"""
        if self._policy_engine is None:
            logger.debug("No policy engine, returning NORMAL risk")
            return RiskLevel.NORMAL
        try:
            risk_str = self._policy_engine.get_risk_level()
            return RiskLevel(risk_str)
        except (AttributeError, ValueError, TypeError):
            return RiskLevel.NORMAL

    # ── 内部：记录与事件发射 ────────────────────────────────────────────────

    def _record_adaptations(self, adaptations: list[Adaptation]) -> None:
        """记录 Adaptation 并发射 ADAPTATION_APPLIED 事件。"""
        logger.debug("Recording %d adaptations", len(adaptations))
        self._adaptation_history.extend(adaptations)
        # 限容
        if len(self._adaptation_history) > self._max_history:
            self._adaptation_history = self._adaptation_history[-self._max_history:]

        # 发射事件
        if self._event_bus is not None:
            _publish_safe(self._event_bus, Event(
                event_type=EventType.ADAPTATION_APPLIED,
                source="adaptive-control",
                payload={
                    "adaptations": [
                        {
                            "param": a.param,
                            "old_value": a.old_value,
                            "new_value": a.new_value,
                            "reason": a.reason,
                            "trigger_event_id": a.trigger_event_id,
                            "timestamp": a.timestamp,
                        }
                        for a in adaptations
                    ],
                },
            ))

    def _clamped(self, name: str) -> float:
        return _clamp(name, self._config.get(name, 0.0))

    # ── Event Bus 订阅 ──────────────────────────────────────────────────────

    def _subscribe_resource_events(self) -> None:
        """订阅 B5 Resource Manager 事件，触发自动调节。"""
        if self._event_bus is None:
            logger.debug("No event bus, skipping resource event subscription")
            return

        logger.debug("Subscribing to resource events")
        sid_exhausted = self._event_bus.subscribe(
            EventType.RESOURCE_EXHAUSTED,
            self._on_resource_exhausted,
            subscriber_id="adaptive-control-resource-exhausted",
        )
        self._subscription_ids.append(sid_exhausted)

        sid_released = self._event_bus.subscribe(
            EventType.RESOURCE_RELEASED,
            self._on_resource_released,
            subscriber_id="adaptive-control-resource-released",
        )
        self._subscription_ids.append(sid_released)

    def _on_resource_exhausted(self, event: Event) -> None:
        """RESOURCE_EXHAUSTED 事件回调 → 触发 auto_adapt。"""
        self.auto_adapt(trigger_event_id=event.event_id)

    def _on_resource_released(self, event: Event) -> None:
        """RESOURCE_RELEASED 事件回调 → 触发 auto_adapt（评估恢复）。"""
        self.auto_adapt(trigger_event_id=event.event_id)

    def unsubscribe_all(self) -> None:
        """取消所有 Event Bus 订阅。"""
        if self._event_bus is None:
            return
        for sid in self._subscription_ids:
            self._event_bus.unsubscribe(sid)
        self._subscription_ids.clear()
