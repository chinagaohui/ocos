"""Phase 60: Autonomous Loop — self-running cognitive engine.

Wraps Phase 46's LoopOrchestrator with autonomy:
  - Self-generates input (reflection, goal-check, feedback processing)
  - Sleeps when idle, wakes on triggers
  - Monitors own health
  - Respects CL46-01: Loop != Autonomy (no self-goal-setting)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Callable

from ocos.cognitive_loop.loop_orchestrator import LoopOrchestrator
from ocos.cognitive_loop.loop_types import LoopContext, TickOutcome, LoopPhase
from ocos.autonomous_runtime.runtime_config import (
    RuntimeConfig, LoopMode, WakeTrigger, LoopStats,
)


@dataclass
class AutonomousLoop:
    """Self-running OCOS cognitive loop.

    Extends LoopOrchestrator with autonomous operation:
      - Auto-input via reflection generation
      - Sleep/wake cycle
      - Action dispatch integration
      - Safety monitoring
    """

    config: RuntimeConfig = field(default_factory=RuntimeConfig)
    orchestrator: LoopOrchestrator = field(default_factory=LoopOrchestrator)
    stats: LoopStats = field(default_factory=LoopStats)

    # Internal state
    _mode: LoopMode = LoopMode.IDLE
    _sleep_since: Optional[datetime] = None
    _last_action_at: Optional[datetime] = None
    _alert_queue: list[str] = field(default_factory=list)
    _on_action: Optional[Callable] = None  # External action dispatcher hook

    # Reflection memory — what OCOS thinks about between inputs
    _reflection_topics: list[str] = field(default_factory=list)
    _pending_feedback: list[dict] = field(default_factory=list)

    # ── Mode Management ──

    @property
    def mode(self) -> LoopMode:
        return self._mode

    def wake(self, trigger: WakeTrigger, reason: str = "") -> None:
        """Wake OCOS from sleep/idle."""
        old_mode = self._mode
        self._mode = LoopMode.ACTIVE
        self._sleep_since = None
        self.stats.current_mode = "active"
        self.stats.sleep_cycles += 1 if old_mode == LoopMode.SLEEPING else 0

    def sleep(self, reason: str = "") -> None:
        """Enter low-power sleep mode."""
        self._mode = LoopMode.SLEEPING
        self._sleep_since = datetime.now(timezone.utc)
        self.stats.current_mode = "sleeping"

    def idle(self) -> None:
        """Enter idle mode — waiting for input."""
        self._mode = LoopMode.IDLE
        self.stats.current_mode = "idle"

    def reflect(self) -> None:
        """Enter reflection mode — self-review."""
        self._mode = LoopMode.REFLECTING
        self.stats.current_mode = "reflecting"

    # ── Tick with Autonomy ──

    def tick(self, external_input: str = "") -> LoopContext:
        """Execute one autonomous cognitive tick.

        If external_input is provided, it comes from Hermes (the operator).
        If empty, OCOS self-generates reflection input.
        """
        self.stats.total_ticks += 1
        self.stats.ticks_this_session += 1

        # Safety caps
        if self.stats.ticks_this_session > self.config.max_ticks_per_session:
            self._alert_queue.append("SAFETY_CAP: max_ticks_per_session reached")
            self.sleep("safety_cap")
            return LoopContext(tick_id=self.stats.total_ticks)

        # ── Determine input source ──
        input_text = external_input

        if not input_text and self._pending_feedback:
            # Process queued feedback (from OpenTale)
            fb = self._pending_feedback.pop(0)
            input_text = self._format_feedback_input(fb)
            self.wake(WakeTrigger.FEEDBACK_ARRIVED, "processing feedback")

        if not input_text and self._mode == LoopMode.ACTIVE:
            # Self-generate reflection input
            input_text = self._generate_reflection_input()

        if not input_text:
            # Nothing to think about → stay idle / consider sleep
            if self._should_sleep():
                self.sleep("idle_timeout")
            else:
                self.idle()
            return LoopContext(tick_id=self.stats.total_ticks)

        # ── Run cognitive cycle ──
        self._mode = LoopMode.ACTIVE
        self.stats.current_mode = "active"

        ctx = self.orchestrator.tick(perception_input=input_text)

        # ── Track action outcomes for dispatch ──
        if ctx.decision_proposal:
            self._last_action_at = datetime.now(timezone.utc)

        return ctx

    def tick_many(self, count: int = 10, external_inputs: Optional[list[str]] = None) -> list[LoopContext]:
        """Run multiple ticks, optionally with a queue of external inputs."""
        contexts = []
        inputs = list(external_inputs or [])
        for _ in range(count):
            ext = inputs.pop(0) if inputs else ""
            ctx = self.tick(ext)
            contexts.append(ctx)
        return contexts

    # ── Reflection Input Generation ──

    def _generate_reflection_input(self) -> str:
        """Self-generate something to think about.

        OCOS reflects on recent contexts, pending goals, or curiosity topics.
        Does NOT create new goals (CL46-01).
        """
        recent = self.orchestrator.recent_contexts
        if not recent:
            return ""

        # What just happened?
        last_ctx = recent[-1] if recent else None

        parts: list[str] = []

        # 1. Check attention focus
        if self.orchestrator.attention.current:
            parts.append(f"Currently focused on: {self.orchestrator.attention.current}")

        # 2. Check decision pipeline
        if last_ctx and last_ctx.decision_proposal:
            parts.append(f"Last decision pending: {last_ctx.decision_proposal[:100]}")

        # 3. Reflection topics from feedback
        if self._reflection_topics:
            topic = self._reflection_topics.pop(0)
            parts.append(f"Reflecting on: {topic}")

        # 4. Check homeostatic needs (attention decay)
        if self.orchestrator.attention.weight < self.config.min_attention_weight:
            parts.append("Attention weight low — scanning for new focus")

        if not parts:
            return ""

        return " | ".join(parts)

    def _format_feedback_input(self, feedback: dict) -> str:
        """Format OpenTale feedback into OCOS-digestible input."""
        ch = feedback.get("chapter_number", "?")
        quality = feedback.get("quality_score", 0.0)
        issues = feedback.get("issues", [])
        arcs = feedback.get("arcs_advanced", {})

        parts = [
            f"Chapter {ch} feedback received (quality={quality:.2f})",
        ]
        if issues:
            parts.append(f"Issues: {', '.join(issues[:3])}")
        if arcs:
            arc_str = ", ".join(f"{k}={v:.1%}" for k, v in list(arcs.items())[:2])
            parts.append(f"Arc progress: {arc_str}")

        return " | ".join(parts)

    # ── Feedback Queue ──

    def enqueue_feedback(self, feedback: dict) -> None:
        """Queue OpenTale chapter feedback for processing."""
        self._pending_feedback.append(feedback)
        if self.config.wake_on_feedback and self._mode == LoopMode.SLEEPING:
            self.wake(WakeTrigger.FEEDBACK_ARRIVED, f"chapter {feedback.get('chapter_number', '?')}")

    # ── Sleep Logic ──

    def _should_sleep(self) -> bool:
        """Determine if OCOS should enter sleep."""
        if self._mode == LoopMode.SLEEPING:
            return True  # already sleeping
        if self._sleep_since:
            elapsed = (datetime.now(timezone.utc) - self._sleep_since).total_seconds() * 1000
            return elapsed < self.config.sleep_duration_ms
        # Check idle timeout
        last_ctx = self.orchestrator.recent_contexts
        if not last_ctx:
            return False
        return len(self.orchestrator.recent_outcomes) > 0 and             self.orchestrator.recent_outcomes[-1] == TickOutcome.NO_INPUT

    # ── Action Hook ──

    def set_action_handler(self, handler: Callable[[LoopContext], Any]) -> None:
        """Register an external action dispatcher.

        Called after each tick where a decision was made.
        """
        self._on_action = handler

    def dispatch_actions(self, ctx: LoopContext) -> Any:
        """Call the registered action handler if one exists."""
        if self._on_action and ctx.decision_proposal:
            return self._on_action(ctx)
        return None

    # ── Status ──

    def summary(self) -> dict:
        """Comprehensive loop status."""
        loop_summary = self.orchestrator.loop_summary()
        return {
            "mode": self._mode.value,
            "stats": {
                "total_ticks": self.stats.total_ticks,
                "session_ticks": self.stats.ticks_this_session,
                "actions": self.stats.actions_dispatched,
                "chapters": self.stats.open_tale_chapters,
                "sleep_cycles": self.stats.sleep_cycles,
                "alerts": self.stats.health_alerts,
            },
            "cognitive": loop_summary,
            "alerts": list(self._alert_queue[-10:]),
            "pending_feedback": len(self._pending_feedback),
        }

    @property
    def is_healthy(self) -> bool:
        return self.orchestrator.health.is_healthy

    @property
    def alerts(self) -> list[str]:
        return list(self._alert_queue)
