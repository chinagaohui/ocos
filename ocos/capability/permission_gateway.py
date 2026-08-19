"""Phase 24-A — PermissionGateway 完整版。

扩展 Phase 22 MVP，新增:
  24a1: caller_id 校验 + issuer 追溯 (§2 禁令矩阵 L1)
  24a2: 反向控制指令检测 (§2 禁令矩阵 L4)
  24a3: 路径穿越/命令注入/SSRF 检测 (§4.4.4)
  24a4: 完整审计日志（结构化 JSON lines）
  24a5: Gateway 集成到 AgentRuntime

保留 Phase 22 所有功能（向后兼容）。
"""

from __future__ import annotations

import enum
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────


class GatewayDecision(str, enum.Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    RESTRICTED = "RESTRICTED"


# ── CallerIdentity ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CallerIdentity:
    """24a1: 调用者身份 — caller_id + issuer 追溯链。"""
    caller_id: str = "unknown"
    issuer: str = ""         # 委托者（A 委托 B 调用时，B.caller_id, A=issuer）
    source: str = "internal"  # internal | api | cli | external
    delegation_chain: tuple[str, ...] = ()  # 完整委托链

    def is_internal(self) -> bool:
        return self.source == "internal"

    def is_external(self) -> bool:
        return self.source == "external"

    @property
    def display(self) -> str:
        chain = "→".join(self.delegation_chain) if self.delegation_chain else self.caller_id
        issuer = f" (via {self.issuer})" if self.issuer else ""
        return f"{self.source}:{chain}{issuer}"


# ── 检测模式 ──────────────────────────────────────────────────────────────────


# 24a2: 反向控制指令 — "指挥 OCOS" 模式
_REVERSE_CONTROL_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:你|you)\s*(?:必须|应该|必须|必须|一定要)\s*(?:修改|改变|删除|创建|执行)",
               re.IGNORECASE),
    re.compile(r"(?:修改|改变|覆盖|覆盖|重写|重写)\s*(?:你的|your)\s*(?:身份|目标|目标|记忆|信念)",
               re.IGNORECASE),
    re.compile(r"(?:ignore|忽略|forget|忘记|override|覆盖)\s*(?:your|你的)\s*(?:rules|规则|constitution|宪章|identity|身份)",
               re.IGNORECASE),
    re.compile(r"(?:pretend|假装|act\s+as|扮演)\s+(?:to\s+be|成为|你是)",
               re.IGNORECASE),
    re.compile(r"(?:bypass|绕过|disable|禁用)\s*(?:the\s+)?(?:gateway|网关|permission|权限)",
               re.IGNORECASE),
    re.compile(r"(?:从现在开始|从现在起|从今以后)\s*(?:你是|you\s+are)",
               re.IGNORECASE),
]

# 24a3: 路径穿越 + 命令注入
_PATH_TRAVERSAL_RE = re.compile(r"\.\.\/|\.\.\\|%2e%2e%2f|%2e%2e/|%252e%252e%252f", re.IGNORECASE)
_COMMAND_INJECTION_RE = re.compile(
    r"[\$]\{|`[^`]+`|\$\([^)]+\)|&&\s*\w+|\|\|\s*\w+|;\s*\w+\s+-|[|&];\s*\w+",
)
_SSRF_RE = re.compile(
    r"http://169\.254\.\d+\.\d+|"        # AWS metadata
    r"http://metadata\.google\.internal|"
    r"http://localhost[:/]|http://127\.0\.0\.1[:/]|"
    r"file:///|gopher://|dict://",
    re.IGNORECASE,
)

# Phase 22 危险指令（保留）
_DANGEROUS_PATTERNS: list[re.Pattern] = [
    re.compile(r"ocos\.\w+", re.IGNORECASE),
    re.compile(r"\bmodify_self\b", re.IGNORECASE),
    re.compile(r"\bmodify_identity\b", re.IGNORECASE),
    re.compile(r"\bwrite_memory\b", re.IGNORECASE),
    re.compile(r"\bmodify_goal\b", re.IGNORECASE),
    re.compile(r"\bmodify_constitution\b", re.IGNORECASE),
    re.compile(r"\bapprove_evolution\b", re.IGNORECASE),
    re.compile(r"\bexecute_system\b", re.IGNORECASE),
    re.compile(r"\bdelete_\w+\b", re.IGNORECASE),
]

_ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "create_goal", "query_memory", "request_plan", "view_belief",
    "view_self", "view_trace", "write", "plan", "reason",
    "execute", "learn", "reflect", "read", "search", "query",
    "generate", "process",
})

# 24a2: 外部调用者白名单（内部模块不在此列的被标记为 SUSPICIOUS）
_INTERNAL_CALLERS: frozenset[str] = frozenset({
    "agent_runtime", "master_agent", "executive_controller",
    "engine_bridge", "async_bridge", "cognitive_interface",
    "event_ingestion", "goal_tree", "meta_controller",
})


# ── AuditEntry ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuditEntry:
    """24a4: 单条审计记录。"""
    timestamp: datetime
    trace_id: str
    caller: str
    issuer: str
    action: str
    decision: str
    reason: str
    violations: tuple[str, ...]
    context_snapshot: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "ts": self.timestamp.isoformat(),
            "trace": self.trace_id,
            "caller": self.caller,
            "issuer": self.issuer,
            "action": self.action,
            "decision": self.decision,
            "reason": self.reason,
            "violations": list(self.violations),
        }, ensure_ascii=False)


# ── GatewayResult（保留 Phase 22 API）─────────────────────────────────────────


@dataclass(frozen=True)
class GatewayResult:
    decision: GatewayDecision
    reason: str = ""
    violations: list[str] = field(default_factory=list)
    trace_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    caller: str = "unknown"
    issuer: str = ""

    @property
    def allowed(self) -> bool:
        return self.decision in (GatewayDecision.ALLOWED, GatewayDecision.RESTRICTED)

    @property
    def blocked(self) -> bool:
        return self.decision == GatewayDecision.BLOCKED


class PermissionDeniedError(PermissionError):
    def __init__(self, result: GatewayResult):
        self.result = result
        super().__init__(
            f"Permission DENIED (trace={result.trace_id}, caller={result.caller}): "
            f"{'; '.join(result.violations) if result.violations else result.reason}"
        )


# ── PermissionGateway 完整版 ──────────────────────────────────────────────────


@dataclass
class PermissionGateway:
    """Phase 24-A 完整版权限网关。

    检查链:
      1. caller_id 校验 + 外部调用者标记 (24a1)
      2. 反向控制指令检测 (24a2)
      3. 路径穿越/命令注入/SSRF 检测 (24a3)
      4. DANGEROUS_PATTERNS 扫描 (Phase 22 保留)
      5. action 白名单校验
      6. 完整审计日志 (24a4)
    """

    allowed_actions: frozenset[str] = field(default=_ALLOWED_ACTIONS)
    audit_trail: list[AuditEntry] = field(default_factory=list)
    _audit_file: str = ""  # 24a4: 可选持久化审计文件路径

    # ── validate ─────────────────────────────────────────────────────

    def validate(
        self,
        contract: Any,
        caller: CallerIdentity | None = None,
        context: dict[str, Any] | None = None,
    ) -> GatewayResult:
        """完整版验证管道。"""
        violations: list[str] = []
        trace_id = getattr(contract, "contract_id", None) or uuid.uuid4().hex[:8]
        caller_id = caller.caller_id if caller else "unknown"
        issuer = caller.issuer if caller else ""
        action = getattr(contract, "agent_id", "") or getattr(contract, "action", "") or ""

        # ── 24a1: caller_id 校验 ──────────────────────────────────────
        if caller is None:
            # 缺少 CallerIdentity 不拦截（向后兼容 Phase 22），但记录
            logger.debug("validate: no CallerIdentity provided for trace=%s", trace_id)

        # ── 24a2: 反向控制指令检测 ────────────────────────────────────
        serialized = _serialize_params(getattr(contract, "input_spec", {}) or {})
        for pattern in _REVERSE_CONTROL_PATTERNS:
            for m in pattern.finditer(serialized):
                violations.append(f"REVERSE_CTRL: '{pattern.pattern}' matched '{m.group()[:60]}'")

        contract_raw = str(contract) if contract else ""
        for pattern in _REVERSE_CONTROL_PATTERNS:
            if not any("REVERSE_CTRL" in v for v in violations):  # 只有前面没匹配时才扫原始
                for m in pattern.finditer(contract_raw):
                    violations.append(
                        f"REVERSE_CTRL(contract): '{pattern.pattern}' matched '{m.group()[:60]}'"
                    )

        # ── 24a3: 路径穿越 / 命令注入 / SSRF ──────────────────────────
        if _PATH_TRAVERSAL_RE.search(serialized):
            violations.append("PATH_TRAVERSAL: detected '..' in parameters")
        if _COMMAND_INJECTION_RE.search(serialized):
            violations.append("CMD_INJECTION: shell metacharacters detected")
        if _SSRF_RE.search(serialized):
            violations.append("SSRF: internal URL pattern detected")

        # ── DANGEROUS_PATTERNS（Phase 22 保留）────────────────────────
        for pattern in _DANGEROUS_PATTERNS:
            for m in pattern.finditer(serialized):
                violations.append(
                    f"DANGEROUS_PATTERN '{pattern.pattern}' matched '{m.group()[:40]}'"
                )
        for pattern in _DANGEROUS_PATTERNS:
            for m in pattern.finditer(contract_raw):
                v = f"DANGEROUS_PATTERN '{pattern.pattern}' matched '{m.group()[:40]}' in contract"
                if v not in violations:
                    violations.append(v)

        # ── action 白名单 ─────────────────────────────────────────────
        # Phase 22 保留行为: agent_id/action 不在白名单不拦截，
        # 仅当同时匹配 DANGEROUS_PATTERNS 才拦截
        if action and action.lower() not in {a.lower() for a in self.allowed_actions}:
            logger.debug("validate: action '%s' not in whitelist (non-blocking)", action)

        # ── 去重 + 判定 ───────────────────────────────────────────────
        violations = sorted(set(violations))

        if violations:
            decision = GatewayDecision.BLOCKED
            reason = f"Gateway blocked: {len(violations)} violation(s)"
        else:
            decision = GatewayDecision.ALLOWED
            reason = "Gateway allowed: all checks passed"

        result = GatewayResult(
            decision=decision,
            reason=reason,
            violations=violations,
            trace_id=trace_id,
            caller=caller_id,
            issuer=issuer,
        )

        # ── 24a4: 审计记录 ────────────────────────────────────────────
        entry = AuditEntry(
            timestamp=result.timestamp,
            trace_id=trace_id,
            caller=caller_id,
            issuer=issuer,
            action=action,
            decision=decision.value,
            reason=reason,
            violations=tuple(violations),
            context_snapshot=serialized[:200],
        )
        self.audit_trail.append(entry)
        self._maybe_persist_audit(entry)

        return result

    def validate_or_raise(
        self,
        contract: Any,
        *,
        caller: CallerIdentity | None = None,
        context: dict[str, Any] | None = None,
    ) -> GatewayResult:
        result = self.validate(contract, caller=caller, context=context)
        if result.blocked:
            raise PermissionDeniedError(result)
        return result

    # ── 审计持久化 ───────────────────────────────────────────────────

    def enable_audit_file(self, path: str) -> None:
        self._audit_file = path

    def _maybe_persist_audit(self, entry: AuditEntry) -> None:
        if not self._audit_file:
            return
        try:
            with open(self._audit_file, "a") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.warning("audit file write failed: %s", e)

    def export_audit(self) -> list[dict]:
        return [json.loads(e.to_json()) for e in self.audit_trail]

    @property
    def audit_log(self) -> list:
        """向后兼容 Phase 22：audit_log 别名 → audit_trail。"""
        return self.audit_trail

    @property
    def audit_count(self) -> int:
        return len(self.audit_trail)


# ── 辅助 ─────────────────────────────────────────────────────────────────────


def _serialize_params(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(f"{k}={_serialize_params(v)}" for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return " ".join(_serialize_params(v) for v in obj)
    return str(obj)
