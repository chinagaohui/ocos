"""
B4 Policy Engine — 安全策略引擎。

职责：
- 对每个 Action 进行安全策略评估：`evaluate(action_type, params) -> PolicyResult`
- 加载默认安全策略
- 支持动态添加/删除/更新策略
- Governance 事件驱动更新（订阅 GOVERNANCE_APPROVED）
- 基于 PolicyRule 的规则引擎（field + operator + value + effect）

依赖：B3 Scheduler（通过 evaluate 接口集成）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.events.event_bus import EventBus
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class PolicyEffect(str, Enum):
    """策略规则的效果。"""
    ALLOW = "allow"
    DENY = "deny"


class RuleOperator(str, Enum):
    """规则运算符。"""
    EQ = "eq"           # field == value
    NEQ = "neq"         # field != value
    GT = "gt"           # field > value
    GTE = "gte"         # field >= value
    LT = "lt"           # field < value
    LTE = "lte"         # field <= value
    IN = "in"           # field in value (value 是 list)
    NOT_IN = "not_in"   # field not in value (value 是 list)
    STARTSWITH = "startswith"  # field.startswith(value)
    CONTAINS = "contains"      # field 包含子串 value
    EXISTS = "exists"          # field 存在且不为空
    NOT_EXISTS = "not_exists"  # field 不存在或为空


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PolicyRule:
    """一条策略规则。

    规则：当 params 中 field 满足 operator(value) 时，触发 effect。
    所有规则同时满足（AND 语义）时策略触发。
    """
    field: str = ""
    operator: RuleOperator = RuleOperator.EQ
    value: Any = None
    effect: PolicyEffect = PolicyEffect.DENY
    description: str = ""


@dataclass(frozen=True)
class Policy:
    """一条完整的策略。

    策略包含多条规则（AND 逻辑），全部匹配时触发 effect。
    """
    policy_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    rules: tuple[PolicyRule, ...] = field(default_factory=tuple)
    effect: PolicyEffect = PolicyEffect.DENY
    enabled: bool = True
    priority: int = 0              # 越高越优先
    action_type_pattern: str = "*"  # 匹配的 action_type，* = 全部
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION

    def matches_action_type(self, action_type: str) -> bool:
        """判断本策略是否适用于指定的 action_type。"""
        if self.action_type_pattern == "*":
            return True
        return action_type == self.action_type_pattern


@dataclass(frozen=True)
class PolicyResult:
    """策略评估结果。"""
    allowed: bool = True
    reason: str = ""
    violated_rules: tuple[str, ...] = field(default_factory=tuple)
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    policy_count: int = 0
    schema_version: str = SCHEMA_VERSION


# ── 规则匹配引擎 ─────────────────────────────────────────────────────────────

def _get_nested_field(params: dict[str, Any], field_path: str) -> Any:
    """从嵌套 dict 中按点号路径取值。例如 'params.engine_name'。"""
    parts = field_path.split(".")
    current: Any = params
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, _MISSING)
        elif isinstance(current, (list, tuple)) and part.lstrip("-").isdigit():
            idx = int(part)
            current = current[idx] if 0 <= idx < len(current) else _MISSING
        else:
            return _MISSING
    return current


_MISSING = object()


def _match_rule(rule: PolicyRule, params: dict[str, Any]) -> bool:
    """检查 params 是否满足某条规则。"""
    actual = _get_nested_field(params, rule.field)

    if rule.operator == RuleOperator.EXISTS:
        return actual is not _MISSING and actual is not None and actual != ""

    if rule.operator == RuleOperator.NOT_EXISTS:
        return actual is _MISSING or actual is None or actual == ""

    if actual is _MISSING:
        return False  # 字段不存在时规则不触发

    try:
        if rule.operator == RuleOperator.EQ:
            return actual == rule.value
        elif rule.operator == RuleOperator.NEQ:
            return actual != rule.value
        elif rule.operator == RuleOperator.GT:
            return actual > rule.value
        elif rule.operator == RuleOperator.GTE:
            return actual >= rule.value
        elif rule.operator == RuleOperator.LT:
            return actual < rule.value
        elif rule.operator == RuleOperator.LTE:
            return actual <= rule.value
        elif rule.operator == RuleOperator.IN:
            if not isinstance(rule.value, (list, tuple, set)):
                return False
            return actual in rule.value
        elif rule.operator == RuleOperator.NOT_IN:
            if not isinstance(rule.value, (list, tuple, set)):
                return False
            return actual not in rule.value
        elif rule.operator == RuleOperator.STARTSWITH:
            return isinstance(actual, str) and actual.startswith(str(rule.value))
        elif rule.operator == RuleOperator.CONTAINS:
            return str(rule.value) in str(actual)
        else:
            return False
    except (TypeError, ValueError):
        return False


def _evaluate_policy(policy: Policy, params: dict[str, Any]) -> bool:
    """判断策略是否针对给定 params 触发。（规则 AND 语义）"""
    if not policy.enabled:
        return False  # 禁用策略不触发
    if not policy.rules:
        return True   # 无规则时默认触发
    return all(_match_rule(r, params) for r in policy.rules)


# ── 默认安全策略 ─────────────────────────────────────────────────────────────

def _default_policies() -> list[Policy]:
    """返回内置默认安全策略。"""
    return [
        Policy(
            name="unknown-action-type",
            description="拒绝未注册的 action_type",
            priority=100,
            effect=PolicyEffect.DENY,
            action_type_pattern="*",
            rules=(
                PolicyRule(
                    field="action_type",
                    operator=RuleOperator.NOT_IN,
                    value=[  # 白名单：仅允许已知 action_type
                        "execute_engine",
                        "schedule_task",
                        "update_policy",
                        "request_resource",
                        "adjust_parameter",
                        "store_memory",
                        "retrieve_memory",
                        "emit_observation",
                        "set_goal",
                        "complete_goal",
                        "form_decision",
                        "cancel_schedule",
                        "reset_scheduler",
                        "emergency_recover",
                    ],
                    effect=PolicyEffect.DENY,
                    description="action_type 不在白名单中",
                ),
            ),
        ),
        Policy(
            name="constitution-protect",
            description="禁止修改宪法级对象（Constitution/Event Schema/ABI）",
            priority=90,
            effect=PolicyEffect.DENY,
            action_type_pattern="execute_engine",
            rules=(
                PolicyRule(
                    field="target_module",
                    operator=RuleOperator.IN,
                    value=["kernel.constitution", "kernel.abi", "kernel.event_schema"],
                    effect=PolicyEffect.DENY,
                    description="禁止写入宪法/ABI/Event Schema",
                ),
            ),
        ),
        Policy(
            name="decision-required",
            description="决策型动作必须携带有效的 decision_id",
            priority=80,
            effect=PolicyEffect.DENY,
            action_type_pattern="execute_engine",
            rules=(
                PolicyRule(
                    field="decision_id",
                    operator=RuleOperator.NOT_EXISTS,
                    effect=PolicyEffect.DENY,
                    description="execute_engine 必须引用 Decision",
                ),
            ),
        ),
        Policy(
            name="no-emergency-override",
            description="不允许在 emergency halt 后执行非恢复动作",
            priority=95,
            effect=PolicyEffect.DENY,
            action_type_pattern="*",
            rules=(
                PolicyRule(
                    field="system_state",
                    operator=RuleOperator.EQ,
                    value="emergency_halt",
                    effect=PolicyEffect.DENY,
                    description="系统处于紧急停止状态",
                ),
                PolicyRule(
                    field="action_type",
                    operator=RuleOperator.NOT_IN,
                    value=["emergency_recover", "emit_observation"],
                    effect=PolicyEffect.DENY,
                    description="紧急状态下仅允许恢复和观察动作",
                ),
            ),
        ),
        Policy(
            name="action-rate-limit",
            description="同类型动作频率限制（每分钟不超过 60 次）",
            priority=70,
            effect=PolicyEffect.DENY,
            action_type_pattern="*",
            rules=(
                PolicyRule(
                    field="_internal_rate_exceeded",
                    operator=RuleOperator.EQ,
                    value=True,
                    effect=PolicyEffect.DENY,
                    description="动作频率超限",
                ),
            ),
        ),
    ]


# ── PolicyEngine ─────────────────────────────────────────────────────────────

class PolicyEngine:
    """策略引擎：评估动作合规性。

    工作流：
        1. 加载默认安全策略
        2. 接收 evaluate(action_type, params) 调用
        3. 按优先级依次评估所有启用的策略
        4. 返回 PolicyResult（allowed + 违规信息）
        5. 订阅 Governance 事件，支持动态策略更新
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        auto_load_defaults: bool = True,
    ):
        self._policies: dict[str, Policy] = {}
        self._event_bus = event_bus
        self._subscription_ids: list[str] = []
        self._evaluation_count: int = 0
        self._last_action_timestamps: dict[str, list[str]] = {}  # action_type -> [timestamp]

        if auto_load_defaults:
            self.load_default_policies()

        if event_bus is not None:
            self._subscribe_governance()

        logger.debug(
            "PolicyEngine initialized: policies=%d, event_bus=%s, auto_load=%s",
            len(self._policies), event_bus is not None, auto_load_defaults,
        )

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def policy_count(self) -> int:
        return len(self._policies)

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    # ── 策略管理 ────────────────────────────────────────────────────────────

    def load_default_policies(self) -> None:
        """加载默认安全策略。"""
        for policy in _default_policies():
            self._policies[policy.policy_id] = policy
        logger.info("Loaded %d default policies", len(self._policies))

    def add_policy(self, policy: Policy) -> str:
        """添加策略。返回 policy_id。"""
        self._policies[policy.policy_id] = policy
        logger.info("Policy added: id=%s name=%s effect=%s",
                     policy.policy_id, policy.name, policy.effect.value)
        return policy.policy_id

    def remove_policy(self, policy_id: str) -> bool:
        """移除策略。返回是否找到。"""
        found = self._policies.pop(policy_id, None) is not None
        if found:
            logger.info("Policy removed: id=%s", policy_id)
        else:
            logger.warning("Policy not found for removal: id=%s", policy_id)
        return found

    def get_policy(self, policy_id: str) -> Policy | None:
        """获取策略。"""
        return self._policies.get(policy_id)

    def get_policy_by_name(self, name: str) -> Policy | None:
        """按名称查找策略。"""
        for p in self._policies.values():
            if p.name == name:
                return p
        return None

    def set_policy_enabled(self, policy_id: str, enabled: bool) -> bool:
        """启用/禁用策略。返回是否找到。"""
        policy = self._policies.get(policy_id)
        if policy is None:
            return False
        # frozen dataclass 不能直接修改，重新创建
        new_policy = Policy(
            policy_id=policy.policy_id,
            name=policy.name,
            description=policy.description,
            rules=policy.rules,
            effect=policy.effect,
            enabled=enabled,
            priority=policy.priority,
            action_type_pattern=policy.action_type_pattern,
            created_at=policy.created_at,
            schema_version=policy.schema_version,
        )
        self._policies[policy_id] = new_policy
        logger.info("Policy %s: id=%s name=%s", "enabled" if enabled else "disabled",
                     policy_id, policy.name)
        return True

    def list_policies(self) -> list[Policy]:
        """列出所有策略（按优先级排序）。"""
        return sorted(
            self._policies.values(),
            key=lambda p: (-p.priority, p.name),
        )

    # ── 核心评估 ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        action_type: str,
        params: dict[str, Any] | None = None,
    ) -> PolicyResult:
        """评估一个动作是否合规。

        Args:
            action_type: 动作类型（如 "execute_engine"）
            params: 动作参数字典

        Returns:
            PolicyResult: 评估结果
        """
        params = params or {}
        self._evaluation_count += 1
        logger.info("Evaluate: action_type=%s params=%s", action_type, params)

        # 注入内部参数（供规则匹配用）
        resolved_params = dict(params)
        resolved_params["action_type"] = action_type

        # 检查频率限制
        if self._check_rate_exceeded(action_type):
            resolved_params["_internal_rate_exceeded"] = True

        # 按优先级（降序）+ ALLOW 优先于 DENY 遍历所有启用的策略
        sorted_policies = sorted(
            self._policies.values(),
            key=lambda p: (
                -p.priority,
                0 if p.effect == PolicyEffect.ALLOW else 1,
                p.name,
            ),
        )

        violated: list[str] = []

        for policy in sorted_policies:
            if not policy.enabled:
                continue
            if not policy.matches_action_type(action_type):
                continue
            if _evaluate_policy(policy, resolved_params):
                # 策略触发
                if policy.effect == PolicyEffect.DENY:
                    violated.append(f"{policy.name}: {policy.description}")
                    # 记录本次动作时间（便于后续频率检查）
                    self._record_action(action_type)
                    return PolicyResult(
                        allowed=False,
                        reason=f"Policy violated: {policy.name} — {policy.description}",
                        violated_rules=tuple(violated),
                        policy_count=len(self._policies),
                    )
                elif policy.effect == PolicyEffect.ALLOW:
                    # 显式允许 — 跳过后续 DENY 策略
                    self._record_action(action_type)
                    return PolicyResult(
                        allowed=True,
                        reason=f"Explicitly allowed by policy: {policy.name}",
                        policy_count=len(self._policies),
                    )

        # 记录动作
        self._record_action(action_type)

        return PolicyResult(
            allowed=True,
            reason="No policy violated",
            policy_count=len(self._policies),
        )

    # ── 频率限制 ────────────────────────────────────────────────────────────

    def _check_rate_exceeded(self, action_type: str) -> bool:
        """检查同类型动作是否超限（每分钟 ≤ 60 次）。"""
        now_ts = datetime.now(timezone.utc).timestamp()
        timestamps = self._last_action_timestamps.get(action_type, [])

        # 清理一分钟前的记录
        cutoff = now_ts - 60.0
        recent = [t for t in timestamps if t > cutoff]

        # 如果清理后仍超过上限，超限
        exceeded = len(recent) > 60
        if exceeded:
            logger.warning("Rate limit exceeded for action_type=%s: %d in last minute",
                            action_type, len(recent))
        return exceeded

    def _record_action(self, action_type: str) -> None:
        """记录一次动作执行的时间（Unix 时间戳）。"""
        now_ts = datetime.now(timezone.utc).timestamp()
        if action_type not in self._last_action_timestamps:
            self._last_action_timestamps[action_type] = []
        self._last_action_timestamps[action_type].append(now_ts)

        # 定期清理旧记录（只保留最近 1 分钟内）
        cutoff = now_ts - 60.0
        self._last_action_timestamps[action_type] = [
            t for t in self._last_action_timestamps[action_type]
            if t > cutoff
        ]

    @staticmethod
    def _ts_to_unix(iso_ts: str) -> float:
        """将 ISO 时间戳转换为 Unix 时间戳。"""
        try:
            dt = datetime.fromisoformat(iso_ts)
            return dt.timestamp()
        except (ValueError, TypeError):
            return 0.0

    # ── Governance 事件集成 ─────────────────────────────────────────────────

    def _subscribe_governance(self) -> None:
        """订阅 Governance 事件，支持动态策略更新。"""
        if self._event_bus is None:
            logger.debug("No event bus, skipping governance subscription")
            return

        logger.debug("Subscribing to governance events")
        sid_approved = self._event_bus.subscribe(
            EventType.GOVERNANCE_APPROVED,
            self._on_governance_approved,
            subscriber_id="policy-engine-governance-approved",
        )
        self._subscription_ids.append(sid_approved)

        sid_rejected = self._event_bus.subscribe(
            EventType.GOVERNANCE_REJECTED,
            self._on_governance_rejected,
            subscriber_id="policy-engine-governance-rejected",
        )
        self._subscription_ids.append(sid_rejected)

    def _on_governance_approved(self, event: Event) -> None:
        """Governance 批准事件回调：添加/启用策略。"""
        payload = event.payload
        action = payload.get("policy_action", "")
        logger.info("Governance approved: action=%s event_id=%s", action, event.event_id)

        if action == "add":
            policy_data = payload.get("policy", {})
            policy = Policy(
                name=policy_data.get("name", "governance-policy"),
                description=policy_data.get("description", ""),
                rules=tuple(
                    PolicyRule(
                        field=r.get("field", ""),
                        operator=RuleOperator(r.get("operator", "eq")),
                        value=r.get("value"),
                        effect=PolicyEffect(r.get("effect", "deny")),
                        description=r.get("description", ""),
                    )
                    for r in policy_data.get("rules", [])
                ),
                effect=PolicyEffect(policy_data.get("effect", "deny")),
                priority=policy_data.get("priority", 50),
                action_type_pattern=policy_data.get("action_type_pattern", "*"),
            )
            self.add_policy(policy)

        elif action == "enable":
            policy_name = payload.get("policy_name", "")
            policy = self.get_policy_by_name(policy_name)
            if policy:
                self.set_policy_enabled(policy.policy_id, True)

    def _on_governance_rejected(self, event: Event) -> None:
        """Governance 拒绝事件回调：禁用/移除策略。"""
        payload = event.payload
        action = payload.get("policy_action", "")
        logger.info("Governance rejected: action=%s event_id=%s", action, event.event_id)

        if action == "disable":
            policy_name = payload.get("policy_name", "")
            policy = self.get_policy_by_name(policy_name)
            if policy:
                self.set_policy_enabled(policy.policy_id, False)

        elif action == "remove":
            policy_name = payload.get("policy_name", "")
            policy = self.get_policy_by_name(policy_name)
            if policy:
                self.remove_policy(policy.policy_id)

    def unsubscribe_governance(self) -> None:
        """取消 Governance 订阅。"""
        for sid in self._subscription_ids:
            if self._event_bus:
                self._event_bus.unsubscribe(sid)
        self._subscription_ids.clear()

    def reset(self) -> None:
        """重置策略引擎（清除所有策略和状态）。"""
        self._policies.clear()
        self._last_action_timestamps.clear()
        self._evaluation_count = 0
        logger.info("PolicyEngine reset")
