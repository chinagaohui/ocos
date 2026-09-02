"""Phase AB: DistributedCognitionManager — 多实例分布式认知管理器。

整合 AgentPool + AgentCollaboration + 分布式协调机制，
支持：
- 多实例认知任务分发
- 状态同步与一致性保障
- 故障转移与冗余
- 跨实例知识共享

架构原则：
- AB-DIST-01: 实例独立运行，通过协调层通信
- AB-DIST-02: 任务可跨实例负载均衡
- AB-DIST-03: 状态变更通过事件日志同步
- AB-DIST-04: 支持水平扩展（动态添加/移除实例）
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from ocos.logging import get_logger

logger = get_logger(__name__)


class InstanceState(Enum):
    """实例状态。"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"
    OFFLINE = "offline"
    FAILED = "failed"


class TaskDistributionStrategy(Enum):
    """任务分发策略。"""
    ROUND_ROBIN = "round_robin"           # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    WEIGHTED = "weighted"                 # 加权
    AFFINITY = "affinity"                 # 亲和性


@dataclass
class CognitionInstance:
    """认知实例信息。"""
    instance_id: str
    host: str
    port: int
    state: InstanceState = InstanceState.INITIALIZING
    created_at: float = 0.0
    last_heartbeat: float = 0.0
    task_count: int = 0
    failed_tasks: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.time()

    @property
    def is_healthy(self) -> bool:
        """实例是否健康（最近5秒有心跳）。"""
        return (
            self.state in (InstanceState.RUNNING, InstanceState.IDLE, InstanceState.BUSY)
            and time.time() - self.last_heartbeat < 5.0
        )


@dataclass
class DistributedTask:
    """分布式任务。"""
    task_id: str
    source_instance: str
    target_instance: str
    task_type: str
    payload: dict[str, Any]
    status: str = "pending"
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    retries: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def is_complete(self) -> bool:
        return self.status in ("completed", "failed")

    @property
    def should_retry(self) -> bool:
        return self.retries < self.max_retries


class DistributedCognitionManager:
    """分布式认知管理器。

    管理多个OCOS实例的协同工作，提供：
    1. 实例注册与发现
    2. 任务分发与负载均衡
    3. 状态同步
    4. 故障转移
    """

    def __init__(
        self,
        strategy: TaskDistributionStrategy = TaskDistributionStrategy.LEAST_CONNECTIONS,
        heartbeat_interval: float = 2.0,
        failover_timeout: float = 10.0,
        max_instances: int = 10,
    ):
        self._strategy = strategy
        self._heartbeat_interval = heartbeat_interval
        self._failover_timeout = failover_timeout
        self._max_instances = max_instances
        
        # 实例管理
        self._instances: dict[str, CognitionInstance] = {}
        self._local_instance_id: str = ""
        self._instance_lock = threading.RLock()
        
        # 任务管理
        self._pending_tasks: list[DistributedTask] = []
        self._active_tasks: dict[str, DistributedTask] = {}
        self._task_lock = threading.RLock()
        
        # 统计
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "instance_joins": 0,
            "instance_leaves": 0,
        }
        
        # 回调
        self._on_task_complete: list[Callable] = []
        self._on_instance_event: list[Callable] = []

    # ── 实例管理 ────────────────────────────────────────────────

    def register_instance(
        self,
        instance_id: str,
        host: str,
        port: int,
        metadata: dict[str, Any] | None = None,
    ) -> CognitionInstance | None:
        """注册新的认知实例。"""
        with self._instance_lock:
            # 检查实例数量限制
            if len(self._instances) >= self._max_instances:
                logger.warning("Max instances reached (%d)", self._max_instances)
                return None
            
            # 检查是否已注册
            if instance_id in self._instances:
                return self._instances[instance_id]
            
            # 创建实例
            instance = CognitionInstance(
                instance_id=instance_id,
                host=host,
                port=port,
                state=InstanceState.INITIALIZING,
                metadata=metadata or {},
            )
            self._instances[instance_id] = instance
            
            self._stats["instance_joins"] += 1
            logger.info("Instance registered: %s (%s:%d)", instance_id, host, port)
            
            self._notify_instance_event("registered", instance)
            return instance

    def deregister_instance(self, instance_id: str) -> bool:
        """注销认知实例。"""
        with self._instance_lock:
            instance = self._instances.pop(instance_id, None)
            if instance:
                instance.state = InstanceState.OFFLINE
                self._stats["instance_leaves"] += 1
                logger.info("Instance deregistered: %s", instance_id)
                self._notify_instance_event("deregistered", instance)
                
                # 转移该实例的任务
                self._reassign_tasks(instance_id)
                return True
            return False

    def update_heartbeat(self, instance_id: str) -> bool:
        """更新实例心跳。"""
        with self._instance_lock:
            instance = self._instances.get(instance_id)
            if instance:
                instance.last_heartbeat = time.time()
                if instance.state == InstanceState.INITIALIZING:
                    instance.state = InstanceState.RUNNING
                return True
            return False

    def get_instance(self, instance_id: str) -> CognitionInstance | None:
        """获取实例信息。"""
        with self._instance_lock:
            return self._instances.get(instance_id)

    def list_instances(self, state: InstanceState | None = None) -> list[CognitionInstance]:
        """列出实例，可按状态过滤。"""
        with self._instance_lock:
            instances = list(self._instances.values())
            if state:
                instances = [i for i in instances if i.state == state]
            return instances

    def get_healthy_instances(self) -> list[CognitionInstance]:
        """获取健康实例列表。"""
        with self._instance_lock:
            return [i for i in self._instances.values() if i.is_healthy]

    # ── 任务分发 ────────────────────────────────────────────────

    def submit_task(
        self,
        task_type: str,
        payload: dict[str, Any],
        source_instance: str | None = None,
    ) -> DistributedTask:
        """提交任务到分布式队列。"""
        task_id = f"task:{uuid.uuid4().hex[:8]}"
        source = source_instance or self._local_instance_id
        
        task = DistributedTask(
            task_id=task_id,
            source_instance=source,
            target_instance="",
            task_type=task_type,
            payload=payload,
        )
        
        with self._task_lock:
            self._pending_tasks.append(task)
            self._stats["tasks_submitted"] += 1
        
        logger.debug("Task submitted: %s (type=%s, source=%s)", task_id, task_type, source)
        return task

    def dispatch_task(self, task: DistributedTask) -> bool:
        """将任务分发给目标实例。"""
        with self._task_lock:
            if task not in self._pending_tasks:
                # 如果不在 pending 中但存在，检查是否在 active
                if task.task_id in self._active_tasks:
                    return False
                logger.warning("Task %s not in pending list", task.task_id)
                return False

            target = self._select_target(task)
            if not target:
                logger.warning("No available instance for task %s", task.task_id)
                return False

            task.target_instance = target.instance_id
            task.status = "dispatched"
            task.started_at = time.time()

            # 从待处理移到活跃
            self._pending_tasks.remove(task)
            self._active_tasks[task.task_id] = task

            # 更新实例计数
            with self._instance_lock:
                if target.instance_id in self._instances:
                    self._instances[target.instance_id].task_count += 1
                    self._instances[target.instance_id].state = InstanceState.BUSY

            logger.debug("Task dispatched: %s -> %s", task.task_id, target.instance_id)
            return True

    def complete_task(self, task_id: str, result: dict[str, Any]) -> bool:
        """标记任务完成。"""
        with self._task_lock:
            task = self._active_tasks.get(task_id)
            if not task:
                return False
            
            task.status = "completed"
            task.result = result
            task.completed_at = time.time()
            
            # 更新实例计数
            with self._instance_lock:
                if task.target_instance in self._instances:
                    self._instances[task.target_instance].task_count -= 1
                    if self._instances[task.target_instance].task_count == 0:
                        self._instances[task.target_instance].state = InstanceState.IDLE
            
            del self._active_tasks[task_id]
            self._stats["tasks_completed"] += 1
            
            logger.debug("Task completed: %s", task_id)
            
            # 通知回调
            for cb in self._on_task_complete:
                try:
                    cb(task)
                except Exception as e:
                    logger.warning("Task complete callback failed: %s", e)
            
            return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """标记任务失败。"""
        with self._task_lock:
            task = self._active_tasks.get(task_id)
            if not task:
                return False

            task.error = error
            task.completed_at = time.time()

            # 更新实例计数
            with self._instance_lock:
                if task.target_instance in self._instances:
                    self._instances[task.target_instance].task_count -= 1
                    self._instances[task.target_instance].failed_tasks += 1
                    if self._instances[task.target_instance].task_count == 0:
                        self._instances[task.target_instance].state = InstanceState.IDLE

            # 尝试重试或标记失败
            # retries 记录已重试次数，max_retries 为最大允许重试次数
            task.retries += 1
            if task.retries >= task.max_retries:
                # 已达最大重试，永久失败
                del self._active_tasks[task_id]
                task.status = "failed"
                self._stats["tasks_failed"] += 1
                logger.error("Task %s failed permanently: %s", task_id, error)
            else:
                # 还可以继续重试
                task.status = "pending"
                task.target_instance = ""
                task.started_at = 0.0
                self._pending_tasks.append(task)
                self._stats["tasks_retried"] += 1
                logger.warning("Task %s failed, retry %d/%d: %s",
                             task_id, task.retries, task.max_retries, error)

        return True

    # ── 故障转移 ────────────────────────────────────────────────

    def handle_instance_failure(self, instance_id: str) -> list[DistributedTask]:
        """处理实例故障，转移其活跃任务。"""
        with self._instance_lock:
            instance = self._instances.get(instance_id)
            if not instance:
                return []
            
            instance.state = InstanceState.FAILED
            logger.error("Instance failed: %s", instance_id)
        
        # 转移任务
        with self._task_lock:
            reassignable = [
                t for t in self._active_tasks.values()
                if t.target_instance == instance_id
            ]
            
            for task in reassignable:
                task.status = "pending"
                task.target_instance = ""
                task.started_at = 0.0
                self._pending_tasks.append(task)
                del self._active_tasks[task.task_id]
                logger.warning("Reassigning task %s from failed instance %s", 
                             task.task_id, instance_id)
            
            # 清理失败实例
            self._instances.pop(instance_id, None)
            self._stats["instance_leaves"] += 1
        
        return reassignable

    def check_health(self) -> list[str]:
        """检查所有实例健康状态，返回问题实例ID列表。"""
        unhealthy = []
        now = time.time()
        
        with self._instance_lock:
            for instance_id, instance in self._instances.items():
                if instance.is_healthy:
                    continue
                
                # 检查是否超时
                if now - instance.last_heartbeat > self._failover_timeout:
                    logger.warning("Instance %s heartbeat timeout", instance_id)
                    unhealthy.append(instance_id)
        
        # 处理不健康实例
        for instance_id in unhealthy:
            self.handle_instance_failure(instance_id)
        
        return unhealthy

    # ── 内部方法 ────────────────────────────────────────────────

    def _select_target(self, task: DistributedTask) -> CognitionInstance | None:
        """根据策略选择目标实例。"""
        healthy = self.get_healthy_instances()
        if not healthy:
            return None
        
        if self._strategy == TaskDistributionStrategy.ROUND_ROBIN:
            return self._round_robin_select(healthy)
        elif self._strategy == TaskDistributionStrategy.LEAST_CONNECTIONS:
            return min(healthy, key=lambda i: i.task_count)
        elif self._strategy == TaskDistributionStrategy.WEIGHTED:
            return self._weighted_select(healthy, task)
        elif self._strategy == TaskDistributionStrategy.AFFINITY:
            return self._affinity_select(healthy, task)
        else:
            return healthy[0]

    def _round_robin_select(self, instances: list[CognitionInstance]) -> CognitionInstance:
        """轮询选择。"""
        # 简化实现：返回第一个（实际应维护计数器）
        return instances[0]

    def _weighted_select(self, instances: list[CognitionInstance], task: DistributedTask) -> CognitionInstance:
        """加权选择（基于实例负载）。"""
        # 简化实现：返回负载最低的
        return min(instances, key=lambda i: i.task_count)

    def _affinity_select(self, instances: list[CognitionInstance], task: DistributedTask) -> CognitionInstance:
        """亲和性选择（基于任务类型）。"""
        # 简化实现：返回第一个
        return instances[0]

    def _reassign_tasks(self, instance_id: str) -> None:
        """重新分配指定实例的任务。"""
        with self._task_lock:
            reassignable = [
                t for t in self._active_tasks.values()
                if t.target_instance == instance_id
            ]
            for task in reassignable:
                task.status = "pending"
                task.target_instance = ""
                task.started_at = 0.0
                self._pending_tasks.append(task)
            for task in reassignable:
                del self._active_tasks[task.task_id]

    def _notify_instance_event(self, event: str, instance: CognitionInstance) -> None:
        """通知实例事件。"""
        for cb in self._on_instance_event:
            try:
                cb(event, instance)
            except Exception as e:
                logger.warning("Instance event callback failed: %s", e)

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._instance_lock:
            instance_count = len(self._instances)
            healthy_count = sum(1 for i in self._instances.values() if i.is_healthy)
        
        with self._task_lock:
            pending_count = len(self._pending_tasks)
            active_count = len(self._active_tasks)
        
        return {
            **self._stats,
            "instance_count": instance_count,
            "healthy_instances": healthy_count,
            "pending_tasks": pending_count,
            "active_tasks": active_count,
            "completion_rate": (
                self._stats["tasks_completed"] / 
                max(1, self._stats["tasks_submitted"])
            ),
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "instance_joins": 0,
            "instance_leaves": 0,
        }

    # ── 回调 ────────────────────────────────────────────────────

    def on_task_complete(self, callback: Callable) -> None:
        """注册任务完成回调。"""
        self._on_task_complete.append(callback)

    def on_instance_event(self, callback: Callable) -> None:
        """注册实例事件回调。"""
        self._on_instance_event.append(callback)

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._instance_lock:
            self._instances.clear()
        with self._task_lock:
            self._pending_tasks.clear()
            self._active_tasks.clear()
        logger.info("DistributedCognitionManager closed")


__all__ = [
    "DistributedCognitionManager",
    "CognitionInstance",
    "DistributedTask",
    "InstanceState",
    "TaskDistributionStrategy",
]
