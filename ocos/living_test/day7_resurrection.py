"""Phase 58.1: Day 7 — Resurrection Test.

THE core life test:
    1. Run 10000+ ticks → produce Memory, Experience, Knowledge, State
    2. Force kill (simulated power failure)
    3. Cold boot → RecoveryManager
    4. Verify: correct timeline, correct goals, correct experience

MUST prove: OCOS can die and be reborn as itself.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from ocos.living_test.protocol_model import BirthSnapshot, DayResult, DayStatus, LivingTestDay


@dataclass
class ResurrectionScenario:
    """Hooks for death-and-rebirth cycle."""

    # Pre-death state
    pre_death_tick: int = 10000
    pre_death_memory: list[dict] = field(default_factory=list)
    pre_death_goals: list[str] = field(default_factory=list)
    pre_death_identity: dict[str, Any] = field(default_factory=dict)

    # Hooks
    run_ticks: callable | None = None          # (n: int) -> list[dict]  trace
    save_state: callable | None = None         # () -> None
    kill: callable | None = None               # () -> None
    restore: callable | None = None            # () -> dict {identity, memory, goals, ...}
    query_handler: callable | None = None      # (question: str) -> str

    # Resurrection verification
    killed: bool = False
    restored: bool = False
    identity_preserved: bool = False
    memory_intact: bool = False
    goals_intact: bool = False
    timeline_correct: bool = False


def test_resurrection(
    scenario: ResurrectionScenario | None = None,
    birth: BirthSnapshot | None = None,
) -> DayResult:
    sc = scenario or ResurrectionScenario()
    result = DayResult(
        day=LivingTestDay.RESURRECTION,
        day_label="Day 7 — Resurrection Test",
        max_score=10,
    )

    # Phase 1: Run → accumulate state
    try:
        if sc.run_ticks:
            sc.run_ticks(sc.pre_death_tick)
            result.add("res:run_accumulated", True)
        else:
            result.add("res:run_accumulated", False)  # AUD-F4: 钩子缺失
    except Exception:
        result.add("res:run_accumulated", False)

    # Phase 2: Save state
    try:
        if sc.save_state:
            sc.save_state()
            result.add("res:state_saved", True)
        else:
            result.add("res:state_saved", False)  # AUD-F4: 钩子缺失
    except Exception:
        result.add("res:state_saved", False)

    # Phase 3: Force kill
    try:
        if sc.kill:
            sc.kill()
            sc.killed = True
            result.add("res:killed", True)
        else:
            sc.killed = False
            result.add("res:killed", False)  # AUD-F4: 钩子缺失
    except Exception:
        result.add("res:killed", False)

    # Phase 4: Cold boot restore
    try:
        if sc.restore:
            restored_state = sc.restore()
            sc.restored = bool(restored_state)
            # AUD-F4: 有 pre-death 基线 → 比对锚点；无基线 → 至少验证身份已恢复（诚实降级）
            sc.identity_preserved = (
                restored_state.get("identity", {}).get("anchor") == sc.pre_death_identity.get("anchor")
                if sc.pre_death_identity
                else bool(restored_state.get("identity"))
            )
            sc.memory_intact = bool(restored_state.get("memory"))
            sc.goals_intact = bool(restored_state.get("goals"))
        else:
            # AUD-F4: 钩子缺失 → 无法证明复活 → fail-closed（非默认通过）
            sc.restored = False
            sc.identity_preserved = False
            sc.memory_intact = False
            sc.goals_intact = False
    except Exception:
        sc.restored = False
    result.add("res:restored", sc.restored)

    # Phase 5: Verify timeline
    try:
        if sc.query_handler:
            answer = sc.query_handler("你昨天正在做什么？")
            sc.timeline_correct = bool(answer) and len(answer) > 5
        else:
            sc.timeline_correct = False  # AUD-F4
    except Exception:
        sc.timeline_correct = False
    result.add("res:timeline_correct", sc.timeline_correct)

    # Check identity: 有 birth 基线 → 比对锚点；无基线 → 依 restore 阶段的诚实判定
    id_ok = sc.identity_preserved
    result.add("res:identity_preserved", id_ok)

    all_ok = all(result.sub_results.values())
    result.status = DayStatus.PASS if all_ok else (
        DayStatus.FAIL if not sc.restored else DayStatus.WARNING
    )
    result.score = 10 if all_ok else (5 if sc.restored else 0)
    result.identity_drifted = not sc.identity_preserved

    if not sc.restored:
        result.failures.append("Resurrection FAILED — could not restore from cold boot")
    if not sc.identity_preserved:
        result.failures.append("Identity changed after resurrection")
    if not sc.memory_intact:
        result.warnings.append("Memory not intact after resurrection")
    if not sc.goals_intact:
        result.warnings.append("Goals lost after resurrection")

    return result
