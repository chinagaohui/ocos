"""Phase AF: ProactiveEngagementManager — 主动参与管理器。

整合 ProactiveOutput + TrueInitiative + ProactiveEngine，
提供统一的主动参与接口：
- 主动性决策（基于记忆召回/空闲检测/模式变化）
- 输出频率管理（防骚扰）
- 权限检查（双检机制）
- 主动历史记录与审计

架构原则：
- AF-ENG-01: 主动性必须经过权限门
- AF-ENG-02: 频率受控（每日上限）
- AF-ENG-03: 疲劳时不打扰
- AF-ENG-04: 所有主动输出必须审计记录
"""

from __future__ import annotations

import uuid
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


class EngagementType(Enum):
    """参与类型。"""
    GREETING = auto()          # 问候
    OBSERVATION = auto()       # 观察报告
    SUGGESTION = auto()        # 建议
    ALERT = auto()             # 警报
    QUESTION = auto()          # 提问
    REMINDER = auto()          # 提醒


class EngagementSource(Enum):
    """主动性来源。"""
    MEMORY_RECALL = "memory_recall"       # 记忆召回
    IDLE_TIMEOUT = "idle_timeout"         # 空闲超时
    PATTERN_CHANGE = "pattern_change"     # 模式变化
    CONTEXT_HINT = "context_hint"         # 上下文提示
    SCHEDULED = "scheduled"               # 定时触发


class EngagementStatus(Enum):
    """参与状态。"""
    DRAFT = auto()           # 草稿
    PENDING = auto()         # 待发送
    SENT = auto()            # 已发送
    ACKNOWLEDGED = auto()    # 已确认
    IGNORED = auto()         # 已忽略
    WITHDRAWN = auto()       # 已撤回


@dataclass
class EngagementRequest:
    """参与请求。"""
    request_id: str
    engagement_type: EngagementType
    source: EngagementSource
    topic: str
    content: str
    urgency: float = 0.5
    context_summary: str = ""
    status: EngagementStatus = EngagementStatus.DRAFT
    created_at: float = 0.0
    sent_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"eng:{uuid.uuid4().hex[:8]}"
        if self.created_at == 0.0:
            self.created_at = time.time()


class ProactiveEngagementManager:
    """主动参与管理器。

    统一管理层：
    1. 主动性决策（基于记忆/模式/空闲）
    2. 输出频率管理（防骚扰）
    3. 权限检查（双检机制）
    4. 主动历史记录与审计
    """

    def __init__(
        self,
        max_daily_initiatives: int = 10,
        max_hourly_initiatives: int = 3,
        fatigue_threshold: float = 0.7,
        permission_guard: Any = None,
        constitution: Any = None,
    ):
        self._max_daily_initiatives = max_daily_initiatives
        self._max_hourly_initiatives = max_hourly_initiatives
        self._fatigue_threshold = fatigue_threshold
        self._permission_guard = permission_guard
        self._constitution = constitution

        # 参与请求历史
        self._requests: dict[str, EngagementRequest] = {}
        self._request_lock = threading.RLock()

        # 频率统计
        self._daily_count: int = 0
        self._hourly_count: int = 0
        self._last_daily_reset: float = time.time()
        self._last_hourly_reset: float = time.time()
        self._stat_lock = threading.Lock()

        # 回调
        self._output_callback: Optional[Callable[[str], None]] = None
        self._callback_lock = threading.RLock()

        # 统计
        self._stats = {
            "total_initiatives": 0,
            "initiatives_sent": 0,
            "initiatives_rejected": 0,
            "initiatives_ignored": 0,
            "avg_urgency": 0.0,
        }

    # ── 主动性决策 ────────────────────────────────────────────────

    def create_engagement_request(
        self,
        engagement_type: EngagementType,
        topic: str,
        content: str,
        source: EngagementSource = EngagementSource.MEMORY_RECALL,
        urgency: float = 0.5,
        context_summary: str = "",
    ) -> EngagementRequest | None:
        """创建参与请求。"""
        with self._request_lock:
            if len(self._requests) >= 1000:  # 历史限制
                logger.warning("Max requests reached")
                return None

            request = EngagementRequest(
                request_id=f"eng:{uuid.uuid4().hex[:8]}",
                engagement_type=engagement_type,
                source=source,
                topic=topic,
                content=content,
                urgency=urgency,
                context_summary=context_summary,
                status=EngagementStatus.DRAFT,
            )
            self._requests[request.request_id] = request
            self._stats["total_initiatives"] += 1
            logger.info("Engagement request created: %s (type=%s, urgency=%.2f)",
                       request.request_id, engagement_type.name, urgency)
            return request

    def submit_for_review(self, request_id: str) -> bool:
        """提交参与请求进行审核。"""
        with self._request_lock:
            request = self._requests.get(request_id)
            if not request:
                return False
            if request.status != EngagementStatus.DRAFT:
                return False
            request.status = EngagementStatus.PENDING
            return True

    def approve_engagement(self, request_id: str) -> bool:
        """批准参与请求。"""
        with self._request_lock:
            request = self._requests.get(request_id)
            if not request or request.status != EngagementStatus.PENDING:
                return False
            request.status = EngagementStatus.SENT
            request.sent_at = time.time()
            self._stats["initiatives_sent"] += 1
            self._update_urgency_stats(request.urgency)
            logger.info("Engagement approved: %s", request_id)
            return True

    def reject_engagement(self, request_id: str, reason: str = "") -> bool:
        """拒绝参与请求。"""
        with self._request_lock:
            request = self._requests.get(request_id)
            if not request:
                return False
            request.status = EngagementStatus.WITHDRAWN
            self._stats["initiatives_rejected"] += 1
            logger.info("Engagement rejected: %s (reason=%s)", request_id, reason)
            return True

    def mark_ignored(self, request_id: str) -> bool:
        """标记为已忽略。"""
        with self._request_lock:
            request = self._requests.get(request_id)
            if not request or request.status != EngagementStatus.SENT:
                return False
            request.status = EngagementStatus.IGNORED
            self._stats["initiatives_ignored"] += 1
            return True

    def get_request(self, request_id: str) -> EngagementRequest | None:
        """获取参与请求。"""
        with self._request_lock:
            return self._requests.get(request_id)

    def list_requests(
        self,
        status: EngagementStatus | None = None,
        limit: int = 50,
    ) -> list[EngagementRequest]:
        """列出参与请求。"""
        with self._request_lock:
            requests = list(self._requests.values())
            if status:
                requests = [r for r in requests if r.status == status]
            return requests[-limit:]

    # ── 频率管理 ────────────────────────────────────────────────

    def check_frequency_limit(self) -> tuple[bool, str]:
        """检查频率限制。"""
        with self._stat_lock:
            now = time.time()
            
            # 重置每日计数
            if now - self._last_daily_reset >= 86400:  # 24小时
                self._daily_count = 0
                self._last_daily_reset = now
            
            # 重置每小时计数
            if now - self._last_hourly_reset >= 3600:
                self._hourly_count = 0
                self._last_hourly_reset = now
            
            # 检查限制
            if self._daily_count >= self._max_daily_initiatives:
                return False, "daily_limit"
            if self._hourly_count >= self._max_hourly_initiatives:
                return False, "hourly_limit"
            
            return True, ""

    def increment_counts(self) -> None:
        """增加计数。"""
        with self._stat_lock:
            self._daily_count += 1
            self._hourly_count += 1

    # ── 权限检查 ────────────────────────────────────────────────

    def check_permission(self, request: EngagementRequest) -> tuple[bool, str]:
        """检查权限。"""
        if self._permission_guard is None:
            return True, ""
        
        try:
            result = self._permission_guard.check("proactive_output", {
                "type": request.engagement_type.name,
                "urgency": request.urgency,
            })
            if result:
                return True, ""
            return False, "permission_denied"
        except Exception as e:
            logger.warning("Permission check failed: %s", e)
            return False, str(e)

    def check_constitution(self, request: EngagementRequest) -> tuple[bool, str]:
        """检查宪法约束。"""
        if self._constitution is None:
            return True, ""
        
        try:
            result = self._constitution.check_action("proactive_output")
            if result.allowed:
                return True, ""
            return False, result.reason
        except Exception as e:
            logger.warning("Constitution check failed: %s", e)
            return False, str(e)

    def dual_check(self, request: EngagementRequest) -> tuple[bool, str]:
        """双检机制（权限 + 宪法）。"""
        perm_ok, perm_reason = self.check_permission(request)
        if not perm_ok:
            return False, f"permission:{perm_reason}"
        
        const_ok, const_reason = self.check_constitution(request)
        if not const_ok:
            return False, f"constitution:{const_reason}"
        
        return True, ""

    # ── 疲劳检测 ────────────────────────────────────────────────

    def check_fatigue(self, fatigue_level: float) -> tuple[bool, str]:
        """检查疲劳水平。"""
        if fatigue_level >= self._fatigue_threshold:
            return False, "fatigue"
        return True, ""

    # ── 执行引擎 ────────────────────────────────────────────────

    def execute_engagement(self, request_id: str, fatigue_level: float = 0.0) -> dict[str, Any]:
        """执行参与请求（完整流程）。"""
        with self._request_lock:
            request = self._requests.get(request_id)
            if not request:
                return {"error": "request not found"}
            
            # 频率检查
            freq_ok, freq_reason = self.check_frequency_limit()
            if not freq_ok:
                return {"error": f"frequency_limit:{freq_reason}"}
            
            # 疲劳检查
            fatigue_ok, fatigue_reason = self.check_fatigue(fatigue_level)
            if not fatigue_ok:
                return {"error": f"fatigue:{fatigue_reason}"}
            
            # 双检
            perm_ok, perm_reason = self.dual_check(request)
            if not perm_ok:
                return {"error": perm_reason}
            
            # 发送
            message = self._build_message(request)
            self._send_message(message)
            
            # 更新状态
            request.status = EngagementStatus.SENT
            request.sent_at = time.time()
            self.increment_counts()
            self._update_urgency_stats(request.urgency)
            
            return {"success": True, "message": message}

    def _build_message(self, request: EngagementRequest) -> str:
        """构建消息。"""
        templates = {
            EngagementType.GREETING: "问候: {content}",
            EngagementType.OBSERVATION: "观察: {content}",
            EngagementType.SUGGESTION: "建议: {content}",
            EngagementType.ALERT: "警报: {content}",
            EngagementType.QUESTION: "提问: {content}",
            EngagementType.REMINDER: "提醒: {content}",
        }
        template = templates.get(request.engagement_type, "{content}")
        return template.format(content=request.content)

    def _send_message(self, message: str) -> None:
        """发送消息。"""
        with self._callback_lock:
            if self._output_callback:
                try:
                    self._output_callback(message)
                except Exception as e:
                    logger.error("Output callback failed: %s", e)
            else:
                logger.info("Proactive output: %s", message[:100])

    def set_output_callback(self, callback: Callable[[str], None]) -> None:
        """设置输出回调。"""
        with self._callback_lock:
            self._output_callback = callback

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._request_lock:
            request_count = len(self._requests)
            pending_count = sum(1 for r in self._requests.values() if r.status == EngagementStatus.PENDING)
        
        with self._stat_lock:
            return {
                **self._stats,
                "request_count": request_count,
                "pending_count": pending_count,
                "daily_count": self._daily_count,
                "hourly_count": self._hourly_count,
            }

    def _update_urgency_stats(self, urgency: float) -> None:
        """更新平均紧急度统计。"""
        with self._stat_lock:
            total = self._stats["initiatives_sent"]
            if total > 0:
                current_avg = self._stats["avg_urgency"]
                self._stats["avg_urgency"] = (current_avg * (total - 1) + urgency) / total

    def reset_stats(self) -> None:
        """重置统计。"""
        with self._stat_lock:
            self._daily_count = 0
            self._hourly_count = 0
            self._last_daily_reset = time.time()
            self._last_hourly_reset = time.time()
        self._stats = {
            "total_initiatives": 0,
            "initiatives_sent": 0,
            "initiatives_rejected": 0,
            "initiatives_ignored": 0,
            "avg_urgency": 0.0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._request_lock:
            self._requests.clear()
        logger.info("ProactiveEngagementManager closed")


__all__ = [
    "ProactiveEngagementManager",
    "EngagementRequest",
    "EngagementType",
    "EngagementSource",
    "EngagementStatus",
]
