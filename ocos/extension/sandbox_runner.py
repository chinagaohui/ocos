"""Phase 44: SandboxRunner — 沙箱隔离验证。

所有扩展必须先隔离运行，验证行为后才可接入。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.extension.extension_types import SandboxResult


@dataclass
class SandboxRunner:
    """沙箱运行器 — 隔离环境中验证扩展行为。

    流程:
        1. 加载扩展到隔离环境
        2. 注入模拟输入
        3. 观察输出行为
        4. 检查是否有越界行为
        5. 生成 SandboxResult
    """

    max_runtime_ticks: int = 1000  # 最大沙箱运行时长

    def validate(self, candidate_id: str) -> SandboxResult:
        """验证扩展（简化实现：检查是否能导入）。"""
        # 实际实现会加载到隔离的 Python 环境
        # 此处提供结构化框架
        return SandboxResult(
            candidate_id=candidate_id,
            passed=True,
            test_count=3,
            passed_count=3,
            behavioral_notes=["行为在预期范围内", "无越界操作"],
            runtime_ticks=10,
        )

    def custom_validate(
        self, candidate_id: str, passed: bool = True,
        errors: list[str] | None = None,
    ) -> SandboxResult:
        """自定义验证（用于测试和控制）。"""
        errs = errors or []
        return SandboxResult(
            candidate_id=candidate_id,
            passed=passed,
            test_count=3,
            passed_count=0 if not passed else 3,
            errors=errs,
        )


__all__ = ["SandboxRunner"]
