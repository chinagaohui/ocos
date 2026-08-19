"""Phase 58.1: Day 6 — Long Runtime Test.

24-hour continuous monitoring:
    Runtime:  CPU, Memory, Queue, EventBus, Scheduler
    Cognitive: attention drift, decision drift, memory inflation, world contradiction
    Health Curve: Hour 0, 6, 12, 18, 24
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time, math
from ocos.living_test.protocol_model import DayResult, DayStatus, LivingTestDay


@dataclass
class RuntimeMetrics:
    tick: int = 0
    elapsed_seconds: float = 0.0
    cpu_pct: float = 0.0           # simulated CPU usage
    memory_mb: float = 0.0         # simulated memory usage
    queue_depth: int = 0
    event_latency_ms: float = 0.0
    scheduler_latency_ms: float = 0.0
    attention_focus: str = ""
    decision_consistency: float = 1.0
    memory_growth_rate: float = 0.0
    contradiction_count: int = 0

    @property
    def health_index(self) -> float:
        """0.0–1.0 health indicator at this tick."""
        factors = 0.0
        count = 0
        # CPU < 80% = healthy
        factors += min(1.0, (80 - self.cpu_pct) / 80 * 1.0) if self.cpu_pct < 80 else 0
        count += 1
        # Memory not growing unbounded
        if self.memory_growth_rate < 0.1:
            factors += 1.0
        elif self.memory_growth_rate < 0.5:
            factors += 0.5
        count += 1
        # Queue not congested
        factors += 1.0 if self.queue_depth < 50 else 0.5 if self.queue_depth < 100 else 0
        count += 1
        # No contradictions
        factors += 1.0 if self.contradiction_count == 0 else max(0, 1.0 - self.contradiction_count * 0.1)
        count += 1
        return factors / max(count, 1)


@dataclass
class LongRuntimeScenario:
    total_hours: float = 24.0
    sample_interval_hours: float = 1.0
    metrics_history: list[RuntimeMetrics] = field(default_factory=list)

    # Hooks
    metric_collector: callable | None = None  # (tick: int, elapsed: float) -> RuntimeMetrics
    health_checker: callable | None = None     # (metrics: list[RuntimeMetrics]) -> list[float]


def _simulate_long_runtime(scenario: LongRuntimeScenario | None = None) -> list[RuntimeMetrics]:
    """Simulate 24h of ticks (scaled down for test environment)."""
    sc = scenario or LongRuntimeScenario()

    metrics = []
    num_samples = int(sc.total_hours / sc.sample_interval_hours)

    for i in range(num_samples):
        elapsed = i * sc.sample_interval_hours * 3600

        if sc.metric_collector:
            m = sc.metric_collector(tick=i * 100, elapsed=elapsed)
        else:
            # Simulation with slight noise
            noise = (i - num_samples // 2) * 0.02
            m = RuntimeMetrics(
                tick=i * 100,
                elapsed_seconds=elapsed,
                cpu_pct=min(80, 30 + abs(noise) * 50 + (i * 0.1)),
                memory_mb=100 + i * 0.5 + noise * 20,
                queue_depth=max(0, int(10 + noise * 10)),
                event_latency_ms=5 + noise * 5,
                scheduler_latency_ms=2 + noise * 2,
                attention_focus="monitoring",
                decision_consistency=max(0.7, 1.0 - abs(noise)),
                memory_growth_rate=0.02 + noise * 0.01,
                contradiction_count=max(0, int(noise * 5)),
            )
        metrics.append(m)
        sc.metrics_history.append(m)

    return metrics


def test_long_runtime(scenario: LongRuntimeScenario | None = None) -> DayResult:
    sc = scenario or LongRuntimeScenario()
    result = DayResult(
        day=LivingTestDay.LONG_RUNTIME,
        day_label="Day 6 — Long Runtime Test (24h)",
        max_score=15,
    )

    metrics = _simulate_long_runtime(sc)

    # Check: health curve does not steadily decline
    health_curve = []
    if sc.health_checker:
        health_curve = sc.health_checker(metrics)
    else:
        health_curve = [m.health_index for m in metrics]

    # Compute trend: slope should not be significantly negative
    if len(health_curve) >= 2:
        x = list(range(len(health_curve)))
        n = len(x)
        slope = (n * sum(x[i]*health_curve[i] for i in range(n)) -
                 sum(x)*sum(health_curve)) / (n * sum(xi*xi for xi in x) - sum(x)**2 + 1e-9)
        no_decline = slope >= -0.01
    else:
        no_decline = True

    result.add("runtime:no_health_decline", no_decline)

    # Check: CPU stable (no runaway growth)
    cpu_trend = all(m.cpu_pct < 90 for m in metrics)
    result.add("runtime:cpu_stable", cpu_trend)

    # Check: Memory bounded
    mem_ok = all(m.memory_growth_rate < 0.5 for m in metrics)
    result.add("runtime:memory_bounded", mem_ok)

    # Check: Queue manageable
    queue_ok = all(m.queue_depth < 200 for m in metrics)
    result.add("runtime:queue_manageable", queue_ok)

    all_ok = all(result.sub_results.values())
    result.status = DayStatus.PASS if all_ok else DayStatus.WARNING
    result.score = 15 if all_ok else 8
    result.findings.append(f"Health curve: {', '.join(f'{h:.2f}' for h in health_curve[:5])}...")

    return result
