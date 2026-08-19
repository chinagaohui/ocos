"""Phase 56: RepairExecutor — 修复执行器。

SD56-04: Repair requires Snapshot — 任何修复前必须 checkpoint。

流程:
    1. 验证提案
    2. 创建检查点 (Snapshot)
    3. 执行修复步骤
    4. 验证结果
    5. 提交 或 回滚
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time
import uuid

from ocos.diagnosis.repair_types import (
    RepairProposal, RepairType, RepairStatus, RepairRisk, RepairRecord,
)
from ocos.diagnosis.repair_validator import RepairValidator, ValidationCode


class ExecutorResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass
class ExecutionReport:
    """执行报告。"""
    execution_id: str
    proposal_id: str
    result: ExecutorResult

    checkpoint_id: str = ""
    duration_ms: float = 0.0
    steps_executed: int = 0
    steps_failed: int = 0
    error: str = ""
    rollback_success: bool = False

    @property
    def ok(self) -> bool:
        return self.result == ExecutorResult.SUCCESS


@dataclass
class RepairExecutor:
    """修复执行器。

    SD56-04: 执行前创建快照，失败后回滚。
    """

    validator: RepairValidator = field(default_factory=RepairValidator)

    # 回调 — 由外部注入真实功能
    create_checkpoint: object = None   # Callable[[str], str] -> checkpoint_id
    rollback_checkpoint: object = None # Callable[[str], bool]
    execute_step: object = None        # Callable[[str, dict], bool] — (step, context) -> ok
    finalize: object = None            # Callable[[], bool]

    # 事件回调
    on_complete: object = None         # Callable[[ExecutionReport], None]
    on_repair_record: object = None    # Callable[[RepairRecord], None]

    def execute(self, proposal: RepairProposal) -> ExecutionReport:
        """执行修复。

        SD56-04: 先 checkpoint，再执行。
        """
        exec_id = f"exec-{uuid.uuid4().hex[:10]}"
        t0 = _time.time()

        # 1. 验证
        validation = self.validator.validate(proposal)
        if validation.code == ValidationCode.REJECT:
            elapsed = (_time.time() - t0) * 1000
            return self._report(exec_id, proposal, ExecutorResult.REJECTED,
                                error=validation.reason, duration_ms=elapsed)

        # 2. SD56-04: 创建检查点
        checkpoint_id = ""
        if self.create_checkpoint:
            try:
                checkpoint_id = self.create_checkpoint(proposal.proposal_id)  # type: ignore
            except Exception as e:
                elapsed = (_time.time() - t0) * 1000
                return self._report(exec_id, proposal, ExecutorResult.REJECTED,
                                    error=f"checkpoint failed: {e}",
                                    checkpoint_id="", duration_ms=elapsed)

        # 3. 执行步骤
        steps_done = 0
        steps_failed = 0
        last_error = ""

        for step in proposal.steps:
            try:
                if self.execute_step:
                    ok = self.execute_step(step, {"proposal_id": proposal.proposal_id})  # type: ignore
                    if not ok:
                        steps_failed += 1
                        last_error = f"step failed: {step}"
                        break
                steps_done += 1
            except Exception as e:
                steps_failed += 1
                last_error = f"step error: {step} -> {e}"
                break

        # 4. 验证结果
        if steps_failed > 0:
            # 回滚
            rolled_back = self._rollback(checkpoint_id)
            elapsed = (_time.time() - t0) * 1000
            return self._report(exec_id, proposal, ExecutorResult.ROLLED_BACK,
                                error=last_error,
                                checkpoint_id=checkpoint_id,
                                steps_executed=steps_done,
                                steps_failed=steps_failed,
                                rollback_success=rolled_back,
                                duration_ms=elapsed)

        # 5. 成功 — 提交
        if self.finalize:
            try:
                self.finalize()  # type: ignore
            except Exception:
                pass

        elapsed = (_time.time() - t0) * 1000
        return self._report(exec_id, proposal, ExecutorResult.SUCCESS,
                            checkpoint_id=checkpoint_id,
                            steps_executed=steps_done,
                            duration_ms=elapsed)

    def _rollback(self, checkpoint_id: str) -> bool:
        if self.rollback_checkpoint and checkpoint_id:
            try:
                return self.rollback_checkpoint(checkpoint_id)  # type: ignore
            except Exception:
                return False
        return False

    def _report(self, exec_id: str, proposal: RepairProposal,
                result: ExecutorResult, **kw) -> ExecutionReport:
        report = ExecutionReport(
            execution_id=exec_id,
            proposal_id=proposal.proposal_id,
            result=result,
            **kw,
        )
        if self.on_complete:
            try:
                self.on_complete(report)  # type: ignore
            except Exception:
                pass
        return report


__all__ = ["RepairExecutor", "ExecutionReport", "ExecutorResult"]
