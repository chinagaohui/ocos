"""P2-D: ProactiveEngine — 主动输出引擎（无 LLM，全确定性触发链）。

触发链（全部条件满足才输出）：
  1. 频率闸门：今日已输出 < daily_limit（默认每日 ≤1 次，陪伴≠骚扰）
  2. SELF 目标待办：goal_store 中存在 origin_level=SELF 的活跃目标
     （内生驱动源；无 SELF 目标 → 不主动打扰，审计 reason=no_self_goal）
  3. 疲劳闸门：attention.fatigue < 0.7（疲劳时不打扰）
  4. 模板选择：确定性轮换（问候 / 观察 / 提问）
  5. 权限双检：PermissionGuard.check + 宪法 check_action 均 allowed
     （防护缺失 → 拒绝输出并审计，绝不绕过）
  6. 输出：output_callback(message)（可注入通道）；未注入 → 本地日志
  7. 审计记录（granted=True / False 均落库）

Telegram 等外部通道仅留接口（output_callback 注入点），本模块不实现。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ocos.proactive.audit import ProactiveAuditStore
from ocos.proactive.templates import select_template

logger = logging.getLogger(__name__)

# 权限双检使用的动作（主动输出是 Agent 对自身观察的展示，属低风险）
_PROACTIVE_ACTION = "view_self"
_FATIGUE_THRESHOLD = 0.7


class ProactiveEngine:
    """主动输出引擎。所有依赖可选注入，缺失时防御式降级（不抛、不输出）。"""

    def __init__(
        self,
        *,
        goal_store: Any = None,
        attention: Any = None,
        permission_guard: Any = None,
        constitution: Any = None,
        audit_store: Optional[ProactiveAuditStore] = None,
        daily_limit: int = 1,
        fatigue_threshold: float = _FATIGUE_THRESHOLD,
        output_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.goal_store = goal_store
        self.attention = attention
        self.permission_guard = permission_guard
        self.constitution = constitution
        self.audit_store = audit_store or ProactiveAuditStore()
        self.audit_store.initialize()  # 幂等建表：注入与默认路径统一初始化
        self.daily_limit = max(1, daily_limit)
        self.fatigue_threshold = fatigue_threshold
        self.output_callback = output_callback

    # ── 入口 ─────────────────────────────────────────────────────────

    def maybe_proactive_output(self) -> Optional[str]:
        """尝试一次主动输出。触发链任一条件不满足 → 返回 None 并审计原因。

        防御式降级：内部异常全部吞掉（返回 None），绝不向调用方抛。
        """
        try:
            return self._run()
        except Exception as exc:  # pragma: no cover - 防御兜底
            logger.warning("ProactiveEngine degraded: %s", exc)
            return None

    # ── 触发链 ───────────────────────────────────────────────────────

    def _run(self) -> Optional[str]:
        # 1. 频率闸门
        if self.audit_store.count_granted_today() >= self.daily_limit:
            self.audit_store.record("greeting", "", False, reason="daily_limit")
            return None

        # 2. SELF 目标待办（内生驱动源）
        topic = self._self_goal_topic()
        if topic is None:
            self.audit_store.record("greeting", "", False, reason="no_self_goal")
            return None

        # 3. 疲劳闸门
        fatigue = self._fatigue_score()
        if fatigue is None or fatigue >= self.fatigue_threshold:
            self.audit_store.record(
                "greeting", "", False, reason=f"fatigue:{fatigue}"
            )
            return None

        # 4. 模板选择（确定性轮换）
        index = self.audit_store.count_granted_today()
        template = select_template(index, topic=topic)
        message = template.text

        # 5. 权限双检（PermissionGuard + 宪法，fail-closed）
        checks_ok, check_reason = self._checks_pass()
        if not checks_ok:
            self.audit_store.record(
                template.kind, message, False, reason=check_reason
            )
            return None

        # 6. 输出 + 7. 审计
        self._deliver(message)
        self.audit_store.record(template.kind, message, True)
        return message

    # ── 触发条件实现 ─────────────────────────────────────────────────

    def _self_goal_topic(self) -> Optional[str]:
        """返回首个 SELF 活跃目标的主题（description 前 12 字），无则 None。"""
        if self.goal_store is None:
            return None
        try:
            goals = self.goal_store.load_active()
        except Exception:
            return None
        for goal in goals or []:
            origin = getattr(goal, "origin_level", None)
            origin_name = getattr(origin, "name", None) or str(origin)
            if origin_name != "SELF":
                continue
            description = getattr(goal, "description", "") or ""
            topic = description.strip()[:12]
            return topic or "未命名目标"
        return None

    def _fatigue_score(self) -> Optional[float]:
        """注意力疲劳分（0~1）；attention 缺失 → None（触发链拒绝）。"""
        if self.attention is None:
            return None
        try:
            return float(self.attention.fatigue)
        except Exception:
            return None

    def _checks_pass(self) -> tuple[bool, str]:
        """权限双检：PermissionGuard + 宪法均允许才放行。

        fail-closed：任一防护缺失 → (False, "missing_guard")；检查异常 →
        (False, "check_error")。绝不无检输出。
        """
        if self.permission_guard is None or self.constitution is None:
            return False, "missing_guard"
        context = {"origin": "proactive", "channel": "local"}
        try:
            g = self.permission_guard.check(_PROACTIVE_ACTION, context)
            if not getattr(g, "allowed", False):
                return False, "permission_denied"

            # 宪法第二检：兼容 check_action（ConstitutionHub）与
            # check_decision（BehavioralConstitution，需 action 属性包装）
            constitution = self.constitution
            if hasattr(constitution, "check_action"):
                c = constitution.check_action(_PROACTIVE_ACTION, context)
            elif hasattr(constitution, "check_decision"):
                from types import SimpleNamespace

                c = constitution.check_decision(
                    SimpleNamespace(action=_PROACTIVE_ACTION), context
                )
            else:
                return False, "missing_guard"
            if not getattr(c, "allowed", False):
                return False, "constitution_denied"
        except Exception:
            return False, "check_error"
        return True, ""

    def _deliver(self, message: str) -> None:
        """输出通道：注入 callback 优先；否则本地日志（Telegram 留接口）。"""
        if self.output_callback is not None:
            try:
                self.output_callback(message)
                return
            except Exception as exc:  # 回调失败 → 降级日志
                logger.warning("Proactive output_callback failed: %s", exc)
        logger.info("[proactive] %s", message)
