"""Phase 62: Cognitive Coupling Bridge — 信念 ↔ 稳态实时耦合。

将 BeliefManager 的信念变更事件实时桥接到 HomeostasisManager，
实现 BELIEF_MODEL.md 中定义的"信念冲突→认知熵→稳态调节"闭环。

架构:
    BeliefManager._event_log
         │  (事件流)
         ▼
    CognitiveCouplingBridge.on_belief_event(event)
         │  (分类/聚合)
         ▼
    HomeostasisManager 调整:
      - cognitive_entropy ↑  (矛盾增加时)
      - attention_reallocation (确认偏差警报)
      - cognitive_load_update  (信念强度变化)
      - memory_cleanup         (休眠信念过多)

用法:
    bridge = CognitiveCouplingBridge(belief_mgr, homeostasis_mgr)
    bridge.poll()  # 每次 tick 拉取信念事件并更新稳态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import time

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── CouplingConfig ───────────────────────────────────────────────────────────


@dataclass
class CouplingConfig:
    """耦合配置 — 控制事件→稳态响应的阈值。"""

    # 矛盾阈值
    contradiction_alert_threshold: int = 3       # 积累 N 个矛盾后发出警报
    contradiction_entropy_per_event: float = 0.15  # 每个矛盾增加的认知熵

    # 确认偏差
    confirmation_bias_dimension_threshold: int = 5  # 同维度信念数超过此值触发检查
    confirmation_bias_entropy_boost: float = 0.3    # 确认偏差时认知熵增量

    # 信念强度变化
    strength_shift_threshold: float = 0.5  # 概率变化超过此值触发更新
    strength_shift_load_factor: float = 0.05

    # 休眠信念
    dormant_count_threshold: int = 50       # 休眠信念数超过此值建议清理
    dormant_age_hours: int = 24             # 超过此时间未更新视为休眠

    # 全局上限
    max_cognitive_entropy: float = 10.0     # 认知熵上限（防溢出）
    min_cognitive_entropy: float = 0.0


# ── CouplingMetrics ──────────────────────────────────────────────────────────


@dataclass
class CouplingMetrics:
    """耦合指标 — 跨 session 可追踪。"""
    total_contradictions_processed: int = 0
    total_confirmation_bias_alerts: int = 0
    total_strength_shifts: int = 0
    total_dormancy_alerts: int = 0
    current_cognitive_entropy: float = 0.0
    last_poll_at: float = 0.0
    session_started_at: float = field(default_factory=time.time)


# ── CognitiveCouplingBridge ──────────────────────────────────────────────────


@dataclass
class CognitiveCouplingBridge:
    """信念 ↔ 稳态 实时耦合桥。

    连接 BeliefManager 的事件流与 HomeostasisManager 的健康调节，
    实现 BELIEF_MODEL.md 中定义的理论闭环。
    """

    # 被耦合的两个系统（由外部注入）
    belief_manager: Optional[object] = None       # BeliefManager
    homeostasis_manager: Optional[object] = None  # HomeostasisManager

    config: CouplingConfig = field(default_factory=CouplingConfig)
    metrics: CouplingMetrics = field(default_factory=CouplingMetrics)

    # 内部状态
    _pending_contradictions: list[dict] = field(default_factory=list)
    _recent_alerts: list[dict] = field(default_factory=list)
    _event_count_since_last_poll: int = 0

    # ── Public API ───────────────────────────────────────────────────────

    def poll(self) -> dict:
        """拉取 BeliefManager 的事件队列，处理并更新 Homeostasis。

        应该在每次认知 tick 中调用。
        返回本轮处理摘要。
        """
        self.metrics.last_poll_at = time.time()

        if self.belief_manager is None:
            return {"status": "no_belief_manager", "events_processed": 0}

        events = self._safe_drain_events()
        self._event_count_since_last_poll = len(events)

        if not events:
            return {"status": "no_events", "events_processed": 0}

        # 分类处理
        contradiction_events = [e for e in events if e.get("event") in (
            "belief_contradiction", "contradiction_detected",
        )]
        bias_events = [e for e in events if e.get("event") == "confirmation_bias_alert"]
        strength_events = [e for e in events if e.get("event") in (
            "belief_updated", "belief_strength_change",
        )]
        dormant_events = [e for e in events if e.get("event") == "belief_dormant"]

        # 1. 处理矛盾 → 认知熵
        self._process_contradictions(contradiction_events)

        # 2. 处理确认偏差
        self._process_confirmation_bias(bias_events)

        # 3. 处理信念强度变化
        self._process_strength_shifts(strength_events)

        # 4. 处理休眠信念
        self._process_dormancy(dormant_events)

        # 5. 将认知熵推入 Homeostasis
        self._apply_to_homeostasis()

        return {
            "status": "processed",
            "events_processed": len(events),
            "contradictions": len(contradiction_events),
            "bias_alerts": len(bias_events),
            "strength_shifts": len(strength_events),
            "dormancy_alerts": len(dormant_events),
            "cognitive_entropy": round(self.metrics.current_cognitive_entropy, 3),
        }

    def get_cognitive_entropy(self) -> float:
        """获取当前认知熵值。"""
        return self.metrics.current_cognitive_entropy

    def reset(self):
        """重置所有内部状态。"""
        self._pending_contradictions.clear()
        self._recent_alerts.clear()
        self.metrics = CouplingMetrics()

    # ── Internal: Event Processing ───────────────────────────────────────

    def _safe_drain_events(self) -> list[dict]:
        """安全地从 BeliefManager 提取事件。"""
        try:
            if hasattr(self.belief_manager, "drain_events"):
                return self.belief_manager.drain_events()
            if hasattr(self.belief_manager, "_event_log"):
                events = list(self.belief_manager._event_log)
                self.belief_manager._event_log.clear()
                return events
        except Exception:
            pass
        return []

    def _process_contradictions(self, events: list[dict]):
        """矛盾事件 → 累积认知熵。"""
        if not events:
            return

        self.metrics.total_contradictions_processed += len(events)
        self._pending_contradictions.extend(events)

        # 逐步增加认知熵
        for _ in events:
            self.metrics.current_cognitive_entropy = min(
                self.config.max_cognitive_entropy,
                self.metrics.current_cognitive_entropy + self.config.contradiction_entropy_per_event,
            )

        # 如果矛盾积累超过阈值，发出警报
        if len(self._pending_contradictions) >= self.config.contradiction_alert_threshold:
            self._recent_alerts.append({
                "type": "contradiction_burst",
                "count": len(self._pending_contradictions),
                "entropy": self.metrics.current_cognitive_entropy,
                "timestamp": time.time(),
            })
            # 清空已处理的矛盾
            self._pending_contradictions.clear()

    def _process_confirmation_bias(self, events: list[dict]):
        """确认偏差 → 提升认知熵 + 触发注意力重分配信号。"""
        if not events:
            return

        self.metrics.total_confirmation_bias_alerts += len(events)
        for _ in events:
            self.metrics.current_cognitive_entropy = min(
                self.config.max_cognitive_entropy,
                self.metrics.current_cognitive_entropy + self.config.confirmation_bias_entropy_boost,
            )

        self._recent_alerts.append({
            "type": "confirmation_bias",
            "count": len(events),
            "timestamp": time.time(),
        })

    def _process_strength_shifts(self, events: list[dict]):
        """信念强度变化 → 更新认知负载。"""
        if not events:
            return

        self.metrics.total_strength_shifts += len(events)
        total_shift = sum(
            abs(e.get("probability_delta", 0.0))
            for e in events
            if isinstance(e.get("probability_delta"), (int, float))
        )

        # 强度变化超过阈值时调整认知熵
        if total_shift >= self.config.strength_shift_threshold:
            delta = total_shift * self.config.strength_shift_load_factor
            self.metrics.current_cognitive_entropy = max(
                self.config.min_cognitive_entropy,
                min(self.config.max_cognitive_entropy, self.metrics.current_cognitive_entropy + delta),
            )

    def _process_dormancy(self, events: list[dict]):
        """休眠信念 → 如果超过阈值，记录建议。"""
        if not events:
            return

        self.metrics.total_dormancy_alerts += len(events)
        # 通过 get_belief_map 检查休眠总数
        dormant_count = len(events)

        if dormant_count >= self.config.dormant_count_threshold:
            self._recent_alerts.append({
                "type": "dormancy_overload",
                "dormant_count": dormant_count,
                "recommended_action": "gc",
                "timestamp": time.time(),
            })

    # ── Internal: Apply to Homeostasis ───────────────────────────────────

    def _apply_to_homeostasis(self):
        """将当前认知熵应用到 HomeostasisManager。

        通过 Homeostasis 的 context monitor 注入认知负载指标，
        使其在下一次 health_report() 中反映信念冲突带来的压力。
        """
        if self.homeostasis_manager is None:
            return

        try:
            # 通过 ContextMonitor 注入认知熵
            ctx = getattr(self.homeostasis_manager, "context", None)
            if ctx is not None:
                current_metrics = getattr(ctx, "_metrics", {})
                if isinstance(current_metrics, dict):
                    current_metrics["cognitive_entropy"] = self.metrics.current_cognitive_entropy
                    current_metrics["pending_contradictions"] = len(self._pending_contradictions)
                    current_metrics["recent_coupling_alerts"] = len(self._recent_alerts)
        except Exception:
            pass

    # ── Diagnostics ──────────────────────────────────────────────────────

    def diagnostics(self) -> dict:
        return {
            "entropy": round(self.metrics.current_cognitive_entropy, 3),
            "pending_contradictions": len(self._pending_contradictions),
            "recent_alerts": self._recent_alerts[-5:],  # 最近 5 条
            "metrics": {
                "contradictions": self.metrics.total_contradictions_processed,
                "bias_alerts": self.metrics.total_confirmation_bias_alerts,
                "strength_shifts": self.metrics.total_strength_shifts,
                "dormancy_alerts": self.metrics.total_dormancy_alerts,
            },
        }
