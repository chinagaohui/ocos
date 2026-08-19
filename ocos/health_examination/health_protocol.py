"""Phase 58.0: HealthProtocol — 统一健康检查协议执行器。

编排五大体检器并生成最终健康报告。
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
import json

from ocos.health_examination.health_model import (
    HealthCategory, HealthCertification,
)
from ocos.health_examination.structural_examiner import StructuralExaminer
from ocos.health_examination.connectivity_examiner import ConnectivityExaminer
from ocos.health_examination.cognitive_examiner import (
    CognitiveExaminer, MemorySnapshot, DecisionSnapshot, WorldSnapshot,
)
from ocos.health_examination.immune_examiner import ImmuneExaminer
from ocos.health_examination.runtime_examiner import RuntimeExaminer
from ocos.health_examination.recovery_examiner import RecoveryExaminer
from ocos.health_examination.health_scorer import HealthScorer


@dataclass
class HealthProtocolReport:
    """健康检查协议完整报告。"""
    certification: HealthCertification | None = None
    structural_score: dict | None = None
    connectivity_score: dict | None = None
    cognitive_score: dict | None = None
    immune_score: dict | None = None
    runtime_score: dict | None = None
    recovery_result: dict | None = None
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        def to_dict_or_none(v):
            if hasattr(v, "__dict__"):
                return v.__dict__
            return v

        return {
            "certification": to_dict_or_none(self.certification),
            "structural": self.structural_score,
            "connectivity": self.connectivity_score,
            "cognitive": self.cognitive_score,
            "immune": self.immune_score,
            "runtime": self.runtime_score,
            "recovery": self.recovery_result,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str, ensure_ascii=False)


@dataclass
class HealthProtocol:
    """OCOS 健康检查协议执行器。

    执行顺序: 结构 → 连接 → 认知 → 免疫 → 运行恢复 → 评分
    """

    # 五大体检器
    structural: StructuralExaminer = field(default_factory=StructuralExaminer)
    connectivity: ConnectivityExaminer = field(default_factory=ConnectivityExaminer)
    cognitive: CognitiveExaminer = field(default_factory=CognitiveExaminer)
    immune: ImmuneExaminer = field(default_factory=ImmuneExaminer)
    runtime: RuntimeExaminer = field(default_factory=RuntimeExaminer)
    recovery: RecoveryExaminer = field(default_factory=RecoveryExaminer)
    scorer: HealthScorer = field(default_factory=HealthScorer)

    def execute(self,
                sim_engine=None,
                memory_snap: MemorySnapshot | None = None,
                decision_snap: DecisionSnapshot | None = None,
                attention_goals: list[str] | None = None,
                attention_context: str = "",
                world_snap: WorldSnapshot | None = None,
                ) -> HealthProtocolReport:
        """执行完整健康检查协议。"""
        report = HealthProtocolReport()

        # 1. 结构体检
        struct = self.structural.examine()
        report.structural_score = {
            "score": struct.raw_score,
            "normalized": struct.normalized,
            "details": struct.details,
            "warnings": struct.warnings,
        }

        # 2. 连接体检
        conn = self.connectivity.examine()
        report.connectivity_score = {
            "score": conn.raw_score,
            "normalized": conn.normalized,
            "details": conn.details,
            "warnings": conn.warnings,
        }

        # 3. 认知体检
        cog = self.cognitive.full_examination(
            memory=memory_snap,
            decision=decision_snap,
            attention_goals=attention_goals,
            attention_context=attention_context,
            world=world_snap,
        )
        report.cognitive_score = {
            "score": cog.raw_score,
            "normalized": cog.normalized,
            "details": cog.details,
            "warnings": cog.warnings,
        }

        # 4. 免疫体检
        imm = self.immune.full_examination()
        report.immune_score = {
            "score": imm.raw_score,
            "normalized": imm.normalized,
            "details": imm.details,
            "warnings": imm.warnings,
        }

        # 5. 运行 + 恢复体检
        rt = self.runtime.examine(sim_engine=sim_engine)
        report.runtime_score = {
            "score": rt.raw_score,
            "normalized": rt.normalized,
            "details": rt.details,
            "warnings": rt.warnings,
        }

        # 恢复测试 (计入 Runtime)
        rec = self.recovery.full_examination()
        report.recovery_result = {
            "recovered": rec.normalized,
            "details": rec.details,
        }

        # 6. 评分
        cert = self.scorer.score({
            HealthCategory.STRUCTURAL.value: struct,
            HealthCategory.CONNECTIVITY.value: conn,
            HealthCategory.COGNITIVE.value: cog,
            HealthCategory.IMMUNE.value: imm,
            HealthCategory.RUNTIME.value: rt,
        })
        report.certification = cert

        return report


def quick_health_check(protocol: HealthProtocol | None = None) -> HealthCertification:
    """快速健康检查：只运行结构+连接+免疫（快速层）。"""
    if protocol is None:
        protocol = HealthProtocol()

    struct = protocol.structural.examine()
    conn = protocol.connectivity.examine()
    imm = protocol.immune.full_examination()

    return protocol.scorer.score({
        HealthCategory.STRUCTURAL.value: struct,
        HealthCategory.CONNECTIVITY.value: conn,
        HealthCategory.IMMUNE.value: imm,
    })


__all__ = ["HealthProtocol", "HealthProtocolReport", "quick_health_check"]
