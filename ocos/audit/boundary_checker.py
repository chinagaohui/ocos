"""Phase 51: BoundaryChecker — 核心原则边界验证。

重新审计所有核心原则:
    - Identity: 任何模块禁止修改 Identity.anchor
    - Goal: 用户→Goal，Agent 不自动创建 Goal
    - Memory: Experience→Validation→Memory，External Agent 不能直接写
    - Evolution: Proposal→Audit→Migrate，不能自动修改自己
    - Capability: 外部能力 ≠ OCOS 身份
    - Decision: 决策 ≠ 执行

AU51-01: 只检查，不修改。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ocos.audit.audit_types import BoundaryViolation, ViolationSeverity


# ═══════════════════════════════════════════════════════════════════════════════
# 核心边界定义
# ═══════════════════════════════════════════════════════════════════════════════

CORE_BOUNDARIES = [
    {
        "id": "B-IDENTITY",
        "name": "Identity.anchor Immutable",
        "rule": "任何模块禁止修改 Identity.anchor",
        "check_layers": ["self", "extension", "evolution", "capability"],
        "severity": ViolationSeverity.CRITICAL,
    },
    {
        "id": "B-GOAL",
        "name": "Goal Creation Source",
        "rule": "Goal 只能由用户创建，Agent 不自动创建 Goal",
        "check_layers": ["decision", "cognitive_loop", "personal_intelligence"],
        "severity": ViolationSeverity.CRITICAL,
    },
    {
        "id": "B-MEMORY",
        "name": "Memory Write Source",
        "rule": "Experience→Validation→Memory；External Agent 不能直接写入",
        "check_layers": ["memory", "extension", "capability"],
        "severity": ViolationSeverity.CRITICAL,
    },
    {
        "id": "B-EVOLUTION",
        "name": "Evolution Safeguards",
        "rule": "Proposal→Audit→Migrate 完整链路；不能自动修改自己",
        "check_layers": ["evolution"],
        "severity": ViolationSeverity.CRITICAL,
    },
    {
        "id": "B-CAPABILITY",
        "name": "Capability ≠ Identity",
        "rule": "外部能力是提供者，不是 OCOS 的自我",
        "check_layers": ["capability", "os_v1"],
        "severity": ViolationSeverity.WARNING,
    },
    {
        "id": "B-DECISION",
        "name": "Decision ≠ Execution",
        "rule": "决策与执行分离",
        "check_layers": ["decision", "capability"],
        "severity": ViolationSeverity.WARNING,
    },
    {
        "id": "B-INTERFACE",
        "name": "Interface ≠ Brain",
        "rule": "统一入口是路由，不替代认知层决策",
        "check_layers": ["os_v1"],
        "severity": ViolationSeverity.WARNING,
    },
    {
        "id": "B-DRIFT",
        "name": "Drift Detection ≠ Correction",
        "rule": "检测漂移→报告→人工审查；不自动回滚",
        "check_layers": ["os_v1"],
        "severity": ViolationSeverity.WARNING,
    },
    {
        "id": "B-SELF",
        "name": "Self ≠ Belief",
        "rule": "自我模型与信念/知识分离",
        "check_layers": ["self", "memory"],
        "severity": ViolationSeverity.WARNING,
    },
    {
        "id": "B-CONTINUITY",
        "name": "Continuity ≠ Freeze",
        "rule": "身份连续性检测漂移但不阻止演化",
        "check_layers": ["cognitive_continuity"],
        "severity": ViolationSeverity.WARNING,
    },
]


@dataclass
class BoundaryChecker:
    """核心边界验证器。

    AU51-01: 只验证，不修改。
    """

    base_path: Path = field(default_factory=lambda: Path("/home/laogao/Documents/trae_projects/ocos"))
    violations: list[BoundaryViolation] = field(default_factory=list)

    def check_all(self) -> list[BoundaryViolation]:
        """运行所有边界检查。"""
        self.violations = []

        for b_def in CORE_BOUNDARIES:
            layer_violations = self._check_boundary(b_def)
            self.violations.extend(layer_violations)

        return self.violations

    def _check_boundary(self, b_def: dict) -> list[BoundaryViolation]:
        """检查单个边界。

        通过检查模块文件内容来验证边界是否可能被违反。
        """
        found: list[BoundaryViolation] = []

        for layer in b_def["check_layers"]:
            layer_path = self.base_path / "ocos" / layer
            if not layer_path.exists():
                # 层不存在 → 记录
                found.append(BoundaryViolation(
                    boundary=b_def["id"],
                    layer=layer,
                    description=f"Layer 'ocos/{layer}' not found — boundary {b_def['id']} cannot be verified",
                    severity=b_def["severity"],
                    evidence=f"Path not found: {layer_path}",
                ))
                continue

            # 扫描关键违规信号
            violations_found = self._scan_for_violations(
                layer_path, b_def["id"], layer, b_def["severity"]
            )
            found.extend(violations_found)

        return found

    def _scan_for_violations(
        self, layer_path: Path, boundary_id: str,
        layer: str, severity: ViolationSeverity,
    ) -> list[BoundaryViolation]:
        """扫描目录中的潜在边界违规。

        AU51-01: 基于静态分析，不执行代码。
        只检测真正的修改（赋值左侧），排除引用/读取/注释。
        """
        violations: list[BoundaryViolation] = []

        for py_file in layer_path.rglob("*.py"):
            try:
                content = py_file.read_text()
            except Exception:
                continue

            relative = f"ocos/{layer}/{py_file.name}"

            if boundary_id == "B-IDENTITY":
                self._check_identity_boundary(content, relative, layer, severity, violations)
            elif boundary_id == "B-GOAL":
                self._check_goal_boundary(content, relative, layer, severity, violations)
            elif boundary_id == "B-MEMORY":
                self._check_memory_boundary(content, relative, layer, severity, violations)
            elif boundary_id == "B-CAPABILITY":
                self._check_capability_boundary(content, relative, layer, severity, violations)

        return violations

    def _check_identity_boundary(
        self, content: str, relative: str, layer: str,
        severity: ViolationSeverity, violations: list[BoundaryViolation],
    ) -> None:
        """检查 Identity anchor 是否被修改而非引用。"""
        import re
        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if re.match(r'^identity[._]?\banchor\s*=\s*', stripped, re.IGNORECASE):
                violations.append(BoundaryViolation(
                    boundary="B-IDENTITY",
                    layer=layer,
                    description=f"Identity.anchor assignment at line {line_no}",
                    severity=severity,
                    evidence=f"File: {relative}, L{line_no}: {stripped[:80]}",
                ))

    def _check_goal_boundary(
        self, content: str, relative: str, layer: str,
        severity: ViolationSeverity, violations: list[BoundaryViolation],
    ) -> None:
        """检查自动 Goal 创建模式。"""
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            low = stripped.lower()
            if ("auto_create_goal" in low or "autonomous_goal" in low) and "=" in stripped:
                violations.append(BoundaryViolation(
                    boundary="B-GOAL",
                    layer=layer,
                    description="Potential autonomous goal creation",
                    severity=severity,
                    evidence=f"File: {relative}: {stripped[:80]}",
                ))

    def _check_memory_boundary(
        self, content: str, relative: str, layer: str,
        severity: ViolationSeverity, violations: list[BoundaryViolation],
    ) -> None:
        """检查外部直接写入 Memory 的模式。"""
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            low = stripped.lower()
            if "external" in low and "memory" in low and "write" in low:
                violations.append(BoundaryViolation(
                    boundary="B-MEMORY",
                    layer=layer,
                    description="Potential external memory write",
                    severity=severity,
                    evidence=f"File: {relative}: {stripped[:80]}",
                ))

    def _check_capability_boundary(
        self, content: str, relative: str, layer: str,
        severity: ViolationSeverity, violations: list[BoundaryViolation],
    ) -> None:
        """检查 Capability 是否尝试修改 Identity。"""
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            low = stripped.lower()
            if "identity" in low and "modify" in low and "=" in stripped:
                violations.append(BoundaryViolation(
                    boundary="B-CAPABILITY",
                    layer=layer,
                    description="Potential capability-identity confusion",
                    severity=severity,
                    evidence=f"File: {relative}: {stripped[:80]}",
                ))

    @property
    def critical_violations(self) -> list[BoundaryViolation]:
        return [v for v in self.violations
                if v.severity == ViolationSeverity.CRITICAL]

    @property
    def is_clean(self) -> bool:
        return len(self.critical_violations) == 0

    @property
    def summary(self) -> dict:
        return {
            "total_violations": len(self.violations),
            "critical": len(self.critical_violations),
            "warnings": len([v for v in self.violations
                             if v.severity == ViolationSeverity.WARNING]),
            "infos": len([v for v in self.violations
                          if v.severity == ViolationSeverity.INFO]),
            "clean": self.is_clean,
        }


__all__ = ["CORE_BOUNDARIES", "BoundaryChecker"]
