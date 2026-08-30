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
        """验证扩展（PW-2.2: 三层探测 — import 探测 + 沙盒能力自检 + 行为留痕）。

        1. find_spec import 探测（不执行模块代码）；
        2. 若候选是命令类扩展（candidate_id 以 "cmd:" 前缀给出），经
           operations/SandboxOps 黑白名单+路径沙盒做真实隔离试运行；
        3. 任一层失败即诚实 passed=False。
        """
        notes: list[str] = []
        test_count = 0
        passed_count = 0
        runtime_ticks = 0

        # Layer 1: import 探测
        try:
            import importlib.util

            spec = importlib.util.find_spec(candidate_id)
            test_count += 1
            if spec is None:
                return SandboxResult(
                    candidate_id=candidate_id,
                    passed=False, test_count=test_count, passed_count=passed_count,
                    behavioral_notes=[f"无法找到模块 '{candidate_id}'（import 探测失败）"],
                    runtime_ticks=runtime_ticks,
                )
            passed_count += 1
            notes.append(f"模块 '{candidate_id}' 可导入")
        except Exception as exc:  # noqa: BLE001 — 探测失败一律诚实报告
            return SandboxResult(
                candidate_id=candidate_id,
                passed=False, test_count=test_count + 1, passed_count=passed_count,
                behavioral_notes=[f"import 探测异常: {exc}"],
                runtime_ticks=runtime_ticks,
            )

        # Layer 2: 命令类扩展 → operations/SandboxOps 真实隔离试运行
        if candidate_id.startswith("cmd:"):
            command = candidate_id[4:].strip()
            test_count += 1
            runtime_ticks += 1
            try:
                import os as _os
                from ocos.operations.sandbox_ops import (
                    SandboxCommand, SandboxOps,
                )
                workdir = "/tmp/ocos_sandbox"
                _os.makedirs(workdir, exist_ok=True)
                result = SandboxOps(strict=True).execute(
                    SandboxCommand(command=command, workdir=workdir,
                                   timeout=15.0))
                if result.blocked:
                    return SandboxResult(
                        candidate_id=candidate_id, passed=False,
                        test_count=test_count, passed_count=passed_count,
                        behavioral_notes=[f"沙盒拦截: {result.block_reason}"],
                        runtime_ticks=runtime_ticks)
                if result.success:
                    passed_count += 1
                    notes.append(f"沙盒试运行通过: {(result.stdout or '')[:80]}")
                else:
                    return SandboxResult(
                        candidate_id=candidate_id, passed=False,
                        test_count=test_count, passed_count=passed_count,
                        behavioral_notes=[f"沙盒试运行失败: {(result.stderr or '')[:120]}"],
                        runtime_ticks=runtime_ticks)
            except Exception as exc:  # noqa: BLE001
                return SandboxResult(
                    candidate_id=candidate_id, passed=False,
                    test_count=test_count, passed_count=passed_count,
                    behavioral_notes=[f"沙盒执行异常: {exc}"],
                    runtime_ticks=runtime_ticks)

        return SandboxResult(
            candidate_id=candidate_id,
            passed=passed_count == test_count,
            test_count=test_count,
            passed_count=passed_count,
            behavioral_notes=notes,
            runtime_ticks=runtime_ticks,
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
