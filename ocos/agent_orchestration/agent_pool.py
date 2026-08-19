"""Phase 62: AgentPool — Agent 并发调度池。

将 Agent 执行从串行提升为并发，支持:
    - 可配置的 max_concurrent 并发数
    - 每任务独立超时（通过 contract.timeout_seconds）
    - 异步 (async) 和同步 (sync) 两种接口
    - 结果聚合: 成功/失败/超时 按任务追踪
    - 单任务失败不阻塞其他任务

架构:
    AutonomousOrchestrator._dispatch_pending()
         │  批量生成 ExecutionContract
         ▼
    AgentPool.execute(tasks) / execute_sync(tasks)
         │  asyncio.Semaphore(N)
         ▼
    AgentExecutor.execute(contract) × N 并行
         │
         ▼
    [(task_id, success, output, error), ...]

用法:
    # 异步
    pool = AgentPool(max_concurrent=4)
    results = await pool.execute(contracts)

    # 同步 (在同步上下文中使用)
    results = pool.execute_sync(contracts)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from ocos.agent_orchestration.contract import ExecutionContract
from ocos.agent_orchestration.executor import AgentExecutor
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── PoolResult ───────────────────────────────────────────────────────────────


@dataclass
class PoolResult:
    """单个任务在池中的执行结果。"""
    task_id: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    timeout: bool = False

    @classmethod
    def timeout_result(cls, task_id: str, timeout_seconds: float):
        """构建超时结果。"""
        return cls(
            task_id=task_id,
            success=False,
            error=f"Timed out after {timeout_seconds:.0f}s",
            elapsed_ms=timeout_seconds * 1000,
            timeout=True,
        )

    @classmethod
    def exception_result(cls, task_id: str, exc: Exception, elapsed_ms: float = 0.0):
        """构建异常结果。"""
        return cls(
            task_id=task_id,
            success=False,
            error=str(exc),
            elapsed_ms=elapsed_ms,
        )


# ── PoolStats ────────────────────────────────────────────────────────────────


@dataclass
class PoolStats:
    """池执行统计。"""
    tasks_submitted: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tasks_timed_out: int = 0
    total_elapsed_ms: float = 0.0
    max_concurrent_reached: bool = False

    @property
    def success_rate(self) -> float:
        if self.tasks_submitted == 0:
            return 1.0
        return self.tasks_succeeded / self.tasks_submitted


# ── AgentPool ────────────────────────────────────────────────────────────────


@dataclass
class AgentPool:
    """Agent 并发调度池。

    控制并发执行的 Agent 数量，管理每个任务的超时和结果收集。

    Attributes:
        max_concurrent: 最大并发任务数 (通过 asyncio.Semaphore 控制)
        executor: AgentExecutor 实例 (默认自动创建)
        execution_timeout: 全局执行超时秒数 (0 表示不限制)
    """

    max_concurrent: int = 3
    executor: Optional[AgentExecutor] = None
    execution_timeout: float = 0.0  # 0 = no global limit

    _stats: PoolStats = field(default_factory=PoolStats)
    _executor_created: bool = False

    def __post_init__(self):
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")

    # ── Public API: Async ────────────────────────────────────────────────

    async def execute(self, contracts: list[ExecutionContract]) -> list[PoolResult]:
        """异步执行一批 Agent 任务。

        Args:
            contracts: ExecutionContract 列表

        Returns:
            PoolResult 列表，顺序与 contracts 一致
        """
        if not contracts:
            return []

        executor = self._get_executor()
        semaphore = asyncio.Semaphore(self.max_concurrent)
        start_time = time.monotonic()

        self._stats.tasks_submitted += len(contracts)
        self._stats.max_concurrent_reached = len(contracts) >= self.max_concurrent

        tasks = [self._run_one(c, executor, semaphore) for c in contracts]

        if self.execution_timeout > 0:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=self.execution_timeout,
            )
        else:
            results = list(await asyncio.gather(*tasks))

        self._stats.total_elapsed_ms += (time.monotonic() - start_time) * 1000
        return results

    def execute_sync(self, contracts: list[ExecutionContract]) -> list[PoolResult]:
        """同步执行一批 Agent 任务。

        在同步上下文中使用 (例如 AutonomousOrchestrator.tick())。
        """
        if not contracts:
            return []

        try:
            asyncio.get_running_loop()
            # 已有事件循环 → 串行执行避免嵌套
            return self._execute_serial(contracts)
        except RuntimeError:
            # 无事件循环 → 通过 asyncio.run() 异步执行
            return asyncio.run(self.execute(contracts))

    # ── Internal ─────────────────────────────────────────────────────────

    async def _run_one(
        self,
        contract: ExecutionContract,
        executor: AgentExecutor,
        semaphore: asyncio.Semaphore,
    ) -> PoolResult:
        """执行单个任务（受 Semaphore 限制）。"""
        async with semaphore:
            task_start = time.monotonic()
            try:
                timeout = contract.timeout_seconds or 60
                success, output, error = await asyncio.wait_for(
                    asyncio.to_thread(executor.execute, contract),
                    timeout=timeout,
                )
                elapsed = (time.monotonic() - task_start) * 1000

                result = PoolResult(
                    task_id=contract.task_id,
                    success=success,
                    output=output or "",
                    error=error,
                    elapsed_ms=elapsed,
                )

                if success:
                    self._stats.tasks_succeeded += 1
                else:
                    self._stats.tasks_failed += 1

                return result

            except asyncio.TimeoutError:
                self._stats.tasks_timed_out += 1
                elapsed = (time.monotonic() - task_start) * 1000
                return PoolResult.timeout_result(
                    contract.task_id,
                    contract.timeout_seconds or 60,
                )
            except Exception as exc:
                self._stats.tasks_failed += 1
                elapsed = (time.monotonic() - task_start) * 1000
                logger.warning(f"Pool execution error for {contract.contract_id}: {exc}")
                return PoolResult.exception_result(contract.contract_id, exc, elapsed)

    def _execute_serial(self, contracts: list[ExecutionContract]) -> list[PoolResult]:
        """串行 fallback（当无法创建事件循环时）。"""
        executor = self._get_executor()
        results = []
        self._stats.tasks_submitted += len(contracts)

        for contract in contracts:
            task_start = time.monotonic()
            try:
                success, output, error = executor.execute(contract)
                elapsed = (time.monotonic() - task_start) * 1000
                result = PoolResult(
                    task_id=contract.task_id,
                    success=success,
                    output=output or "",
                    error=error,
                    elapsed_ms=elapsed,
                )  # serial path
                if success:
                    self._stats.tasks_succeeded += 1
                else:
                    self._stats.tasks_failed += 1
                results.append(result)
            except Exception as exc:
                self._stats.tasks_failed += 1
                results.append(PoolResult.exception_result(
                    contract.task_id, exc,
                    elapsed_ms=(time.monotonic() - task_start) * 1000,
                ))

        return results

    def _get_executor(self) -> AgentExecutor:
        """获取或创建 AgentExecutor。"""
        if self.executor is None:
            self.executor = AgentExecutor()
            self._executor_created = True
        return self.executor

    # ── Stats ────────────────────────────────────────────────────────────

    @property
    def stats(self) -> PoolStats:
        return self._stats

    def reset_stats(self):
        self._stats = PoolStats()
