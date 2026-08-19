"""Phase 46: HealthMonitor — 认知健康监控器。

全系统健康自检，监控所有 Phase 39-45 模块。

监控维度:
    - Memory 是否异常增长
    - Decision 是否漂移
    - Capability 是否退化
    - World Model 是否冲突
    - Attention 是否失控
    - Runtime 是否稳定

边界 CL46-02: Health ≠ Self-Rewrite
    允许: 发现问题 → 提出修复建议 → 执行受限修复
    禁止: 自我重新定义、修改 Identity、修改核心原则
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_loop.loop_types import (
    HealthSignal, ModuleHealth, CognitiveHealthReport,
)


@dataclass
class HealthMonitor:
    """认知健康监控器。

    在每个 tick 检查所有模块的健康状态。
    """

    _history: list[CognitiveHealthReport] = field(default_factory=list)
    _module_metrics: dict[str, float] = field(default_factory=lambda: {
        "runtime": 1.0,
        "self_model": 1.0,
        "memory": 1.0,
        "world_model": 1.0,
        "decision": 1.0,
        "extension": 1.0,
        "capability": 1.0,
        "attention": 1.0,
        "perception": 1.0,
        "learning": 1.0,
    })

    # 允许的修复操作 (CL46-02 约束)
    ALLOWED_REPAIRS: list[str] = field(default_factory=lambda: [
        "reconnect_capability",
        "adjust_attention_weight",
        "clear_stale_memory_cache",
        "reload_world_snapshot",
        "pause_degraded_extension",
        "request_context_resync",
        "log_anomaly",
    ])

    # 禁止的修复操作
    FORBIDDEN_REPAIRS: list[str] = field(default_factory=lambda: [
        "modify_identity",
        "rewrite_constitution",
        "alter_core_principles",
        "redefine_self",
        "bypass_permission",
    ])

    def check(
        self,
        tick_id: int,
        memory_count: int = 0,
        attention_weight: float = 0.5,
        capability_states: dict[str, float] | None = None,
        decision_consistency: float = 1.0,
    ) -> CognitiveHealthReport:
        """执行全系统健康检查。"""
        modules: list[ModuleHealth] = []
        anomalies: list[str] = []
        repairs: list[str] = []

        # 1. Memory 检查
        memory_health = self._check_memory(memory_count)
        self._module_metrics["memory"] = memory_health.metric_value
        modules.append(memory_health)
        if memory_health.signal != HealthSignal.NORMAL:
            anomalies.append(memory_health.anomaly_description)
            repairs.append("clear_stale_memory_cache")

        # 2. Attention 检查
        attn_health = self._check_attention(attention_weight)
        self._module_metrics["attention"] = attn_health.metric_value
        modules.append(attn_health)
        if attn_health.signal != HealthSignal.NORMAL:
            anomalies.append(attn_health.anomaly_description)
            repairs.append("adjust_attention_weight")

        # 3. Capability 检查
        cap_health = self._check_capabilities(capability_states or {})
        self._module_metrics["capability"] = cap_health.metric_value
        modules.append(cap_health)
        if cap_health.signal != HealthSignal.NORMAL:
            anomalies.append(cap_health.anomaly_description)
            repairs.append("reconnect_capability")

        # 4. Decision 检查
        d_health = self._check_decision(decision_consistency)
        self._module_metrics["decision"] = d_health.metric_value
        modules.append(d_health)
        if d_health.signal != HealthSignal.NORMAL:
            anomalies.append(d_health.anomaly_description)

        # 5. 整体评估
        overall = self._assess_overall(modules)

        report = CognitiveHealthReport(
            tick_id=tick_id,
            overall=overall,
            modules=modules,
            anomalies=anomalies,
            repair_suggestions=repairs,
        )
        self._history.append(report)
        # 保持最近 200 份
        if len(self._history) > 200:
            self._history = self._history[-100:]

        return report

    def _check_memory(self, count: int) -> ModuleHealth:
        if count > 10_000:
            return ModuleHealth("memory", HealthSignal.ALERT, 0.2, f"Memory overflow: {count} items")
        if count > 5_000:
            return ModuleHealth("memory", HealthSignal.WARNING, 0.5, f"Memory growing: {count} items")
        return ModuleHealth("memory", HealthSignal.NORMAL, 1.0)

    def _check_attention(self, weight: float) -> ModuleHealth:
        if weight > 0.95:
            return ModuleHealth("attention", HealthSignal.WARNING, 0.6, "Attention hyper-focus (risk: tunnel vision)")
        if weight < 0.1:
            return ModuleHealth("attention", HealthSignal.WARNING, 0.4, "Attention too low (risk: disengagement)")
        return ModuleHealth("attention", HealthSignal.NORMAL, 1.0)

    def _check_capabilities(self, states: dict[str, float]) -> ModuleHealth:
        degraded = [k for k, v in states.items() if v < 0.5]
        if degraded:
            return ModuleHealth(
                "capability", HealthSignal.WARNING, 0.5,
                f"Degraded capabilities: {degraded}",
            )
        return ModuleHealth("capability", HealthSignal.NORMAL, 1.0)

    def _check_decision(self, consistency: float) -> ModuleHealth:
        if consistency < 0.3:
            return ModuleHealth("decision", HealthSignal.ALERT, 0.2, "Decision drift detected")
        if consistency < 0.6:
            return ModuleHealth("decision", HealthSignal.WARNING, 0.5, "Decision pattern shifting")
        return ModuleHealth("decision", HealthSignal.NORMAL, 1.0)

    def _assess_overall(self, modules: list[ModuleHealth]) -> HealthSignal:
        signals = [m.signal for m in modules]
        if HealthSignal.CRITICAL in signals:
            return HealthSignal.CRITICAL
        if HealthSignal.ALERT in signals:
            return HealthSignal.ALERT
        if HealthSignal.WARNING in signals:
            return HealthSignal.WARNING
        return HealthSignal.NORMAL

    def propose_repair(self, anomaly: str) -> str | None:
        """根据异常提出修复建议——受限于 ALLOWED_REPAIRS。

        禁止自我重写 (CL46-02)。
        """
        if "memory" in anomaly.lower():
            return "clear_stale_memory_cache"
        if "attention" in anomaly.lower():
            return "adjust_attention_weight"
        if "capability" in anomaly.lower():
            return "reconnect_capability"
        if "decision" in anomaly.lower():
            return "log_anomaly"
        return None

    @property
    def latest_report(self) -> CognitiveHealthReport | None:
        return self._history[-1] if self._history else None

    @property
    def all_metrics(self) -> dict[str, float]:
        return dict(self._module_metrics)

    @property
    def is_healthy(self) -> bool:
        report = self.latest_report
        return report.is_healthy if report else True


__all__ = ["HealthMonitor"]
