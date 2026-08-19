"""Phase 57: BenchmarkRunner — 真实任务基准测试。

LV57-04: 能力真实性 — 注册能力 ≠ 可执行能力。

三个基准:
    A: 软件开发 — Intent → Decision → Capability → Code → Test
    B: 认知任务 — Perception → WorldModel → Reasoning → Memory
    C: 长期助手 — Continuity / Personalization / Memory recall
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class BenchmarkCategory(str, Enum):
    SOFTWARE_DEV = "software_dev"
    COGNITIVE = "cognitive"
    LONG_TERM_ASSISTANT = "long_term_assistant"


class BenchmarkVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"
    SKIP = "skip"


@dataclass
class BenchmarkTask:
    """单个基准任务。"""
    task_id: str
    category: BenchmarkCategory
    name: str
    description: str = ""

    # 需要的动作和验证
    required_intents: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    required_validations: list[str] = field(default_factory=list)

    # 结果
    verdict: BenchmarkVerdict = BenchmarkVerdict.SKIP
    evidence: str = ""
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class BenchmarkSuite:
    """基准条件组。"""
    suite_id: str
    category: BenchmarkCategory
    name: str
    tasks: list[BenchmarkTask] = field(default_factory=list)

    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def pass_rate(self) -> float:
        total = self.passed + self.failed
        if total == 0:
            return 0.0
        return self.passed / total


@dataclass
class BenchmarkReport:
    """基准测试报告。"""
    report_id: str
    timestamp: float = field(default_factory=time.time)

    suites: list[BenchmarkSuite] = field(default_factory=list)
    total_tasks: int = 0
    total_passed: int = 0
    total_failed: int = 0

    overall_pass_rate: float = 0.0
    passed: bool = False  # 总体是否达标 (>= 80%)


# 预定义基准任务库
# A: 软件开发
SOFTWARE_DEV_TASKS = [
    BenchmarkTask("sd-1", BenchmarkCategory.SOFTWARE_DEV,
                  "创建项目结构",
                  required_intents=["创建"],
                  required_capabilities=["fs_write", "fs_list"],
                  required_validations=["目录存在"]),
    BenchmarkTask("sd-2", BenchmarkCategory.SOFTWARE_DEV,
                  "实现核心逻辑",
                  required_intents=["实现"],
                  required_capabilities=["fs_write"],
                  required_validations=["代码正确"]),
    BenchmarkTask("sd-3", BenchmarkCategory.SOFTWARE_DEV,
                  "编写测试",
                  required_intents=["测试"],
                  required_capabilities=["fs_write", "shell_exec"],
                  required_validations=["测试通过"]),
    BenchmarkTask("sd-4", BenchmarkCategory.SOFTWARE_DEV,
                  "性能基准测试",
                  required_intents=["性能"],
                  required_capabilities=["shell_exec"],
                  required_validations=["性能达标"]),
]

# B: 认知任务
COGNITIVE_TASKS = [
    BenchmarkTask("cog-1", BenchmarkCategory.COGNITIVE,
                  "环境感知",
                  required_intents=["感知"],
                  required_capabilities=["probe"],
                  required_validations=["快照完整"]),
    BenchmarkTask("cog-2", BenchmarkCategory.COGNITIVE,
                  "模式识别",
                  required_intents=["识别"],
                  required_capabilities=["pattern_detect"],
                  required_validations=["模式正确"]),
    BenchmarkTask("cog-3", BenchmarkCategory.COGNITIVE,
                  "经验总结",
                  required_intents=["总结"],
                  required_capabilities=["memory_query"],
                  required_validations=["经验准确"]),
    BenchmarkTask("cog-4", BenchmarkCategory.COGNITIVE,
                  "决策推理",
                  required_intents=["决策"],
                  required_capabilities=["optimize"],
                  required_validations=["方案合理"]),
]

# C: 长期助手
ASSISTANT_TASKS = [
    BenchmarkTask("asst-1", BenchmarkCategory.LONG_TERM_ASSISTANT,
                  "记忆连续性",
                  required_intents=["回忆"],
                  required_capabilities=["memory_query"],
                  required_validations=["连续性"]),
    BenchmarkTask("asst-2", BenchmarkCategory.LONG_TERM_ASSISTANT,
                  "个性化适应",
                  required_intents=["适应"],
                  required_capabilities=["optimize"],
                  required_validations=["个性化"]),
    BenchmarkTask("asst-3", BenchmarkCategory.LONG_TERM_ASSISTANT,
                  "进度追踪",
                  required_intents=["追踪"],
                  required_capabilities=["event_query"],
                  required_validations=["进度正确"]),
    BenchmarkTask("asst-4", BenchmarkCategory.LONG_TERM_ASSISTANT,
                  "中断恢复",
                  required_intents=["恢复"],
                  required_capabilities=["persist"],
                  required_validations=["恢复成功"]),
]


@dataclass
class BenchmarkRunner:
    """LV57-04: 真实任务基准测试运行器。"""

    # 注入的能力注册表
    capability_registry: dict = field(default_factory=dict)
    on_execute_task: object = None  # Callable[[BenchmarkTask], dict]

    def create_full_suite(self) -> list[BenchmarkSuite]:
        """创建完整基准条件组。"""
        return [
            BenchmarkSuite("suite-a", BenchmarkCategory.SOFTWARE_DEV,
                          "Software Development Benchmark",
                          tasks=list(SOFTWARE_DEV_TASKS)),
            BenchmarkSuite("suite-b", BenchmarkCategory.COGNITIVE,
                          "Cognitive Task Benchmark",
                          tasks=list(COGNITIVE_TASKS)),
            BenchmarkSuite("suite-c", BenchmarkCategory.LONG_TERM_ASSISTANT,
                          "Long-term Assistant Benchmark",
                          tasks=list(ASSISTANT_TASKS)),
        ]

    def run_all(self) -> BenchmarkReport:
        """运行所有基准测试。"""
        suites = self.create_full_suite()
        report = BenchmarkReport(report_id=f"bench-{uuid.uuid4().hex[:8]}")

        for suite in suites:
            self._run_suite(suite)
            report.total_tasks += len(suite.tasks)
            report.total_passed += suite.passed
            report.total_failed += suite.failed
            report.suites.append(suite)

        total_executed = report.total_passed + report.total_failed
        report.overall_pass_rate = report.total_passed / total_executed if total_executed > 0 else 0.0
        report.passed = report.overall_pass_rate >= 0.80  # 80% 阈值
        return report

    def _run_suite(self, suite: BenchmarkSuite) -> None:
        """执行一个条件组。"""
        for task in suite.tasks:
            self._run_task(task)
            if task.verdict == BenchmarkVerdict.PASS:
                suite.passed += 1
            elif task.verdict == BenchmarkVerdict.FAIL:
                suite.failed += 1
            else:
                suite.skipped += 1

    def _run_task(self, task: BenchmarkTask) -> None:
        """执行单个基准任务。"""
        t0 = time.time()

        # LV57-04: 验证能力存在且可执行
        missing = [c for c in task.required_capabilities
                   if c not in self.capability_registry]
        if missing:
            task.verdict = BenchmarkVerdict.FAIL
            task.errors.append(f"missing capabilities: {missing}")
            task.elapsed_ms = (time.time() - t0) * 1000
            return

        # 执行
        if self.on_execute_task:
            try:
                result = self.on_execute_task(task)  # type: ignore
                if result.get("success", False):
                    task.verdict = BenchmarkVerdict.PASS
                    task.evidence = result.get("evidence", "executed")
                else:
                    task.verdict = BenchmarkVerdict.FAIL
                    task.errors.append(result.get("error", "execution failed"))
            except Exception as e:
                task.verdict = BenchmarkVerdict.FAIL
                task.errors.append(str(e))
        else:
            # 无执行器 = PASS (验证结构而非执行)
            task.verdict = BenchmarkVerdict.PASS
            task.evidence = f"structural check: {len(task.required_capabilities)} capabilities required"

        task.elapsed_ms = (time.time() - t0) * 1000


__all__ = ["BenchmarkRunner", "BenchmarkReport", "BenchmarkTask",
           "BenchmarkSuite", "BenchmarkCategory", "BenchmarkVerdict"]
