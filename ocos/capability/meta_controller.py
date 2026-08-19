"""Phase 23 — Meta Controller。

认知循环监控：
  - 死循环检测：同一 Skill 重复执行 N 次
  - 停滞检测：连续 3 次失败
  - 超时检测：Process 时间预算超限
  - 路径过长检测：Skill 数量超阈值
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.capability.models import ProcessGraph, SkillStatus


@dataclass
class MetaControllerConfig:
    """Meta Controller 配置。"""

    max_skill_retries: int = 3
    max_process_duration_seconds: float = 300.0
    max_skills_per_process: int = 50
    min_progress_required: float = 0.01
    deadlock_threshold: int = 5  # 同一 Skill 连续执行 N 次 → 死锁


@dataclass
class Intervention:
    """监控干预"""

    process_id: str
    interventions: list[tuple[str, str]] = field(default_factory=list)
    decision: str = "continue"  # "continue" | "retry" | "abort" | "warn"


class MetaController:
    """认知循环元控制器。

    监控 Process Graph 执行，检测异常并发出干预建议。

    用法:
        controller = MetaController()
        intervention = controller.monitor(process)
        if intervention.decision == "abort":
            executor.stop(process.id)
    """

    def __init__(self, config: Optional[MetaControllerConfig] = None):
        self._config = config or MetaControllerConfig()
        self._intervention_history: list[dict[str, Any]] = []

    # ── 监控入口 ────────────────────────────────────────────────────────

    def monitor(self, process: ProcessGraph) -> Intervention:
        """监控 Process Graph，返回干预建议。"""
        interventions: list[tuple[str, str]] = []

        # 死循环检测
        deadlock = self._detect_deadlock(process)
        if deadlock:
            interventions.append(("DEADLOCK", deadlock))

        # 路径过长检测
        skill_count = len(process.execution_history)
        if skill_count > self._config.max_skills_per_process:
            interventions.append(
                ("PATH_TOO_LONG", f"skills={skill_count}")
            )

        # 时长超限检测
        if (
            process.start_time
            and process.total_duration > 0
            and process.total_duration
            > self._config.max_process_duration_seconds
        ):
            interventions.append(
                ("TIMEOUT", f"duration={process.total_duration:.1f}s")
            )

        # 停滞检测（连续 3 次失败）
        if self._detect_stall(process):
            interventions.append(
                ("STALLED", "no progress in last 3 skills")
            )

        if interventions:
            return Intervention(
                process_id=process.id,
                interventions=interventions,
                decision=self._decide_intervention(interventions),
            )

        return Intervention(process_id=process.id, interventions=[])

    # ── 检测方法 ────────────────────────────────────────────────────────

    def _detect_deadlock(self, process: ProcessGraph) -> Optional[str]:
        """检测死循环：同一 Skill 连续执行 N 次无变化。"""
        count = process.repeated_skill_count()
        if count >= self._config.deadlock_threshold:
            return (
                f"skill repeated {count} times without change "
                f"(threshold: {self._config.deadlock_threshold})"
            )
        return None

    def _detect_stall(self, process: ProcessGraph) -> bool:
        """检测停滞：连续 3 次失败。"""
        return process.failed_count() >= 3

    def _decide_intervention(
        self, interventions: list[tuple[str, str]]
    ) -> str:
        """根据检测结果决定干预级别。"""
        for intervention_type, _ in interventions:
            if intervention_type in ("DEADLOCK", "TIMEOUT"):
                return "abort"
        if any(t == "STALLED" for t, _ in interventions):
            return "retry"
        return "warn"

    # ── 干预执行 ────────────────────────────────────────────────────────

    def intervene(
        self,
        executor: Any,
        process_id: str,
        action: str,
    ) -> None:
        """执行干预。"""
        self._intervention_history.append({
            "process_id": process_id,
            "action": action,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if action == "abort" and hasattr(executor, "stop"):
            executor.stop(process_id)

    @property
    def intervention_history(self) -> list[dict[str, Any]]:
        return list(self._intervention_history)

    def clear_history(self) -> None:
        self._intervention_history.clear()
