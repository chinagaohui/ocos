"""HealthCheck — Agent 运行时健康检查框架。

每个组件自身决定健康状态。HealthCheck 聚合结果并返回统一报告。
设计原则：不注入 — 不 ping — 不超时。组件同步返回当前状态。
"""

from __future__ import annotations

from typing import Any, Callable

from ocos.events.event_bus import EventBus

# 健康状态枚举
HEALTHY = "healthy"
DEGRADED = "degraded"
UNHEALTHY = "unhealthy"
UNKNOWN = "unknown"


class ComponentCheck:
    """单个组件的健康检查封装。"""

    __slots__ = ("name", "_check_fn", "_metadata")

    def __init__(
        self,
        name: str,
        check_fn: Callable[[], dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self._check_fn = check_fn
        self._metadata = metadata or {}

    def run(self) -> dict[str, Any]:
        """执行检查，返回结构化结果。"""
        try:
            result = self._check_fn()
            status = result.get("status", UNKNOWN)
        except Exception as e:
            status = UNHEALTHY
            result = {"error": str(e)}

        return {
            "component": self.name,
            "status": status,
            **self._metadata,
            **result,
        }

    def __repr__(self) -> str:
        return f"ComponentCheck({self.name})"


class HealthCheck:
    """聚合式健康检查。

    每个组件独立检查，互不等待。
    """

    def __init__(self) -> None:
        self._checks: dict[str, ComponentCheck] = {}

    def register(
        self,
        name: str,
        check_fn: Callable[[], dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """注册一个健康检查。"""
        self._checks[name] = ComponentCheck(name, check_fn, metadata)

    def unregister(self, name: str) -> None:
        """取消注册。"""
        self._checks.pop(name, None)

    def check_all(self) -> dict[str, Any]:
        """运行所有检查，返回聚合报告。"""
        results: list[dict[str, Any]] = []
        for name in sorted(self._checks):
            c = self._checks[name]
            results.append(c.run())

        # 聚合状态
        statuses = {r["status"] for r in results}
        if UNHEALTHY in statuses:
            overall = UNHEALTHY
        elif DEGRADED in statuses:
            overall = DEGRADED
        elif statuses == {HEALTHY}:
            overall = HEALTHY
        else:
            overall = UNKNOWN

        return {
            "overall": overall,
            "components": results,
            "total": len(results),
            "healthy": sum(1 for r in results if r["status"] == HEALTHY),
            "unhealthy": sum(1 for r in results if r["status"] == UNHEALTHY),
        }

    def check_one(self, name: str) -> dict[str, Any] | None:
        """运行单个组件的检查。"""
        c = self._checks.get(name)
        if c is None:
            return None
        return c.run()

    # ── 便捷工厂方法 ────────────────────────────────────────

    @staticmethod
    def for_event_bus(event_bus: EventBus) -> ComponentCheck:
        """EventBus 检查工厂。"""
        def _check() -> dict[str, Any]:
            return {"status": HEALTHY}

        return ComponentCheck("event_bus", _check)

    @staticmethod
    def for_engine_bridge(bridge) -> ComponentCheck:
        """EngineBridge 检查工厂。"""
        def _check() -> dict[str, Any]:
            registered = bridge.list_engines()
            return {
                "status": HEALTHY if registered else DEGRADED,
                "registered_engines": registered,
            }

        return ComponentCheck("engine_bridge", _check)

    @staticmethod
    def for_writer_engine(engine) -> ComponentCheck:
        """WriterEngine 检查工厂。"""
        def _check() -> dict[str, Any]:
            traces = engine.trace_count
            last = engine.last_trace
            last_success = last.success if last else None
            return {
                "status": HEALTHY,
                "traces": traces,
                "last_success": last_success,
            }

        return ComponentCheck(
            "writer_engine",
            _check,
            metadata={"type": "narrative"},
        )
