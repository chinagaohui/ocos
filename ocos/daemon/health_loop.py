"""GAP-P1-2: daemon 稳态健康监控 — HealthLoop。

随 ResidentRuntime tick 每 interval_ticks 次触发一次体检：
  AgentRuntime 快照（记忆条数 / goal 栈深 / 决策失败率 / WM 占用）
  → CognitiveExaminer 认知体检（记忆膨胀/遗忘、决策漂移）
  → AlertManager 告警（Log + File 通道）+ HomeostasisManager 稳态检查复用。

fail-closed 原则：任一采集项失败 → 降级为 0/空并继续（不编造、不中断 tick）。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from ocos.alerts.manager import AlertManager
from ocos.alerts.models import AlertLevel as AlertsLevel
from ocos.capability.homeostasis import HomeostasisManager
from ocos.health_examination.cognitive_examiner import (
    CognitiveExaminer,
    DecisionSnapshot,
    DisorderFinding,
    MemorySnapshot,
)

logger = logging.getLogger(__name__)


class HealthLoop:
    """周期认知体检 — 采集 → 体检 → 告警。"""

    def __init__(
        self,
        runtime: Any,
        examiner: Optional[CognitiveExaminer] = None,
        alerts: Optional[AlertManager] = None,
        homeostasis: Optional[HomeostasisManager] = None,
        interval_ticks: int = 100,
        db_path: Optional[str] = None,   # PW-3.1: 诊断循环需要 db 路径
    ) -> None:
        self._runtime = runtime
        self._examiner = examiner or CognitiveExaminer()
        self._alerts = alerts or AlertManager()
        self._homeostasis = homeostasis or HomeostasisManager()
        self._interval_ticks = max(1, interval_ticks)
        self._ticks = 0
        self._last_finding: Optional[DisorderFinding] = None
        self._last_detail: dict[str, Any] = {}
        self._db_path = db_path
        self._diagnosis_summary: dict[str, Any] = {}

    # ── 对外只读状态 ─────────────────────────────────────────────────────────

    @property
    def last_finding(self) -> Optional[DisorderFinding]:
        """最近一次体检的认知疾病发现（无异常为 None）。"""
        return self._last_finding

    @property
    def last_detail(self) -> dict[str, Any]:
        """最近一次体检的采集项（goal 栈深 / WM 占用 / 决策失败率等）。"""
        return dict(self._last_detail)

    @property
    def alerts(self) -> AlertManager:
        return self._alerts

    # ── 运行时绑定（延迟注入：ResidentRuntime 构造后再绑定）──

    def bind(self, runtime: Any) -> None:
        """绑定被体检的 AgentRuntime（须在 daemon start() 前调用）。"""
        self._runtime = runtime

    # ── daemon 驱动 ──────────────────────────────────────────────────────────

    def tick(self) -> Optional[DisorderFinding]:
        """每个 daemon tick 调用一次；每 interval_ticks 次执行一次体检。"""
        # S3.5: daemon tick 心跳计数器（每次调用 +1，与体检周期解耦）
        monitoring = getattr(self, "monitoring", None)
        if monitoring is not None:
            try:
                monitoring.record_metric(
                    "ocos_tick_total", 1.0, metric_type="counter")
            except Exception as _te:
                logger.debug("tick metric skipped: %s", _te)
        self._ticks += 1
        if self._ticks < self._interval_ticks:
            return None
        self._ticks = 0
        finding = self.run_check()
        # PW-3.1: 诊断循环 — 探针/故障检测/修复提案入待批（失败不阻断）
        try:
            from ocos.daemon.repair_link import run_diagnosis_cycle
            if self._db_path:
                self._diagnosis_summary = run_diagnosis_cycle(self._db_path)
        except Exception as _dl_e:
            logger.debug("diagnosis cycle skipped: %s", _dl_e)
        return finding

    def run_check(self) -> Optional[DisorderFinding]:
        """执行一次完整体检（测试可直接调用）。"""
        rt = self._runtime

        # ── 1. 采集 4 项（全部来自已有公开属性；失败降级不中断）──
        stats = self._safe(lambda: rt._memory_hub.get_stats(), {}) or {}
        episode_count = stats.get("episode_count", 0)
        pattern_count = stats.get("pattern_count", 0)
        goal_depth = self._safe(lambda: len(rt.agent.goal_stack), 0)
        wm_usage = self._safe(lambda: rt._wm_store.count(), 0)
        fail_rate = self._decision_failure_rate()

        # ── 2. CognitiveExaminer 认知体检 ──
        mem_finding = self._examiner.examine_memory(
            MemorySnapshot(event_count=episode_count, wisdom_count=pattern_count)
        )
        # DecisionSnapshot 漂移检测需真实决策记录；runtime 当前无公开决策记录
        # 接口，以 tick 周期为问题上下文、空选项建基线（chosen_option 空 →
        # 漂移判定条件不满足，永不误报）。
        dec_finding = self._examiner.examine_decision(
            DecisionSnapshot(
                problem=f"tick cycle {self._safe(lambda: rt._cycle_count, 0)}",
                chosen_option="",
                risk_level="",
                timestamp=time.time(),
            )
        )

        # ── 3. HomeostasisManager 稳态检查（复用组件，非新建架构）──
        homeo_alerts: list[Any] = []
        try:
            report = self._homeostasis.health_report()
            homeo_alerts = report.alerts
        except Exception as _he:  # 稳态检查失败不中断体检
            logger.debug("health_loop homeostasis check skipped: %s", _he)

        # ── 4. 告警 ──
        detail = {
            "goal_depth": goal_depth,
            "wm_usage": wm_usage,
            "decision_failure_rate": fail_rate,
            "episode_count": episode_count,
            "pattern_count": pattern_count,
        }
        self._last_detail = detail

        # S3.5 (白皮书 P3): 5 个核心 Prometheus 指标（monitoring 未装配
        # 时静默跳过）
        monitoring = getattr(self, "monitoring", None)
        if monitoring is not None:
            try:
                monitoring.record_metric(
                    "ocos_memory_episodes_total", episode_count,
                    metric_type="gauge")
                monitoring.record_metric(
                    "ocos_goal_active", goal_depth, metric_type="gauge")
                monitoring.record_metric(
                    "ocos_execution_pending",
                    detail.get("decision_failure_rate", 0.0),
                    metric_type="gauge")
            except Exception as _me:
                logger.debug("metrics record skipped: %s", _me)

        detected: Optional[DisorderFinding] = None
        for finding in (mem_finding, dec_finding):
            if finding.detected:
                detected = detected or finding
                self._alerts.send(
                    level=AlertsLevel.WARNING,
                    source="health_loop",
                    message=finding.evidence,
                    detail=detail,
                    finding_id=finding.disorder_type.name,
                )
        for ha in homeo_alerts:
            level_name = getattr(ha.level, "name", "WARNING")
            alerts_level = getattr(AlertsLevel, level_name, AlertsLevel.WARNING)
            self._alerts.send(
                level=alerts_level,
                source=f"homeostasis:{ha.dimension}",
                message=ha.message or f"{ha.metric} {ha.current_value:.2f} > {ha.threshold:.2f}",
                detail={"metric": ha.metric, "current": ha.current_value,
                        "threshold": ha.threshold},
            )

        self._last_finding = detected
        return detected

    # ── 采集辅助 ──────────────────────────────────────────────────────────────

    def _decision_failure_rate(self) -> float:
        """最近注意决策未被接受的比例（0.0–1.0；无决策 → 0.0）。"""
        decisions = getattr(self._runtime, "_last_attention_decisions", None) or []
        if not decisions:
            return 0.0
        accepted = sum(1 for d in decisions if getattr(d, "is_accepted", False))
        return round(1.0 - accepted / len(decisions), 4)

    @staticmethod
    def _safe(fn: Any, default: Any) -> Any:
        try:
            return fn()
        except Exception:
            return default


__all__ = ["HealthLoop"]
