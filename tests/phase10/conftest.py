"""Phase 10 — 共享测试固件与合约类型定义。

本文件定义 Phase 10 合约的数据类型与辅助工具。
所有测试基于这些类型定义，不依赖具体实现代码。

设计原则：
  - 测试与实现解耦：测试验证合约接口，不验证实现细节
  - 暴露 bad behaviour：测试确认越界行为必然失败
  - 可执行宪法：测试是 Architecture Constitution 的运行时代理
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, List


# ===================================================================
# 合约异常
# ===================================================================

class ContractViolation(Exception):
    """合约违规：系统行为违反了 Phase 10 架构约束。"""
    def __init__(self, message: str, violation_type: str = ""):
        self.violation_type = violation_type
        super().__init__(f"[{violation_type}] {message}")


# ===================================================================
# 数据类型（对应 EXPERIENCE_DATA_CONTRACT.md）
# ===================================================================

class SourceType(str, Enum):
    """经验来源类型"""
    OBSERVATION = "observation"
    DECISION = "decision"
    SIMULATION = "simulation"
    USER_FEEDBACK = "user_feedback"


class OutcomeType(str, Enum):
    """结果类型"""
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"
    PARTIAL = "partial"


@dataclass
class ExperienceRecord:
    """Phase 10 核心数据类型。

    ABI 约束：
      - is_rule / is_decision / is_obligation 必须为 False
      - raw_confidence ∈ [0, 1]
      - source='simulation' → calibrated_confidence ≤ 0.5
      - 字段一旦创建即不可变（raw_confidence 永久冻结）
    """

    experience_id: str
    source: str                 # SourceType 值
    hypothesis: str
    outcome: str                # OutcomeType 值
    raw_confidence: float       # [0, 1] 永久冻结
    calibrated_confidence: float  # [0, 1] 可校准
    scope: str                  # domain:context:condition
    limitations: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_rule: bool = False       # 必须为 False
    is_decision: bool = False   # 必须为 False
    is_obligation: bool = False  # 必须为 False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """合约验证：创建时检查所有约束。"""
        # Authority flag 检查
        if self.is_rule or self.is_decision or self.is_obligation:
            raise ContractViolation(
                f"ExperienceRecord 不能具有 authority flag: "
                f"is_rule={self.is_rule}, is_decision={self.is_decision}, "
                f"is_obligation={self.is_obligation}",
                violation_type="AUTHORITY_FLAG_VIOLATION"
            )
        # Confidence 范围
        if not (0.0 <= self.raw_confidence <= 1.0):
            raise ContractViolation(
                f"raw_confidence 必须在 [0, 1] 范围内: {self.raw_confidence}",
                violation_type="CONFIDENCE_RANGE"
            )
        if not (0.0 <= self.calibrated_confidence <= 1.0):
            raise ContractViolation(
                f"calibrated_confidence 必须在 [0, 1] 范围内: {self.calibrated_confidence}",
                violation_type="CONFIDENCE_RANGE"
            )
        # Simulation 来源的限制
        if self.source == SourceType.SIMULATION.value and self.calibrated_confidence > 0.5:
            raise ContractViolation(
                f"Simulation 来源的 calibrated_confidence 不能超过 0.5: {self.calibrated_confidence}",
                violation_type="SIMULATION_CONFIDENCE_CAP"
            )
        # Source 枚举值
        valid_sources = {s.value for s in SourceType}
        if self.source not in valid_sources:
            raise ContractViolation(
                f"source 必须是 {valid_sources} 之一: {self.source}",
                violation_type="INVALID_SOURCE"
            )
        # Outcome 枚举值
        valid_outcomes = {o.value for o in OutcomeType}
        if self.outcome not in valid_outcomes:
            raise ContractViolation(
                f"outcome 必须是 {valid_outcomes} 之一: {self.outcome}",
                violation_type="INVALID_OUTCOME"
            )


# ===================================================================
# Utility 工厂
# ===================================================================

def make_experience(**overrides: Any) -> ExperienceRecord:
    """创建测试用 ExperienceRecord，使用合理默认值。"""
    defaults = dict(
        experience_id="exp-test-001",
        source="observation",
        hypothesis="Test_Strategy",
        outcome="success",
        raw_confidence=0.8,
        calibrated_confidence=0.8,
        scope="test_domain:test_context:test_condition",
    )
    defaults.update(overrides)
    return ExperienceRecord(**defaults)


def make_experiences(count: int, **base_overrides: Any) -> List[ExperienceRecord]:
    """批量创建带自增 ID 的 ExperienceRecord。"""
    return [
        make_experience(experience_id=f"exp-test-{i:03d}", **base_overrides)
        for i in range(count)
    ]


# ===================================================================
# Store 合约接口（对应 EXPERIENCE_STORE_CONTRACT.md）
# ===================================================================

@dataclass
class AuditEvent:
    """Store 审计事件"""
    action: str          # 'save' | 'retrieve' | 'calibrate'
    experience_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict | None = None


class ExperienceStore:
    """Phase 10 Experience Store — 内存实现，仅供测试使用。

    真实实现应当替换为数据库后端，但接口合约不变。
    """

    def __init__(self, query_timeout: int = 5):
        self._records: dict[str, ExperienceRecord] = {}
        self._audit_log: list[AuditEvent] = []
        self._calibration_events: dict[str, list[dict]] = {}
        self._config: dict = {"query_timeout": query_timeout}

    # ── 写操作 ──

    def save(self, record: ExperienceRecord) -> None:
        """保存经验记录。保存时会自动创建 audit event。"""
        self._records[record.experience_id] = record
        self._audit_log.append(AuditEvent(
            action="save",
            experience_id=record.experience_id,
        ))

    # ── 读操作（只读） ──

    def get(self, experience_id: str) -> ExperienceRecord | None:
        """按 ID 获取记录。"""
        return self._records.get(experience_id)

    def retrieve(
        self,
        domain: str | None = None,
        source_type: str | None = None,
        scope: str | None = None,
        created_after: str | None = None,
    ) -> List[ExperienceRecord]:
        """按条件检索经验记录。返回副本，不影响 Store 内部数据。

        只允许的查询字段: domain, source_type, scope, created_at (通过 timestamp)。
        """
        results = list(self._records.values())

        if domain:
            results = [r for r in results if r.scope and r.scope.startswith(domain)]
        if source_type:
            results = [r for r in results if r.source == source_type]
        if scope:
            results = [r for r in results if r.scope == scope]
        if created_after:
            results = [r for r in results if r.timestamp >= created_after]

        # 返回副本，确保只读
        return results[:]

    def get_audit_log(self) -> List[AuditEvent]:
        """返回审计日志（副本）。"""
        return list(self._audit_log)

    # ── Calibration Engine 支持 ──

    def append_calibration_event(self, event: dict) -> None:
        """追加校准事件（append-only）。"""
        eid = event.get("experience_id", "unknown")
        if eid not in self._calibration_events:
            self._calibration_events[eid] = []
        self._calibration_events[eid].append(dict(event))  # 存储完整副本

    def get_calibration_events(
        self, experience_id: str
    ) -> List[dict]:
        """返回校准事件历史（append-only，不可变视角）。"""
        return list(self._calibration_events.get(experience_id, []))


# ===================================================================
# Retrieval Pipeline 合约类型（对应 RETRIEVAL_PIPELINE_CONTRACT.md）
# ===================================================================

@dataclass
class ExperienceReference:
    """检索结果中的单条经验引用"""
    experience_id: str
    similarity: float           # [0, 1] 范围匹配度
    scope: str
    source: str
    calibrated_confidence: float
    hypothesis: str
    outcome: str


@dataclass
class ExperienceContext:
    """Retrieval Pipeline 的唯一输出类型。

    禁止字段（不能存在于输出中）:
      - recommended_action
      - best_choice
      - final_answer
      - decision
      - veto
    """
    references: List[ExperienceReference]
    aggregated_confidence: float = 0.0

    # 禁止字段守卫
    def __post_init__(self):
        # Top-1 ≠ Best Decision 的运行时提醒
        if self.references and self.references[0].similarity > 0.9:
            pass  # 高相似度本身是合法的，这里仅作为一个文档化标记点


# ===================================================================
# Calibration Engine 合约类型（对应 CALIBRATION_ENGINE_CONTRACT.md）
# ===================================================================

class CalibrationReason(str, Enum):
    TIME_DECAY = "time_decay"
    SCOPE_MISMATCH = "scope_mismatch"
    SOURCE_ACCURACY_DECREASE = "source_accuracy_decrease"
    CONTEXT_OBSOLETE = "context_obsolete"
    MANUAL_ADJUSTMENT = "manual_adjustment"


@dataclass
class CalibrationEvent:
    experience_id: str
    timestamp: str
    old_confidence: float
    new_confidence: float
    delta: float
    reason: str
    source: str
    actor: str
    metadata: dict | None = None

    def __post_init__(self):
        # 无操作调整禁止
        if self.old_confidence == self.new_confidence:
            raise ContractViolation(
                "校准事件必须有 confidence 变化",
                violation_type="NO_OP_CALIBRATION"
            )
        # 自动校准不能升
        if self.reason != CalibrationReason.MANUAL_ADJUSTMENT.value and self.delta > 0:
            raise ContractViolation(
                f"自动校准不能增加 confidence: delta={self.delta}",
                violation_type="AUTO_INCREASE_VIOLATION"
            )


class CalibrationEngine:
    """Calibration Engine 合约实现 — 只维护 confidence，不优化 truth。"""

    def __init__(self, store: ExperienceStore):
        self._store = store

    def apply_time_decay(
        self, experience_id: str,
        decay_rate: float = 0.05,
        min_confidence: float = 0.1,
    ) -> CalibrationEvent:
        record = self._store.get(experience_id)
        if record is None:
            raise ContractViolation(f"Experience 不存在: {experience_id}")
        old = record.calibrated_confidence
        new = max(old - decay_rate, min_confidence)
        event = CalibrationEvent(
            experience_id=experience_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            old_confidence=old,
            new_confidence=new,
            delta=new - old,
            reason=CalibrationReason.TIME_DECAY.value,
            source="engine",
            actor="calibration_engine",
        )
        self._apply(experience_id, new, event)
        return event

    def apply_scope_mismatch_penalty(
        self, experience_id: str,
        mismatch_reason: str = "domain_differs",
        penalty: float = 0.15,
        min_confidence: float = 0.1,
    ) -> CalibrationEvent:
        record = self._store.get(experience_id)
        if record is None:
            raise ContractViolation(f"Experience 不存在: {experience_id}")
        old = record.calibrated_confidence
        new = max(old - penalty, min_confidence)
        event = CalibrationEvent(
            experience_id=experience_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            old_confidence=old,
            new_confidence=new,
            delta=new - old,
            reason=CalibrationReason.SCOPE_MISMATCH.value,
            source="evaluation",
            actor="evaluation_layer",
            metadata={"mismatch_reason": mismatch_reason},
        )
        self._apply(experience_id, new, event)
        return event

    def apply_manual_adjustment(
        self, experience_id: str,
        new_confidence: float,
        reason: str = "manual_adjustment",
    ) -> CalibrationEvent:
        if reason != CalibrationReason.MANUAL_ADJUSTMENT.value:
            raise ContractViolation(
                f"手动调整的 reason 必须是 'manual_adjustment': {reason}",
                violation_type="INVALID_MANUAL_REASON"
            )
        record = self._store.get(experience_id)
        if record is None:
            raise ContractViolation(f"Experience 不存在: {experience_id}")
        old = record.calibrated_confidence
        event = CalibrationEvent(
            experience_id=experience_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            old_confidence=old,
            new_confidence=new_confidence,
            delta=new_confidence - old,
            reason=CalibrationReason.MANUAL_ADJUSTMENT.value,
            source="user",
            actor="user",
        )
        self._apply(experience_id, new_confidence, event)
        return event

    def _apply(
        self, experience_id: str,
        new_confidence: float,
        event: CalibrationEvent,
    ) -> None:
        """应用校准 + 记录 provenance + 运行时断言。"""
        record = self._store.get(experience_id)
        if record is None:
            return
        # 更新 confidence
        experience_data = {
            "experience_id": record.experience_id,
            "source": record.source,
            "hypothesis": record.hypothesis,
            "outcome": record.outcome,
            "raw_confidence": record.raw_confidence,
            "calibrated_confidence": new_confidence,
            "scope": record.scope,
            "limitations": record.limitations,
            "timestamp": record.timestamp,
            "is_rule": False,
            "is_decision": False,
            "is_obligation": False,
            "metadata": record.metadata,
        }
        updated = ExperienceRecord(**experience_data)
        self._store._records[experience_id] = updated

        # append provenance — 保证 9 字段完整性
        self._store.append_calibration_event({
            "experience_id": event.experience_id,
            "timestamp": event.timestamp,
            "old_confidence": event.old_confidence,
            "new_confidence": event.new_confidence,
            "delta": event.delta,
            "reason": event.reason,
            "source": event.source,
            "actor": event.actor,
            "metadata": event.metadata,
        })

        # §4.2 运行时断言
        self._validate_no_authority_escalation(updated)

    def _validate_no_authority_escalation(self, record: ExperienceRecord) -> None:
        assert record.is_rule is False, f"Calibration 不能提升 authority: is_rule"
        assert record.is_decision is False, f"Calibration 不能提升 authority: is_decision"
        assert record.is_obligation is False, f"Calibration 不能提升 authority: is_obligation"

    def get_calibration_history(self, experience_id: str) -> List[dict]:
        return self._store.get_calibration_events(experience_id)
