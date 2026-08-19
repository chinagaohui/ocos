"""Phase 60: Runtime Configuration — timing, thresholds, triggers.

Defines the rhythm of OCOS's autonomous cognitive life.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class LoopMode(Enum):
    """OCOS runtime modes."""
    IDLE = "idle"            # Waiting for external trigger
    ACTIVE = "active"        # Running autonomous loop
    REFLECTING = "reflecting" # Self-review / consolidation
    SLEEPING = "sleeping"    # Low-power, minimal processing
    RECOVERING = "recovering" # Post-error recovery


class WakeTrigger(Enum):
    """What wakes OCOS from sleep."""
    EXTERNAL_INPUT = "external_input"       # Hermes feeds something
    INTERNAL_TIMER = "internal_timer"        # Scheduled wake
    GOAL_VIOLATION = "goal_violation"       # Something important needs attention
    FEEDBACK_ARRIVED = "feedback_arrived"   # OpenTale chapter ready
    CURIOSITY_SPIKE = "curiosity_spike"     # Random exploration impulse
    ANOMALY_DETECTED = "anomaly_detected"   # Something unusual


@dataclass
class RuntimeConfig:
    """Configuration for autonomous OCOS runtime loop.

    Controls timing, attention thresholds, sleep/wake behavior,
    and safety boundaries.
    """

    # ── Timing ──

    tick_interval_ms: int = 2000          # Time between cognitive ticks (2s default)
    min_tick_interval_ms: int = 500       # Fastest allowed (prevents spin)
    max_tick_interval_ms: int = 30000     # Slowest allowed (30s)

    # ── Sleep/Wake ──

    idle_timeout_ms: int = 60000           # 60s no input → sleep mode
    sleep_duration_ms: int = 300000        # 5min sleep minimum
    wake_on_external: bool = True          # Wake when Hermes feeds input
    wake_on_feedback: bool = True          # Wake when OpenTale produces output
    wake_on_goal_urgency: bool = True      # Wake when goal urgency > threshold

    # ── Attention ──

    attention_decay_rate: float = 0.05     # Per tick decay (0 = no decay, 1 = instant)
    min_attention_weight: float = 0.1      # Below this, shift focus
    max_focus_duration_ticks: int = 50     # Max ticks on same focus (prevents stuck)

    # ── Decision ──

    decision_confidence_threshold: float = 0.5  # Min confidence to execute
    max_pending_decisions: int = 10             # Queue limit

    # ── Action ──

    max_actions_per_tick: int = 1           # One at a time
    action_cooldown_ms: int = 5000          # Min time between external actions
    max_consecutive_actions: int = 20       # Safety cap

    # ── Learning ──

    consolidate_interval_ticks: int = 10    # Consolidate every N ticks
    max_experiences: int = 5000             # Experience buffer size

    # ── Safety ──

    max_ticks_per_session: int = 10000      # Hard safety cap
    runaway_threshold_ms: int = 100         # If ticks < this → runaway alarm
    identity_check_interval_ticks: int = 100  # Identity drift check frequency
    max_goal_self_generation: int = 0       # OCOS cannot create its own goals (CL46-01)

    # ── Health ──

    health_check_interval_ticks: int = 10   # Full health check every N ticks
    auto_recovery_enabled: bool = True      # Attempt self-recovery on errors
    max_recovery_attempts: int = 3          # Before giving up

    def validate(self) -> list[str]:
        """Validate config and return warnings/errors."""
        issues: list[str] = []
        if self.tick_interval_ms < self.min_tick_interval_ms:
            issues.append(f"tick_interval {self.tick_interval_ms}ms below min {self.min_tick_interval_ms}ms")
        if self.tick_interval_ms > self.max_tick_interval_ms:
            issues.append(f"tick_interval {self.tick_interval_ms}ms above max {self.max_tick_interval_ms}ms")
        if self.max_goal_self_generation > 0:
            issues.append("CL46-01 VIOLATION: max_goal_self_generation > 0")
        if self.max_consecutive_actions > 100:
            issues.append(f"max_consecutive_actions {self.max_consecutive_actions} is dangerously high")
        return issues


@dataclass
class LoopStats:
    """Runtime statistics for the autonomous loop."""
    total_ticks: int = 0
    ticks_this_session: int = 0
    actions_dispatched: int = 0
    open_tale_chapters: int = 0
    web_searches_performed: int = 0
    sleep_cycles: int = 0
    recovery_attempts: int = 0
    health_alerts: int = 0
    total_runtime_ms: float = 0.0
    avg_tick_ms: float = 0.0
    current_mode: str = "idle"
