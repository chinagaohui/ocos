"""Phase X: SecurityManager 单元测试。"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from ocos.security.manager import (
    SecurityManager,
    SecurityPolicy,
    SecurityLevel,
    AccessDecision,
    RateLimitConfig,
    RateLimiter,
    InputSanitizer,
    SecurityAuditLog,
    SecurityEvent,
)


class TestSecurityEvent:
    """SecurityEvent 测试。"""

    def test_create(self):
        from datetime import datetime
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="test",
            source="src",
            action="act",
            decision="ALLOW",
            severity="LOW",
        )
        assert event.event_id.startswith("src:act:")
        assert event.source == "src"

    def test_to_dict(self):
        from datetime import datetime
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="access",
            source="api",
            action="query",
            decision="ALLOW",
            severity="LOW",
            details={"key": "value"},
        )
        d = event.to_dict()
        assert d["source"] == "api"
        assert d["details"]["key"] == "value"


class TestRateLimiter:
    """RateLimiter 测试。"""

    def test_basic_allow(self):
        config = RateLimitConfig(max_requests=10, window_seconds=60)
        limiter = RateLimiter(config)

        allowed, info = limiter.is_allowed("user1", "query")
        assert allowed is True
        assert info["reason"] == "allowed"

    def test_rate_limit_exceeded(self):
        config = RateLimitConfig(max_requests=5, window_seconds=60)
        limiter = RateLimiter(config)

        # 对同一 source+action 发送超过限制的请求
        for i in range(5):
            allowed, _ = limiter.is_allowed("user1", "query")
            assert allowed is True

        # 第 6 个应该被拒绝
        allowed, info = limiter.is_allowed("user1", "query")
        assert allowed is False
        assert info["reason"] == "rate_limit_exceeded"

    def test_different_sources_independent(self):
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        limiter = RateLimiter(config)

        # user1 发送 2 个请求到同一 action
        for _ in range(2):
            allowed, _ = limiter.is_allowed("user1", "query")
            assert allowed is True

        # user1 第 3 个被拒绝
        allowed, _ = limiter.is_allowed("user1", "query")
        assert allowed is False

        # user2 应该独立（同一 action）
        allowed, _ = limiter.is_allowed("user2", "query")
        assert allowed is True

    def test_different_actions_independent(self):
        config = RateLimitConfig(max_requests=2, window_seconds=60)
        limiter = RateLimiter(config)

        # query 动作
        for _ in range(2):
            allowed, _ = limiter.is_allowed("user1", "query")
            assert allowed is True

        # plan 动作应该独立（不同 action 不计入同一计数）
        allowed, _ = limiter.is_allowed("user1", "plan")
        assert allowed is True

    def test_get_stats(self):
        config = RateLimitConfig(max_requests=100, window_seconds=60)
        limiter = RateLimiter(config)

        stats = limiter.get_stats()
        assert stats["max_requests"] == 100
        assert stats["window_seconds"] == 60


class TestInputSanitizer:
    """InputSanitizer 测试。"""

    def test_clean_text(self):
        sanitizer = InputSanitizer()
        sanitized, threats = sanitizer.sanitize("Hello world", "test")
        assert sanitized == "Hello world"
        assert threats == []

    def test_sql_injection(self):
        sanitizer = InputSanitizer()
        sanitized, threats = sanitizer.sanitize("SELECT * FROM users", "sql")
        assert len(threats) > 0
        assert any("SQL" in t for t in threats)

    def test_xss(self):
        sanitizer = InputSanitizer()
        sanitized, threats = sanitizer.sanitize("<script>alert(1)</script>", "xss")
        assert len(threats) > 0
        assert any("XSS" in t for t in threats)

    def test_path_traversal(self):
        sanitizer = InputSanitizer()
        sanitized, threats = sanitizer.sanitize("../../etc/passwd", "path")
        assert len(threats) > 0
        assert any("PATH" in t for t in threats)

    def test_is_safe(self):
        sanitizer = InputSanitizer()
        assert sanitizer.is_safe("normal text") is True
        assert sanitizer.is_safe("<script>alert(1)</script>") is False


class TestSecurityAuditLog:
    """SecurityAuditLog 测试。"""

    def test_record_and_stats(self):
        from datetime import datetime
        log = SecurityAuditLog()
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="access",
            source="api",
            action="query",
            decision=AccessDecision.ALLOW.value,
            severity=SecurityLevel.LOW.value,
        )
        log.record(event)

        stats = log.get_stats()
        assert stats["total_events"] == 1
        assert stats["allowed"] == 1

    def test_get_recent(self):
        from datetime import datetime
        log = SecurityAuditLog()
        for i in range(5):
            event = SecurityEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="test",
                source="s",
                action="a",
                decision=AccessDecision.ALLOW.value,
                severity=SecurityLevel.LOW.value,
            )
            log.record(event)

        recent = log.get_recent(limit=3)
        assert len(recent) == 3

    def test_export_json(self):
        from datetime import datetime
        log = SecurityAuditLog()
        event = SecurityEvent(
            timestamp=datetime.now(timezone.utc),
            event_type="test",
            source="s",
            action="a",
            decision=AccessDecision.ALLOW.value,
            severity=SecurityLevel.LOW.value,
        )
        log.record(event)

        json_str = log.export_json()
        data = json.loads(json_str)
        assert len(data) == 1


class TestSecurityManager:
    """SecurityManager 测试。"""

    def test_create_default(self):
        manager = SecurityManager()
        stats = manager.get_security_stats()
        assert "default" in stats["policies"]
        assert "high_security" in stats["policies"]

    def test_check_access_allow(self):
        manager = SecurityManager()
        decision, reason, info = manager.check_access("user", "query")
        assert decision == AccessDecision.ALLOW
        assert reason == "access granted"

    def test_check_access_blocked(self):
        manager = SecurityManager()
        decision, reason, info = manager.check_access("user", "delete_memory")
        assert decision == AccessDecision.DENY

    def test_check_access_unknown_policy(self):
        manager = SecurityManager()
        decision, reason, info = manager.check_access("user", "query", policy_name="nonexistent")
        assert decision == AccessDecision.DENY

    def test_sanitize_input_safe(self):
        manager = SecurityManager()
        sanitized, threats, decision = manager.sanitize_input("normal text")
        assert decision == AccessDecision.ALLOW
        assert threats == []

    def test_sanitize_input_threat(self):
        manager = SecurityManager()
        sanitized, threats, decision = manager.sanitize_input("<script>alert(1)</script>")
        assert decision == AccessDecision.DENY
        assert len(threats) > 0

    def test_get_security_stats(self):
        manager = SecurityManager()
        stats = manager.get_security_stats()
        assert "audit_stats" in stats
        assert "rate_limiters" in stats
        assert "policies" in stats

    def test_get_recent_events(self):
        manager = SecurityManager()
        # 先产生一些事件
        manager.check_access("user", "query")
        manager.check_access("user", "delete_memory")

        events = manager.get_recent_events()
        assert len(events) >= 2

    def test_export_audit_log(self):
        manager = SecurityManager()
        manager.check_access("user", "query")

        json_str = manager.export_audit_log()
        data = json.loads(json_str)
        assert len(data) >= 1

    def test_add_custom_policy(self):
        manager = SecurityManager()
        manager.add_custom_policy(
            name="custom",
            allowed=["read", "write"],
            blocked=["delete"],
            level=SecurityLevel.HIGH,
        )

        stats = manager.get_security_stats()
        assert "custom" in stats["policies"]

    def test_rate_limiting(self):
        """测试限流生效。"""
        # 创建带有自定义限流的策略
        policy = SecurityPolicy(
            name="limited",
            level=SecurityLevel.MEDIUM,
            allowed_actions=["query"],
            rate_limit=RateLimitConfig(max_requests=5, window_seconds=60),
        )

        manager = SecurityManager()
        manager.register_policy(policy)

        # 对同一 source+action 发送超过限制的请求
        for i in range(5):
            decision, _, _ = manager.check_access("user", "query", policy_name="limited")
            assert decision == AccessDecision.ALLOW

        # 第 6 个应该被限流
        decision, reason, _ = manager.check_access("user", "query", policy_name="limited")
        assert decision == AccessDecision.RATE_LIMITED

    def test_strict_mode(self):
        """严格模式测试。"""
        manager = SecurityManager(strict_mode=True)
        assert manager.strict_mode is True


class TestEdgeCases:
    """边界条件测试。"""

    def test_empty_input_sanitize(self):
        manager = SecurityManager()
        sanitized, threats, decision = manager.sanitize_input("")
        assert decision == AccessDecision.ALLOW

    def test_unicode_input(self):
        manager = SecurityManager()
        sanitized, threats, decision = manager.sanitize_input("中文测试")
        assert decision == AccessDecision.ALLOW

    def test_very_long_input(self):
        manager = SecurityManager()
        long_text = "x" * 10000
        sanitized, threats, decision = manager.sanitize_input(long_text)
        # 纯重复字符不应触发威胁
        sql_xss_path = [t for t in threats if any(x in t for x in ["SQL", "XSS", "PATH"])]
        assert len(sql_xss_path) == 0

    def test_special_characters(self):
        manager = SecurityManager()
        # 使用不会触发威胁的安全字符
        safe_special = "[]{}().,:;-"
        sanitized, threats, decision = manager.sanitize_input(safe_special)
        # 安全字符不应触发 SQL/XSS/路径穿越威胁
        sql_xss_path = [t for t in threats if any(x in t for x in ["SQL", "XSS", "PATH"])]
        assert len(sql_xss_path) == 0
