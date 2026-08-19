"""Phase 56: RepairMemory — 修复记忆。

SD56-06: Learning From Repair — 修复结果进入记忆系统。

记录:
    - 修复记录 → RepairRecord
    - 提炼经验 → lesson + pattern
    - 标记是否值得记住 → should_remember

不在本模块中实现真实的 EventMemory/Memory 写入（那是集成层的事），
而是提供记录结构和分类接口，供上层集成。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from collections import deque
import time as _time

from ocos.diagnosis.repair_types import (
    RepairRecord, RepairType, RepairStatus,
)
from ocos.diagnosis.repair_executor import ExecutionReport, ExecutorResult


@dataclass
class RepairMemory:
    """修复记忆库。

    SD56-06: 从修复中学习。

    功能:
        - 存储修复历史
        - 提炼修复模式
        - 查询历史修复
        - 统计修复成功率
    """

    records: deque[RepairRecord] = field(default_factory=deque)
    max_records: int = 500
    on_record: object = None  # Callable[[RepairRecord], None] — 集成到 EventMemory

    def record(self, record: RepairRecord) -> None:
        """记录一次修复。"""
        self.records.append(record)
        while len(self.records) > self.max_records:
            self.records.popleft()

        if self.on_record:
            try:
                self.on_record(record)  # type: ignore
            except Exception:
                pass

    def record_execution(self, proposal,
                         report: ExecutionReport,
                         extract_lesson: bool = True) -> RepairRecord:
        """从执行报告创建修复记录。"""
        record = RepairRecord(
            record_id=f"rrec-{_time.time():.0f}-{len(self.records)}",
            timestamp=_time.time(),
            proposal_id=proposal.proposal_id,
            diagnosis_report_id=proposal.diagnosis_report_id,
            repair_type=proposal.repair_type,
            target_component=proposal.target_component,
            status=self._map_status(report.result),
            duration_ms=report.duration_ms,
            checkpoint_id=report.checkpoint_id,
            was_rolled_back=report.result == ExecutorResult.ROLLED_BACK,
            success=report.result == ExecutorResult.SUCCESS,
            error=report.error,
            side_effects=[],
        )

        # SD56-06: 提取教训
        if extract_lesson:
            record.lesson = self._extract_lesson(record, proposal)
            record.pattern = self._extract_pattern(record)
            record.should_remember = self._should_remember(record)

        self.record(record)
        return record

    def _map_status(self, result: ExecutorResult) -> RepairStatus:
        mapping = {
            ExecutorResult.SUCCESS: RepairStatus.SUCCESS,
            ExecutorResult.FAILED: RepairStatus.FAILED,
            ExecutorResult.ROLLED_BACK: RepairStatus.ROLLED_BACK,
            ExecutorResult.REJECTED: RepairStatus.REJECTED,
        }
        return mapping.get(result, RepairStatus.FAILED)

    def _extract_lesson(self, record: RepairRecord, proposal) -> str:
        """SD56-06: 提炼经验教训。"""
        if record.success:
            return (f"{record.repair_type} 修复 {record.target_component} 成功，"
                    f"耗时 {record.duration_ms:.0f}ms")
        if record.was_rolled_back:
            return (f"{record.repair_type} 修复 {record.target_component} 失败，"
                    f"已安全回滚: {record.error}")
        if record.status == RepairStatus.REJECTED:
            return (f"{record.repair_type} 修复被拒绝: {record.error}")
        return f"{record.repair_type} 修复 {record.target_component} 失败"

    def _extract_pattern(self, record: RepairRecord) -> str:
        """提取修复模式。"""
        if record.success:
            return f"effective_repair:{record.repair_type}:{record.target_component}"
        if record.was_rolled_back:
            return f"rollback_pattern:{record.repair_type}:{record.target_component}"
        return f"failure_pattern:{record.repair_type}:{record.target_component}"

    def _should_remember(self, record: RepairRecord) -> bool:
        """SD56-06: 判断是否值得记住。"""
        # 成功的修复 → 记住 (正面经验)
        if record.success:
            return True
        # 回滚 → 记住 (避免重复错误)
        if record.was_rolled_back:
            return True
        # 关键组件 → 记住
        important = {"memory", "persistence", "event_memory", "self_model"}
        if record.target_component in important:
            return True
        return False

    def query(self, component: str | None = None,
              repair_type: str | None = None,
              successful_only: bool = False) -> list[RepairRecord]:
        """查询历史修复记录。"""
        results = []
        for r in self.records:
            if component and r.target_component != component:
                continue
            if repair_type and str(r.repair_type) != repair_type:
                continue
            if successful_only and not r.success:
                continue
            results.append(r)
        return results

    def stats(self) -> dict:
        """修复统计。"""
        total = len(self.records)
        success = sum(1 for r in self.records if r.success)
        rolled_back = sum(1 for r in self.records if r.was_rolled_back)

        by_component = {}
        for r in self.records:
            c = r.target_component
            if c not in by_component:
                by_component[c] = {"total": 0, "success": 0}
            by_component[c]["total"] += 1
            if r.success:
                by_component[c]["success"] += 1

        return {
            "total_repairs": total,
            "success_rate": success / total if total > 0 else 0.0,
            "failed": total - success - rolled_back,
            "rolled_back": rolled_back,
            "by_component": by_component,
        }

    def clear(self) -> None:
        self.records.clear()


__all__ = ["RepairMemory"]
