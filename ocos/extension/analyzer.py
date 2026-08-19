"""Phase 44: Analyzer — 扩展分析器。

理解扩展是什么: 类型、影响层、接口、风险。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import (
    ExtensionCandidate, ExtensionType, ImpactLayer,
    AnalysisReport,
)


@dataclass
class Analyzer:
    """分析引擎 — 理解扩展的性质。

    对每个 ExtensionCandidate 生成 AnalysisReport。
    """

    _report_counter: int = field(default=0, init=False)

    def analyze(self, candidate: ExtensionCandidate) -> AnalysisReport:
        self._report_counter += 1
        return AnalysisReport(
            candidate_id=candidate.candidate_id,
            analysis_id=f"analysis:{self._report_counter}",
            extension_type=candidate.extension_type,
            summary=self._summarize(candidate),
            impact_layers=self._infer_impact(candidate),
            input_schema="dynamic",  # 简化: 实际需从模块反射
            output_schema="dynamic",
            dependencies=[],
            risks_identified=self._identify_risks(candidate),
            confidence=0.7,
        )

    def _summarize(self, c: ExtensionCandidate) -> str:
        type_map = {
            ExtensionType.PERCEPTION: "感知扩展 — 增加输入通道",
            ExtensionType.MEMORY: "记忆扩展 — 增加存储后端",
            ExtensionType.REASONING: "推理扩展 — 增加推理引擎",
            ExtensionType.CAPABILITY: "能力扩展 — 增加执行能力",
            ExtensionType.COMMUNICATION: "通信扩展 — 增加输出通道",
            ExtensionType.KNOWLEDGE: "知识扩展 — 增加领域模型",
            ExtensionType.META: "元扩展 — 监控/治理组件",
        }
        return f"{c.name}: {type_map.get(c.extension_type, '未知类型')}"

    def _infer_impact(self, c: ExtensionCandidate) -> list[ImpactLayer]:
        """推断扩展影响的认知层。"""
        mapping = {
            ExtensionType.PERCEPTION: [ImpactLayer.INPUT],
            ExtensionType.MEMORY: [ImpactLayer.MEMORY],
            ExtensionType.REASONING: [ImpactLayer.PROCESSING],
            ExtensionType.CAPABILITY: [ImpactLayer.OUTPUT],
            ExtensionType.COMMUNICATION: [ImpactLayer.OUTPUT],
            ExtensionType.KNOWLEDGE: [ImpactLayer.MEMORY, ImpactLayer.PROCESSING],
            ExtensionType.META: [ImpactLayer.META],
        }
        return mapping.get(c.extension_type, [ImpactLayer.META])

    def _identify_risks(self, c: ExtensionCandidate) -> list[str]:
        risks: list[str] = []
        if c.extension_type == ExtensionType.CAPABILITY:
            risks.append("能力扩展可能绕过权限控制")
        if c.extension_type == ExtensionType.MEMORY:
            risks.append("记忆扩展可能写入错误数据")
        if c.extension_type == ExtensionType.PERCEPTION:
            risks.append("感知扩展可能注入错误输入")
        return risks


__all__ = ["Analyzer"]
