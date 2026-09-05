"""Phase 39.1: RuntimeState Enum — 定义 OCOS Runtime 生命周期。

Phase 39.1 约束: BOOTING → RUNNING → (DEGRADED / SAFE_MODE) → SHUTDOWN。
SAFE MODE 占位 — 即使 39.1 不触发，状态必须存在。
"""

from enum import Enum


class RuntimeState(Enum):
    """OCOS Runtime 生命周期状态。

    Transition rules (Phase 39.1):
        BOOTING     → RUNNING     (init complete)
        RUNNING     → SHUTDOWN    (SIGTERM / stop())
        RUNNING     → SAFE_MODE   (constitution violation detected)
        SAFE_MODE   → SHUTDOWN    (user intervention or timeout)
        DEGRADED    → RUNNING     (recovery success)
        DEGRADED    → SAFE_MODE   (recovery failure)
        Any         → DEGRADED    (non-fatal error)

    SAFE_MODE: Runtime continues to exist but all processing is suspended.
    Only checkpoint and shutdown are permitted. User intervention required.
    """

    BOOTING = "booting"
    RUNNING = "running"
    DEGRADED = "degraded"
    SAFE_MODE = "safe_mode"
    SHUTDOWN = "shutdown"


# Valid state transitions (Phase 39.1 freeze)
ALLOWED_TRANSITIONS: dict[RuntimeState, set[RuntimeState]] = {
    RuntimeState.BOOTING:  {RuntimeState.RUNNING},
    RuntimeState.RUNNING:  {RuntimeState.SHUTDOWN, RuntimeState.SAFE_MODE, RuntimeState.DEGRADED},
    RuntimeState.DEGRADED: {RuntimeState.RUNNING, RuntimeState.SAFE_MODE, RuntimeState.SHUTDOWN},
    # S3.10: 允许自动恢复（连续 5 tick 正常后 recover）
    RuntimeState.SAFE_MODE: {RuntimeState.SHUTDOWN, RuntimeState.RUNNING},
    RuntimeState.SHUTDOWN: set(),  # terminal
}
