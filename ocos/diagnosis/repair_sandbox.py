"""Phase 56: RepairSandbox — 修复沙箱。

SD56-04: 修复前必须先验证。

沙箱模式:
    1. 创建隔离环境
    2. 模拟执行修复
    3. 检查前后状态差异
    4. 验证成功标准
    5. 报告结果

沙箱内的操作不会影响生产环境。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time
import uuid


class SandboxResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    INCONCLUSIVE = "inconclusive"


@dataclass
class SandboxReport:
    """沙箱验证报告。"""
    sandbox_id: str
    proposal_id: str
    result: SandboxResult

    # 验证详情
    checks_passed: int = 0
    checks_failed: int = 0
    checks: list[dict] = field(default_factory=list)  # [{name, passed, detail}]

    # 状态快照
    before_state: dict = field(default_factory=dict)
    after_state: dict = field(default_factory=dict)

    # 副作用
    side_effects_detected: list[str] = field(default_factory=list)
    unexpected_changes: bool = False

    duration_ms: float = 0.0

    @property
    def passed(self) -> bool:
        return self.result == SandboxResult.PASS

    @property
    def safe_to_execute(self) -> bool:
        return self.passed and not self.unexpected_changes


@dataclass
class RepairSandbox:
    """修复沙箱。

    SD56-04: 在实际执行之前，先在沙箱中验证修复。
    """

    timeout: float = 30.0  # 沙箱超时

    def validate(self, proposal,
                 before_state: dict | None = None,
                 simulate_fn: callable | None = None) -> SandboxReport:
        """在沙箱中验证修复提案。

        simulate_fn(report: SandboxReport) -> dict: 模拟执行，返回 after_state。
        """
        sandbox_id = f"sand-{uuid.uuid4().hex[:10]}"
        t0 = _time.time()
        report = SandboxReport(
            sandbox_id=sandbox_id,
            proposal_id=proposal.proposal_id,
            result=SandboxResult.INCONCLUSIVE,
            before_state=before_state or {},
        )

        checks = []

        # 1. 类型验证 — 是否允许的修复
        if not proposal.is_allowed:
            checks.append({"name": "type_allowed", "passed": False,
                          "detail": f"forbidden type: {proposal.repair_type}"})
            report.checks = checks
            report.checks_failed = len(checks)
            report.result = SandboxResult.FAIL
            report.duration_ms = (_time.time() - t0) * 1000
            return report
        checks.append({"name": "type_allowed", "passed": True, "detail": "ok"})

        # 2. 步骤验证 — 是否有可执行步骤
        if not proposal.steps:
            checks.append({"name": "has_steps", "passed": False, "detail": "empty steps"})
        else:
            checks.append({"name": "has_steps", "passed": True,
                          "detail": f"{len(proposal.steps)} steps"})

        # 3. 回滚计划 — 不可逆修复必须有回滚
        if not proposal.reversible and not proposal.rollback_plan:
            checks.append({"name": "rollback_plan", "passed": False,
                          "detail": "no rollback plan for irreversible repair"})
        else:
            checks.append({"name": "rollback_plan", "passed": True, "detail": "ok"})

        # 4. 模拟执行 (如果提供了 simulate_fn)
        if simulate_fn:
            try:
                after = simulate_fn(report)
                report.after_state = after
                # 检查关键数据是否还完整
                if "identity" in report.before_state and "identity" in after:
                    if report.before_state["identity"] != after["identity"]:
                        checks.append({"name": "identity_preserved", "passed": False,
                                      "detail": "identity was modified!"})
                        report.side_effects_detected.append("identity modified")
                        report.unexpected_changes = True
                    else:
                        checks.append({"name": "identity_preserved", "passed": True,
                                      "detail": "ok"})
            except Exception as e:
                checks.append({"name": "simulation", "passed": False,
                              "detail": f"simulation failed: {e}"})

        report.checks = checks
        report.checks_passed = sum(1 for c in checks if c["passed"])
        report.checks_failed = len(checks) - report.checks_passed

        if report.checks_failed == 0:
            report.result = SandboxResult.PASS
        else:
            report.result = SandboxResult.FAIL

        elapsed = (_time.time() - t0) * 1000
        if elapsed > self.timeout * 1000:
            report.result = SandboxResult.TIMEOUT

        report.duration_ms = elapsed
        return report


__all__ = ["RepairSandbox", "SandboxReport", "SandboxResult"]
