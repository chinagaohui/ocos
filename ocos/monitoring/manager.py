"""Phase Y: MonitoringManager — 统一监控与可观测性管理。

整合现有监控组件：
- MetricsCollector: 引擎指标
- HealthMonitor: 认知健康
- GoalMonitor: 目标健康

新增能力：
- Prometheus HTTP 端点（/metrics）
- 告警规则引擎
- 监控日志
- 健康检查聚合

启动方式:
    from ocos.monitoring.manager import MonitoringManager
    mm = MonitoringManager()
    mm.start()  # 启动 HTTP 端点
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── 枚举 ────────────────────────────────────────────────────────────────────


class AlertSeverity(str):
    """告警等级。"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertState(str):
    """告警状态。"""
    FIRING = "FIRING"
    RESOLVED = "RESOLVED"
    PENDING = "PENDING"


# ── 数据类 ──────────────────────────────────────────────────────────────────


@dataclass
class MetricPoint:
    """单一指标数据点。"""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)

    def to_prometheus(self) -> str:
        """转换为 Prometheus exposition format。"""
        if self.labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
            return f'{self.name}{{{label_str}}} {self.value}'
        return f"{self.name} {self.value}"


@dataclass
class AlertRule:
    """告警规则。"""
    name: str
    condition: Callable[[dict[str, Any]], bool]
    severity: AlertSeverity
    message: str
    cooldown_seconds: int = 60
    enabled: bool = True

    def evaluate(self, context: dict[str, Any]) -> Optional[dict[str, Any]]:
        """评估规则。"""
        if not self.enabled:
            return None
        try:
            if self.condition(context):
                return {
                    "rule": self.name,
                    "severity": self.severity,
                    "message": self.message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.warning("Alert rule evaluation error: %s", e)
        return None


@dataclass
class Alert:
    """告警实例。"""
    rule_name: str
    severity: str
    message: str
    state: str = AlertState.FIRING
    fired_at: str = ""
    resolved_at: Optional[str] = None

    def __post_init__(self):
        if not self.fired_at:
            self.fired_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule_name,
            "severity": self.severity,
            "message": self.message,
            "state": self.state,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
        }


# ── AlertManager ─────────────────────────────────────────────────────────────


class AlertManager:
    """告警管理器。"""

    def __init__(self, max_alerts: int = 100):
        self._rules: list[AlertRule] = []
        self._active_alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []
        self._max_alerts = max_alerts
        self._last_fire_time: dict[str, float] = {}

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则。"""
        self._rules.append(rule)
        logger.info("Added alert rule: %s", rule.name)

    def evaluate(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """评估所有规则。"""
        triggered = []
        now = time.time()

        for rule in self._rules:
            result = rule.evaluate(context)
            if result:
                # 检查冷却时间
                last_fire = self._last_fire_time.get(rule.name, 0)
                if now - last_fire >= rule.cooldown_seconds:
                    self._last_fire_time[rule.name] = now
                    alert = Alert(
                        rule_name=rule.name,
                        severity=rule.severity,
                        message=rule.message,
                    )
                    self._active_alerts[rule.name] = alert
                    self._alert_history.append(alert)
                    triggered.append(result)

                    logger.warning("Alert triggered: %s - %s", rule.name, rule.message)

        # 清理过期历史
        if len(self._alert_history) > self._max_alerts:
            self._alert_history = self._alert_history[-self._max_alerts // 2:]

        return triggered

    def resolve_alert(self, rule_name: str) -> bool:
        """手动解决告警。"""
        if rule_name in self._active_alerts:
            alert = self._active_alerts[rule_name]
            alert.state = AlertState.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc).isoformat()
            del self._active_alerts[rule_name]
            return True
        return False

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """获取活跃告警。"""
        return [a.to_dict() for a in self._active_alerts.values()]

    def get_alert_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取告警历史。"""
        return [a.to_dict() for a in self._alert_history[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """获取告警统计。"""
        return {
            "active_alerts": len(self._active_alerts),
            "total_rules": len(self._rules),
            "total_history": len(self._alert_history),
        }


# ── 全局指标钩子（S3.5: 进程级埋点，未装配时静默 no-op）──────────────
#
# daemon 装配时经 set_global_metrics 挂接真实 MetricsRegistry；bridge 等
# 无法直接持有实例的模块经 record_global 埋点。测试/嵌入场景不装配 →
# _GLOBAL_METRICS 为 None，调用零开销返回。

_GLOBAL_METRICS: Optional["MetricsRegistry"] = None


def set_global_metrics(registry: Optional["MetricsRegistry"]) -> None:
    """挂接（或解除，传 None）进程级指标注册表。"""
    global _GLOBAL_METRICS
    _GLOBAL_METRICS = registry


def record_global(name: str, value: float = 1.0,
                  metric_type: str = "counter",
                  labels: Optional[dict[str, str]] = None) -> None:
    """进程级指标记录 — 未挂接时静默跳过（与 health_loop 同模式）。"""
    reg = _GLOBAL_METRICS
    if reg is None:
        return
    try:
        if metric_type == "counter":
            reg.increment(name, value, labels)
        elif metric_type == "gauge":
            reg.set_gauge(name, value, labels)
        elif metric_type == "histogram":
            reg.observe(name, value, labels)
    except Exception:
        # 埋点失败不放大（fail-open，仅观测）
        logger.debug("record_global skipped: %s", name)


# ── MetricsRegistry ─────────────────────────────────────────────────────────


class MetricsRegistry:
    """指标注册表。"""

    def __init__(self):
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._last_reset = time.monotonic()

    def increment(self, name: str, value: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """增加计数器。"""
        key = f"{name}{''.join(f'_{k}_{v}' for k, v in (labels or {}).items())}"
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """设置仪表盘值。"""
        key = f"{name}{''.join(f'_{k}_{v}' for k, v in (labels or {}).items())}"
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """观察直方图值。"""
        key = f"{name}{''.join(f'_{k}_{v}' for k, v in (labels or {}).items())}"
        self._histograms.setdefault(key, []).append(value)
        # 保留最近 1000 个值
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-500:]

    def to_prometheus(self) -> str:
        """导出为 Prometheus 格式。"""
        lines = []
        lines.append("# HELP ocos_up System is running")
        lines.append("# TYPE ocos_up gauge")
        lines.append(f"ocos_up {{status=\"running\"}} 1")
        lines.append("")

        lines.append("# HELP ocos_uptime_seconds Uptime in seconds")
        lines.append("# TYPE ocos_uptime_seconds gauge")
        uptime = time.monotonic() - self._last_reset
        lines.append(f"ocos_uptime_seconds {uptime:.1f}")
        lines.append("")

        lines.append("# HELP ocos_counters Counters")
        lines.append("# TYPE ocos_counters counter")
        for name, value in sorted(self._counters.items()):
            lines.append(f"ocos_counters{{name=\"{name}\"}} {value}")
        lines.append("")

        lines.append("# HELP ocos_gauges Gauges")
        lines.append("# TYPE ocos_gauges gauge")
        for name, value in sorted(self._gauges.items()):
            lines.append(f"ocos_gauges{{name=\"{name}\"}} {value}")
        lines.append("")

        lines.append("# HELP ocos_histograms Histograms")
        lines.append("# TYPE ocos_histograms histogram")
        for name, values in sorted(self._histograms.items()):
            if values:
                # S3.5 (白皮书 P3): 真实分位数（原 0.9/0.99 均输出 max）
                import statistics as _stats
                avg = sum(values) / len(values)
                ordered = sorted(values)
                def _q(q: float) -> float:
                    if len(ordered) == 1:
                        return ordered[0]
                    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
                    return ordered[idx]
                p50 = _stats.median(ordered)
                lines.append(f"ocos_histograms{{name=\"{name}\",quantile=\"0.5\"}} {p50}")
                lines.append(f"ocos_histograms{{name=\"{name}\",quantile=\"0.9\"}} {_q(0.9)}")
                lines.append(f"ocos_histograms{{name=\"{name}\",quantile=\"0.99\"}} {_q(0.99)}")
                lines.append(f"ocos_histograms_count{{name=\"{name}\"}} {len(values)}")
        lines.append("")

        # Step 5: 追加北极星指标 (autonomy_metrics) — 实时从 DB 计算
        try:
            from ocos.governance.autonomy_metrics import prometheus_metrics
            lines.append(prometheus_metrics())
        except Exception:
            pass  # DB 不存在或指标模块不可用时静默降级

        return "\n".join(lines)

    def reset(self) -> None:
        """重置所有指标。"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._last_reset = time.monotonic()


# ── MonitoringManager ───────────────────────────────────────────────────────


class MonitoringManager:
    """统一监控管理器。

    职责：
    1. 指标收集与聚合
    2. 告警规则评估
    3. Prometheus 端点暴露
    4. 健康检查聚合
    """

    def __init__(
        self,
        port: int = 9090,
        host: str = "127.0.0.1",
        enable_http: bool = True,
    ):
        self.port = port
        self.host = host
        self.enable_http = enable_http

        self.metrics = MetricsRegistry()
        self.alerts = AlertManager()

        self._running = False
        self._start_time = time.monotonic()
        self._http_server = None
        self._http_thread = None

        # 默认告警规则
        self._register_default_rules()

    def _register_default_rules(self) -> None:
        """注册默认告警规则。"""
        self.alerts.add_rule(AlertRule(
            name="high_error_rate",
            condition=lambda ctx: ctx.get("error_rate", 0) > 0.1,
            severity=AlertSeverity.ERROR,
            message="错误率超过 10%",
            cooldown_seconds=300,
        ))

        self.alerts.add_rule(AlertRule(
            name="high_latency",
            condition=lambda ctx: ctx.get("avg_latency_ms", 0) > 1000,
            severity=AlertSeverity.WARNING,
            message="平均延迟超过 1 秒",
            cooldown_seconds=120,
        ))

        self.alerts.add_rule(AlertRule(
            name="low_memory_health",
            condition=lambda ctx: ctx.get("memory_health_score", 1.0) < 0.3,
            severity=AlertSeverity.CRITICAL,
            message="记忆健康度低于 30%",
            cooldown_seconds=600,
        ))

    def record_metric(self, name: str, value: float, metric_type: str = "counter",
                      labels: Optional[dict[str, str]] = None) -> None:
        """记录指标。"""
        if metric_type == "counter":
            self.metrics.increment(name, value, labels)
        elif metric_type == "gauge":
            self.metrics.set_gauge(name, value, labels)
        elif metric_type == "histogram":
            self.metrics.observe(name, value, labels)

    def evaluate_alerts(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        """评估告警。"""
        return self.alerts.evaluate(context)

    def get_health_status(self) -> dict[str, Any]:
        """获取综合健康状态。"""
        active_alerts = self.alerts.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a["severity"] == AlertSeverity.CRITICAL]

        if critical_alerts:
            health = "critical"
        elif active_alerts:
            health = "degraded"
        else:
            health = "healthy"

        return {
            "status": health,
            "uptime_seconds": time.monotonic() - self._start_time,
            "active_alerts": len(active_alerts),
            "critical_alerts": len(critical_alerts),
            "alerts": active_alerts[:5],  # 最近 5 条
        }

    def get_metrics(self) -> str:
        """获取 Prometheus 格式指标。"""
        return self.metrics.to_prometheus()

    def get_stats(self) -> dict[str, Any]:
        """获取监控统计。"""
        return {
            "running": self._running,
            "port": self.port,
            "host": self.host,
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
            "alert_stats": self.alerts.get_stats(),
        }

    def start_http(self) -> bool:
        """启动 HTTP 端点（仅用于测试）。"""
        if not self.enable_http:
            return False

        try:
            # 简单 HTTP server（无需额外依赖）
            import http.server
            import socketserver

            class MetricsHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == "/metrics":
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; version=0.0.4")
                        self.end_headers()
                        self.wfile.write(self.server.manager.get_metrics().encode())
                    elif self.path == "/health":
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(self.server.manager.get_health_status()).encode())
                    else:
                        self.send_response(404)
                        self.end_headers()

                def log_message(self, format, *args):
                    pass  # 静默日志

            self._http_server = socketserver.TCPServer((self.host, self.port), MetricsHandler)
            self._http_server.manager = self

            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_thread.start()
            self._running = True

            logger.info("Monitoring HTTP server started on %s:%d", self.host, self.port)
            return True

        except Exception as e:
            logger.warning("Failed to start monitoring HTTP server: %s", e)
            return False

    def stop_http(self) -> None:
        """停止 HTTP 端点。"""
        if self._http_server:
            self._http_server.shutdown()
            self._http_server = None
            self._running = False
            logger.info("Monitoring HTTP server stopped")

    def __enter__(self):
        self.start_http()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_http()
        return False


# ── 工厂函数 ────────────────────────────────────────────────────────────────


def create_monitoring_manager(
    port: Optional[int] = None,
    enable_http: bool = True,
    **kwargs,
) -> MonitoringManager:
    """创建 MonitoringManager（支持环境变量覆盖）。"""
    env_port = os.getenv("OCOS_MONITORING_PORT")
    actual_port = int(env_port) if env_port else (port or 9090)

    return MonitoringManager(
        port=actual_port,
        enable_http=enable_http,
        **kwargs,
    )
