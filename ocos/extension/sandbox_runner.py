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
        """验证扩展：dry-run 隔离 import 探测（GAP-P0-4 前为无条件 passed=True 假成功）。

        仅做 find_spec 探测（不执行模块代码，隔离安全）；真实隔离执行见 P2-6。
        """
        try:
            import importlib.util

            spec = importlib.util.find_spec(candidate_id)
            if spec is None:
                return SandboxResult(
                    candidate_id=candidate_id,
                    passed=False,
                    test_count=1,
                    passed_count=0,
                    behavioral_notes=[f"无法找到模块 '{candidate_id}'（import 探测失败）"],
                    runtime_ticks=0,
                )
            return SandboxResult(
                candidate_id=candidate_id,
                passed=True,
                test_count=1,
                passed_count=1,
                behavioral_notes=[f"模块 '{candidate_id}' 可导入（dry-run import 探测）"],
                runtime_ticks=1,
            )
        except Exception as exc:  # noqa: BLE001 — 探测失败一律诚实报告
            return SandboxResult(
                candidate_id=candidate_id,
                passed=False,
                test_count=1,
                passed_count=0,
                behavioral_notes=[f"import 探测异常: {exc}"],
                runtime_ticks=0,
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
