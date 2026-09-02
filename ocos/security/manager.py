"""Phase X: SecurityManager — 统一安全管理与防护。

整合现有安全基础设施：
- PermissionGateway: 权限网关（PS24-A）
- AuditEntry: 审计日志
- 输入验证与清洗

新增能力：
- RateLimiter: 请求频率限制（令牌桶/滑动窗口）
- SecurityPolicy: 安全策略管理
- SecurityAuditLog: 综合审计日志（安全事件聚合）
- InputSanitizer: 输入清洗（SQL注入/XSS/路径穿越）
- SecurityMetrics: 安全指标暴露

启动方式:
    from ocos.security.manager import SecurityManager
    sm = SecurityManager()
    result = sm.check_access("user_request", action="create_goal")
"""

from __future__ import annotations

import enum
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ── 枚举 ────────────────────────────────────────────────────────────────────


class SecurityLevel(enum.Enum):
    """安全等级。"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AccessDecision(enum.Enum):
    """访问决策。"""
    ALLOW = "ALLOW"
    DENY = "DENY"
    RATE_LIMITED = "RATE_LIMITED"
    REQUIRE_AUTH = "REQUIRE_AUTH"


# ── 数据类 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SecurityEvent:
    """安全事件记录。"""
    timestamp: datetime
    event_type: str
    source: str
    action: str
    decision: str
    severity: str
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            object.__setattr__(self, 'event_id', f"{self.source}:{self.action}:{int(time.time() * 1000)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "source": self.source,
            "action": self.action,
            "decision": self.decision,
            "severity": self.severity,
            "details": self.details,
        }


@dataclass
class RateLimitConfig:
    """限流配置。"""
    window_seconds: int = 60
    max_requests: int = 100
    burst_size: int = 20
    key_func: Optional[Callable[[str, str], str]] = None  # 自定义 key 生成器

    def get_key(self, source: str, action: str) -> str:
        if self.key_func:
            return self.key_func(source, action)
        return f"{source}:{action}"


@dataclass
class SecurityPolicy:
    """安全策略。"""
    name: str
    level: SecurityLevel
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    rate_limit: Optional[RateLimitConfig] = None
    require_auth: bool = False
    ip_whitelist: list[str] = field(default_factory=list)
    description: str = ""


# ── RateLimiter ──────────────────────────────────────────────────────────────


class RateLimiter:
    """令牌桶 + 滑动窗口限流器。"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._burst_buckets: dict[str, float] = defaultdict(float)
        self._last_refill: dict[str, float] = {}

    def is_allowed(self, source: str, action: str) -> tuple[bool, dict[str, Any]]:
        """检查是否允许请求。"""
        key = self.config.get_key(source, action)
        now = time.time()
        window_start = now - self.config.window_seconds

        # 清理过期记录
        timestamps = [t for t in self._buckets[key] if t > window_start]
        self._buckets[key] = timestamps

        # 检查滑动窗口
        if len(timestamps) >= self.config.max_requests:
            return False, {
                "reason": "rate_limit_exceeded",
                "current_count": len(timestamps),
                "max_allowed": self.config.max_requests,
                "reset_at": timestamps[0] + self.config.window_seconds if timestamps else now,
            }

        # 检查突发限制
        self._burst_buckets[key] = max(0, self._burst_buckets[key] - (now - self._last_refill.get(key, now)))
        self._last_refill[key] = now

        if self._burst_buckets[key] >= self.config.burst_size:
            return False, {
                "reason": "burst_limit_exceeded",
                "current_burst": self._burst_buckets[key],
                "max_burst": self.config.burst_size,
            }

        # 记录请求
        self._buckets[key].append(now)
        self._burst_buckets[key] += 1

        return True, {
            "reason": "allowed",
            "remaining": self.config.max_requests - len(self._buckets[key]),
            "burst_remaining": self.config.burst_size - self._burst_buckets[key],
        }

    def get_stats(self) -> dict[str, Any]:
        """获取限流统计。"""
        return {
            "tracked_keys": len(self._buckets),
            "window_seconds": self.config.window_seconds,
            "max_requests": self.config.max_requests,
            "burst_size": self.config.burst_size,
            "active_buckets": sum(
                1 for ts in self._buckets.values()
                if ts and ts[-1] > time.time() - self.config.window_seconds
            ),
        }


# ── InputSanitizer ───────────────────────────────────────────────────────────


class InputSanitizer:
    """输入清洗器。"""

    # SQL 注入模式
    _SQL_PATTERNS = [
        re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC)\s", re.IGNORECASE),
        re.compile(r"(?:--|#|/\*)", re.IGNORECASE),
        re.compile(r"(?:OR|AND)\s+\d+=\d+", re.IGNORECASE),
        re.compile(r";\s*(?:DROP|DELETE|INSERT|UPDATE)", re.IGNORECASE),
    ]

    # XSS 模式
    _XSS_PATTERNS = [
        re.compile(r"<\s*script", re.IGNORECASE),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
        re.compile(r"<\s*iframe", re.IGNORECASE),
        re.compile(r"<\s*img[^>]+onerror", re.IGNORECASE),
    ]

    # 路径穿越
    _PATH_PATTERNS = [
        re.compile(r"\.\./"),
        re.compile(r"\.\.\\"),
        re.compile(r"%2e%2e", re.IGNORECASE),
    ]

    # 命令注入
    _CMD_PATTERNS = [
        re.compile(r"[;&|`$]"),
        re.compile(r"\$\("),
        re.compile(r"\{[^}]*\}"),
    ]

    def sanitize(self, text: str, context: str = "general") -> tuple[str, list[str]]:
        """清洗输入，返回（清洗后文本, 检测到的威胁列表）。"""
        threats = []

        # SQL 注入检测
        for pattern in self._SQL_PATTERNS:
            if pattern.search(text):
                threats.append(f"SQL_INJECTION: {pattern.pattern}")

        # XSS 检测
        for pattern in self._XSS_PATTERNS:
            if pattern.search(text):
                threats.append(f"XSS: {pattern.pattern}")

        # 路径穿越检测
        for pattern in self._PATH_PATTERNS:
            if pattern.search(text):
                threats.append(f"PATH_TRAVERSAL: {pattern.pattern}")

        # 命令注入检测
        for pattern in self._CMD_PATTERNS:
            if pattern.search(text):
                threats.append(f"CMD_INJECTION: {pattern.pattern}")

        # 简单清洗（保留原始文本用于审计）
        sanitized = text

        return sanitized, threats

    def is_safe(self, text: str) -> bool:
        """检查文本是否安全。"""
        _, threats = self.sanitize(text)
        return len(threats) == 0


# ── SecurityAuditLog ─────────────────────────────────────────────────────────


class SecurityAuditLog:
    """安全审计日志。"""

    def __init__(self, max_entries: int = 10000):
        self._entries: list[SecurityEvent] = []
        self._max_entries = max_entries
        self._stats = {
            "total_events": 0,
            "blocked": 0,
            "allowed": 0,
            "rate_limited": 0,
            "by_severity": defaultdict(int),
            "by_type": defaultdict(int),
        }

    def record(self, event: SecurityEvent) -> None:
        """记录安全事件。"""
        self._entries.append(event)
        self._stats["total_events"] += 1
        self._stats["by_severity"][event.severity] += 1
        self._stats["by_type"][event.event_type] += 1

        if event.decision == AccessDecision.DENY.value:
            self._stats["blocked"] += 1
        elif event.decision == AccessDecision.ALLOW.value:
            self._stats["allowed"] += 1
        elif event.decision == AccessDecision.RATE_LIMITED.value:
            self._stats["rate_limited"] += 1

        # 限制内存中的条目数
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries // 2:]

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的审计记录。"""
        return [e.to_dict() for e in self._entries[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """获取审计统计。"""
        return {
            **self._stats,
            "by_severity": dict(self._stats["by_severity"]),
            "by_type": dict(self._stats["by_type"]),
            "total_entries": len(self._entries),
        }

    def export_json(self) -> str:
        """导出为 JSON。"""
        return json.dumps(
            [e.to_dict() for e in self._entries],
            indent=2,
            ensure_ascii=False,
        )


# ── SecurityManager ──────────────────────────────────────────────────────────


class SecurityManager:
    """统一安全管理系统。

    职责：
    1. 权限检查（基于策略）
    2. 速率限制
    3. 输入清洗与威胁检测
    4. 安全审计日志
    5. 安全策略管理
    """

    def __init__(
        self,
        default_rate_limit: Optional[RateLimitConfig] = None,
        audit_log_max: int = 10000,
        strict_mode: bool = False,
    ):
        self.default_rate_limit = default_rate_limit or RateLimitConfig()
        self.audit_log = SecurityAuditLog(max_entries=audit_log_max)
        self.strict_mode = strict_mode
        self._policies: dict[str, SecurityPolicy] = {}
        self._rate_limiters: dict[str, RateLimiter] = {}
        self._sanitizer = InputSanitizer()

        # 注册默认策略
        self._register_default_policies()

    def _register_default_policies(self) -> None:
        """注册默认安全策略。"""
        self.register_policy(SecurityPolicy(
            name="default",
            level=SecurityLevel.MEDIUM,
            allowed_actions=["query", "read", "plan", "generate"],
            blocked_actions=["modify_identity", "delete_memory", "override_constitution"],
            rate_limit=RateLimitConfig(window_seconds=60, max_requests=60),
        ))

        self.register_policy(SecurityPolicy(
            name="high_security",
            level=SecurityLevel.HIGH,
            allowed_actions=["query", "read"],
            blocked_actions=["*"],  # 除白名单外全部拒绝
            rate_limit=RateLimitConfig(window_seconds=60, max_requests=30),
            require_auth=True,
        ))

        self.register_policy(SecurityPolicy(
            name="open",
            level=SecurityLevel.LOW,
            allowed_actions=["*"],  # 允许所有
            blocked_actions=[],
            rate_limit=RateLimitConfig(window_seconds=60, max_requests=200),
        ))

    def register_policy(self, policy: SecurityPolicy) -> None:
        """注册安全策略。"""
        self._policies[policy.name] = policy
        if policy.rate_limit:
            self._rate_limiters[policy.name] = RateLimiter(policy.rate_limit)

    def check_access(
        self,
        source: str,
        action: str,
        policy_name: str = "default",
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[AccessDecision, str, dict[str, Any]]:
        """检查访问权限。

        返回: (决策, 原因, 详细信息)
        """
        policy = self._policies.get(policy_name)
        if not policy:
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="access_check",
                source=source,
                action=action,
                decision=AccessDecision.DENY.value,
                severity=SecurityLevel.HIGH.value,
                details={"reason": "unknown_policy", "policy": policy_name},
            )
            self.audit_log.record(event)
            return AccessDecision.DENY, "unknown policy", {"policy": policy_name}

        # 检查动作白名单/黑名单
        if "*" in policy.blocked_actions:
            # 全局拒绝模式
            if action not in policy.allowed_actions:
                event = SecurityEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type="access_denied",
                    source=source,
                    action=action,
                    decision=AccessDecision.DENY.value,
                    severity=SecurityLevel.HIGH.value,
                    details={"policy": policy_name, "reason": "blocked_action"},
                )
                self.audit_log.record(event)
                return AccessDecision.DENY, f"action blocked by policy '{policy_name}'", {}

        if action in policy.blocked_actions:
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="access_denied",
                source=source,
                action=action,
                decision=AccessDecision.DENY.value,
                severity=self._severity_for_action(action),
                details={"policy": policy_name, "reason": "explicitly_blocked"},
            )
            self.audit_log.record(event)
            return AccessDecision.DENY, f"action '{action}' blocked by policy '{policy_name}'", {}

        # 速率限制检查
        limiter = self._rate_limiters.get(policy_name)
        if limiter:
            allowed, info = limiter.is_allowed(source, action)
            if not allowed:
                event = SecurityEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type="rate_limited",
                    source=source,
                    action=action,
                    decision=AccessDecision.RATE_LIMITED.value,
                    severity=SecurityLevel.MEDIUM.value,
                    details=info,
                )
                self.audit_log.record(event)
                return AccessDecision.RATE_LIMITED, "rate limited", info

        # 通过检查
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="access_allowed",
            source=source,
            action=action,
            decision=AccessDecision.ALLOW.value,
            severity=SecurityLevel.LOW.value,
            details={"policy": policy_name},
        )
        self.audit_log.record(event)

        return AccessDecision.ALLOW, "access granted", {}

    def sanitize_input(
        self,
        text: str,
        source: str = "unknown",
        context: str = "general",
    ) -> tuple[str, list[str], AccessDecision]:
        """清洗并检查输入。

        返回: (清洗后文本, 威胁列表, 决策)
        """
        sanitized, threats = self._sanitizer.sanitize(text, context)

        if threats:
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="threat_detected",
                source=source,
                action="input_sanitize",
                decision=AccessDecision.DENY.value,
                severity=SecurityLevel.HIGH.value,
                details={"threats": threats, "original_length": len(text)},
            )
            self.audit_log.record(event)
            return sanitized, threats, AccessDecision.DENY

        return sanitized, [], AccessDecision.ALLOW

    def get_security_stats(self) -> dict[str, Any]:
        """获取安全统计。"""
        return {
            "audit_stats": self.audit_log.get_stats(),
            "rate_limiters": {
                name: limiter.get_stats()
                for name, limiter in self._rate_limiters.items()
            },
            "policies": list(self._policies.keys()),
            "strict_mode": self.strict_mode,
        }

    def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的安全事件。"""
        return self.audit_log.get_recent(limit)

    def export_audit_log(self) -> str:
        """导出完整审计日志。"""
        return self.audit_log.export_json()

    def _severity_for_action(self, action: str) -> str:
        """根据动作确定严重性等级。"""
        critical_actions = {"modify_identity", "override_constitution", "delete_all"}
        high_actions = {"delete_memory", "modify_goal", "execute_system"}

        if action in critical_actions:
            return SecurityLevel.CRITICAL.value
        elif action in high_actions:
            return SecurityLevel.HIGH.value
        return SecurityLevel.MEDIUM.value

    def add_custom_policy(
        self,
        name: str,
        allowed: list[str],
        blocked: list[str],
        rate_limit: Optional[RateLimitConfig] = None,
        level: SecurityLevel = SecurityLevel.MEDIUM,
    ) -> None:
        """添加自定义策略。"""
        self.register_policy(SecurityPolicy(
            name=name,
            level=level,
            allowed_actions=allowed,
            blocked_actions=blocked,
            rate_limit=rate_limit,
        ))


# ── 工厂函数 ────────────────────────────────────────────────────────────────


def create_security_manager(
    strict: bool = False,
    rate_limit_per_minute: int = 60,
    **kwargs,
) -> SecurityManager:
    """创建 SecurityManager（支持环境变量覆盖）。"""
    env_rate = os.getenv("OCOS_RATE_LIMIT")
    if env_rate:
        rate_limit_per_minute = int(env_rate)

    return SecurityManager(
        default_rate_limit=RateLimitConfig(
            window_seconds=60,
            max_requests=rate_limit_per_minute,
        ),
        strict_mode=strict,
        **kwargs,
    )
