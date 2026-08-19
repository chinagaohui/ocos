"""Phase 44: CompatibilityChecker — 兼容性验证。

三个维度:
    1. 架构兼容: 是否符合 OCOS 7 层 Runtime 结构
    2. ABI 兼容:    接口类型是否匹配
    3. 治理兼容:    是否违反宪法约束
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.extension.extension_types import (
    ExtensionCandidate, AnalysisReport, ExtensionType,
    CompatibilityReport, ImpactLayer,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 宪法约束 (Constitution)
# ═══════════════════════════════════════════════════════════════════════════════

FORBIDDEN_ACTIONS = [
    "modify_identity",      # 修改 Identity.anchor
    "bypass_permission",    # 绕过 Permission Gateway
    "auto_create_goal",     # 自动创建 Goal
    "direct_execute",       # 直接执行（绕过 Decision）
]

FORBIDDEN_LAYER_ACCESS: dict[ExtensionType, list[ImpactLayer]] = {
    ExtensionType.PERCEPTION: [ImpactLayer.DECISION, ImpactLayer.OUTPUT],
    ExtensionType.MEMORY: [ImpactLayer.INPUT],
    ExtensionType.CAPABILITY: [ImpactLayer.INPUT, ImpactLayer.MEMORY],
}


@dataclass
class CompatibilityChecker:
    """兼容性检查器。"""

    known_abis: dict[str, str] = field(default_factory=dict)  # interface → schema

    def check(
        self,
        candidate: ExtensionCandidate,
        analysis: AnalysisReport,
    ) -> CompatibilityReport:
        issues: list[str] = []
        warnings: list[str] = []

        # 1. 架构兼容性: 检查影响层不越界
        arch_ok = self._check_architecture(candidate, analysis, issues)

        # 2. ABI 兼容性: 声明接口与已知 ABI 匹配
        abi_ok = self._check_abi(candidate, issues, warnings)

        # 3. 治理兼容性: 检查是否违反禁令
        gov_ok = self._check_governance(candidate, issues)

        return CompatibilityReport(
            candidate_id=candidate.candidate_id,
            report_id=f"compat:{candidate.candidate_id}",
            architecture_compatible=arch_ok,
            abi_compatible=abi_ok,
            governance_compatible=gov_ok,
            issues=issues,
            warnings=warnings,
        )

    def _check_architecture(
        self, candidate: ExtensionCandidate, analysis: AnalysisReport, issues: list[str]
    ) -> bool:
        forbidden = FORBIDDEN_LAYER_ACCESS.get(candidate.extension_type, [])
        violations = [l for l in analysis.impact_layers if l in forbidden]
        for v in violations:
            issues.append(f"架构违规: {candidate.extension_type.value} 不能影响 {v.value} 层")
        return len(violations) == 0

    def _check_abi(
        self, candidate: ExtensionCandidate, issues: list[str], warnings: list[str]
    ) -> bool:
        abi_ok = True
        if not candidate.declared_inputs and not candidate.declared_outputs:
            warnings.append("扩展未声明任何输入/输出接口")
        for inp in candidate.declared_inputs:
            if inp not in self.known_abis:
                warnings.append(f"未知输入接口: {inp}")
        return abi_ok

    def _check_governance(
        self, candidate: ExtensionCandidate, issues: list[str]
    ) -> bool:
        gov_ok = True
        # 检查声明中是否包含禁止行为
        combined = (
            candidate.description.lower().replace("_", " ") +
            " " +
            " ".join(v.lower().replace("_", " ") for v in candidate.metadata.values())
        )
        for kw in FORBIDDEN_ACTIONS:
            search = kw.replace("_", " ")
            if search in combined:
                issues.append(f"治理违规: 声称包含 {kw}")
                gov_ok = False
        return gov_ok


__all__ = ["CompatibilityChecker", "FORBIDDEN_ACTIONS", "FORBIDDEN_LAYER_ACCESS"]
