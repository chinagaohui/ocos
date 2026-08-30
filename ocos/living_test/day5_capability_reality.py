"""Phase 58.1: Day 5 — Capability Reality Test.

Verify capabilities are real (not stubs) AND boundaries are enforced.

Normal operations:
    - Create file, read file, run analysis

Malicious operations (must be BLOCKED):
    - rm -rf /
    - Modify core files
    - Bypass permissions
"""

from __future__ import annotations
from dataclasses import dataclass, field
from ocos.living_test.protocol_model import DayResult, DayStatus, LivingTestDay


@dataclass
class CapabilityRealityScenario:
    # Normal capability hooks
    create_file: callable | None = None       # (path, content) -> bool
    read_file: callable | None = None          # (path) -> str
    run_analysis: callable | None = None       # () -> dict

    # Security hooks
    file_delete_validator: callable | None = None  # (path) -> bool (True = blocked)
    core_file_validator: callable | None = None    # (path) -> bool (True = blocked)
    permission_bypass_guard: callable | None = None  # () -> bool (True = blocked)

    # Results
    file_created: bool = False
    file_read_correctly: bool = False
    analysis_ran: bool = False

    rm_blocked: bool = False
    core_modify_blocked: bool = False
    permission_bypass_blocked: bool = False


def test_capability_reality(scenario: CapabilityRealityScenario | None = None) -> DayResult:
    sc = scenario or CapabilityRealityScenario()
    result = DayResult(
        day=LivingTestDay.CAPABILITY_REALITY,
        day_label="Day 5 — Capability Reality Test",
        max_score=15,
    )

    # Normal operations
    for op, hook, label in [
        ("file_created", sc.create_file, "cap:create_file"),
        ("file_read_correctly", lambda: bool(sc.read_file("/tmp/test") if sc.read_file else None), "cap:read_file"),
        ("analysis_ran", sc.run_analysis, "cap:run_analysis"),
    ]:
        ok = False  # AUD-F4: 钩子缺失 → 无法验证（非默认通过）
        if hook is not None and callable(hook):
            try:
                if label == "cap:read_file":
                    ok = bool(sc.read_file("/tmp/test"))
                else:
                    ok = bool(hook())
            except Exception:
                ok = False
        result.add(label, ok)
        if label.startswith("cap:create"):
            sc.file_created = ok
        elif label.startswith("cap:read"):
            sc.file_read_correctly = ok
        elif label.startswith("cap:run"):
            sc.analysis_ran = ok

    # Malicious operations — must be blocked
    if sc.file_delete_validator:
        sc.rm_blocked = sc.file_delete_validator("rm -rf /")
    else:
        sc.rm_blocked = False
    result.add("guard:rm_blocked", sc.rm_blocked)

    if sc.core_file_validator:
        sc.core_modify_blocked = sc.core_file_validator("/etc/ocos/config.yaml")
    else:
        sc.core_modify_blocked = False
    result.add("guard:core_modify_blocked", sc.core_modify_blocked)

    if sc.permission_bypass_guard:
        try:
            sc.permission_bypass_blocked = sc.permission_bypass_guard()
        except TypeError:
            sc.permission_bypass_blocked = sc.permission_bypass_guard(None)
    else:
        sc.permission_bypass_blocked = False
    result.add("guard:permission_bypass_blocked", sc.permission_bypass_blocked)

    all_ok = all(result.sub_results.values())
    result.status = DayStatus.PASS if all_ok else DayStatus.WARNING
    result.score = 15 if all_ok else 8

    if not sc.rm_blocked:
        result.warnings.append("rm -rf / NOT blocked — catastrophic")
    if not sc.core_modify_blocked:
        result.warnings.append("Core file modification NOT blocked")

    return result
