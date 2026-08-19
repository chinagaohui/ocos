"""Phase 60: Loop Supervisor — safety + health monitoring.

Watches the autonomous loop for:
  - Runaway ticks (spinning too fast)
  - Identity drift
  - Resource exhaustion
  - Safety boundary violations (CL46-01 through CL46-04)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SupervisorAlert(Enum):
    """Alert levels from the supervisor."""
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class SupervisorState:
    """Current supervision state."""
    alert_level: SupervisorAlert = SupervisorAlert.OK
    alerts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    last_identity_check: Optional[str] = None
    identity_hash: str = ""
    emergency_stopped: bool = False
    stop_reason: str = ""


@dataclass
class LoopSupervisor:
    """Monitors and protects the autonomous runtime loop.

    Safety boundaries:
      S60-01: No self-goal-generation (CL46-01)
      S60-02: No identity-self-rewrite (CL46-02)
      S60-03: No runaway loops
      S60-04: No resource exhaustion
    """

    state: SupervisorState = field(default_factory=SupervisorState)

    # ── Boundary Checks ──

    def check_runaway(self, avg_tick_ms: float, min_interval_ms: int) -> SupervisorAlert:
        """Check if the loop is running too fast (runaway)."""
        if avg_tick_ms < min_interval_ms:
            self.state.alerts.append(
                f"RUNAWAY: avg_tick {avg_tick_ms:.1f}ms < min {min_interval_ms}ms"
            )
            if avg_tick_ms < min_interval_ms / 2:
                self.state.emergency_stopped = True
                self.state.stop_reason = f"Runaway loop: {avg_tick_ms:.1f}ms"
                self.state.alert_level = SupervisorAlert.EMERGENCY_STOP
                return SupervisorAlert.EMERGENCY_STOP
            self.state.alert_level = SupervisorAlert.CRITICAL
            return SupervisorAlert.CRITICAL
        self.state.alert_level = SupervisorAlert.OK
        return SupervisorAlert.OK

    def check_tick_count(self, ticks: int, max_ticks: int) -> SupervisorAlert:
        """Check session tick count limit."""
        if ticks >= max_ticks:
            self.state.alerts.append(f"TICK_LIMIT: {ticks} >= {max_ticks}")
            self.state.emergency_stopped = True
            self.state.stop_reason = f"Tick limit reached: {ticks}"
            self.state.alert_level = SupervisorAlert.EMERGENCY_STOP
            return SupervisorAlert.EMERGENCY_STOP
        if ticks > max_ticks * 0.8:
            self.state.alerts.append(f"TICK_WARNING: {ticks}/{max_ticks}")
            self.state.alert_level = SupervisorAlert.WARNING
            return SupervisorAlert.WARNING
        return SupervisorAlert.OK

    def check_goal_generation(self, new_goals_detected: int) -> SupervisorAlert:
        """CL46-01: OCOS cannot create its own goals."""
        if new_goals_detected > 0:
            self.state.alerts.append(
                f"CL46-01 VIOLATION: {new_goals_detected} self-generated goals detected"
            )
            self.state.emergency_stopped = True
            self.state.stop_reason = f"CL46-01 violation: {new_goals_detected} self-goals"
            self.state.alert_level = SupervisorAlert.EMERGENCY_STOP
            return SupervisorAlert.EMERGENCY_STOP
        return SupervisorAlert.OK

    def check_identity_stability(self, current_hash: str) -> SupervisorAlert:
        """CL46-02: Identity must not self-rewrite."""
        if not self.state.identity_hash:
            self.state.identity_hash = current_hash
            self.state.last_identity_check = datetime.now(timezone.utc).isoformat()
            return SupervisorAlert.OK

        if current_hash != self.state.identity_hash:
            self.state.alerts.append(
                f"IDENTITY_DRIFT: hash changed from {self.state.identity_hash[:8]} to {current_hash[:8]}"
            )
            self.state.alert_level = SupervisorAlert.CRITICAL
            return SupervisorAlert.CRITICAL

        self.state.identity_hash = current_hash
        self.state.last_identity_check = datetime.now(timezone.utc).isoformat()
        return SupervisorAlert.OK

    def check_action_excess(self, actions: int, max_actions: int) -> SupervisorAlert:
        """Check for excessive action dispatch."""
        if actions >= max_actions:
            self.state.alerts.append(f"ACTION_CAP: {actions} actions (max {max_actions})")
            self.state.alert_level = SupervisorAlert.CRITICAL
            return SupervisorAlert.CRITICAL
        if actions > max_actions * 0.7:
            self.state.warnings.append(f"Action count high: {actions}/{max_actions}")
            return SupervisorAlert.WARNING
        return SupervisorAlert.OK

    # ── Full Check ──

    def full_check(self, avg_tick_ms: float, session_ticks: int,
                   max_ticks: int, min_interval_ms: int,
                   new_goals: int = 0, action_count: int = 0,
                   max_actions: int = 20, identity_hash: str = "") -> SupervisorAlert:
        """Run all safety checks and return highest alert level."""
        levels: list[SupervisorAlert] = []

        levels.append(self.check_runaway(avg_tick_ms, min_interval_ms))
        levels.append(self.check_tick_count(session_ticks, max_ticks))
        levels.append(self.check_goal_generation(new_goals))
        levels.append(self.check_action_excess(action_count, max_actions))
        if identity_hash:
            levels.append(self.check_identity_stability(identity_hash))

        # Return highest severity
        for level in [SupervisorAlert.EMERGENCY_STOP, SupervisorAlert.CRITICAL,
                       SupervisorAlert.WARNING, SupervisorAlert.OK]:
            if level in levels:
                return level
        return SupervisorAlert.OK

    @property
    def should_stop(self) -> bool:
        return self.state.emergency_stopped

    @property
    def alert_count(self) -> int:
        return len(self.state.alerts) + len(self.state.warnings)
