"""R4-A: DecisionBridge — 自治循环决策 → 真实任务执行的铰链。

"一个铰链,两条回路" 的执行回路侧:
  AgentRuntime.tick step 7 (core_loop 决策 / TaskDAG 任务)
      ↓  step 8 Dispatch
  DecisionBridge.process(core_loop_result) / execute_dag_task(task)
      ↓
  ① interpret_decision → DispatchedAction 列表
  ② 风险分级 (AUTO / ASK / DENY) + PermissionGuard 语义双检
      AUTO → action_dispatcher.dispatch → capability_reality 真实执行 → ExecutionAudit
      ASK  → 记录 pending (R4-B 接 Outbox 待批)
      DENY → 拒绝记录
  ③ 全部落 ExecutionAudit 审计

冻结面 (零改动):
  - action_dispatcher / capability_reality 核心逻辑 — 只注册 handler、只调用
  - constitution / ProactiveEngine / attention_abi — 不触碰
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.autonomous_runtime.action_dispatcher import (
    ActionDispatcher,
    ActionType,
    DispatchedAction,
)
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.interaction.base import PermissionGuard, ALLOWED_ACTIONS

logger = logging.getLogger(__name__)

# ── 风险分级表 (设计冻结: 低危 AUTO / 中危 ASK / 禁区 DENY) ──────────────
AUTO_ACTIONS: frozenset[ActionType] = frozenset({
    ActionType.CONSOLIDATE_MEMORY,   # 记忆整理 (fs 只读/内部)
    ActionType.HEALTH_CHECK,         # 健康检查 (fs stat / registry 汇总)
    ActionType.REFLECT,              # 反思 (内部记录)
    ActionType.FEEDBACK_PROCESS,     # 反馈处理 (内部记录)
    ActionType.NOOP,                 # 空操作
})

ASK_ACTIONS: frozenset[ActionType] = frozenset({
    ActionType.WRITE_CHAPTER,        # OpenTale 写章节 (中危, 可配置)
    ActionType.SEARCH_WEB,           # 网络检索 (中危)
    ActionType.RUN_COMMAND,          # PW-4.1: 沙盒命令 (黑/白名单闸门后真实执行)
    ActionType.HTTP_FETCH,           # PW-4.1: 白名单 URL 抓取
})

DENY_ACTIONS: frozenset[ActionType] = frozenset()
# 注: 未来若引入 shell/HTTP 类高危 ActionType，其 ASK 批准后的执行层
# 候选为 ocos/operations/（黑白名单闸门，AUD-F5 裁决），非 digital_world/。

# ActionType → 交互层语义动作 (PermissionGuard 双检映射)
# 注 1: 语义双检只在 AUTO 路径触达 (_adjudicate 中 ASK 类提前进入待批,
#       永远走不到这里) — 因此不给 ASK 类动作配语义, 避免读语义伪装放行写操作。
# 注 2: CONSOLIDATE_MEMORY/REFLECT/FEEDBACK_PROCESS 虽映射读语义, 其 handler
#       会写 ~/.ocos/executions/ 沙盒内文件 — 该 AUTO 写豁免已登记于
#       docs/EVOLUTION_CONSTRAINED_AUTONOMY_20260820.md §二。
ACTION_SEMANTICS: dict[ActionType, str] = {
    ActionType.HEALTH_CHECK: "view_self",
    ActionType.REFLECT: "view_trace",
    ActionType.CONSOLIDATE_MEMORY: "query_memory",
    ActionType.FEEDBACK_PROCESS: "analyze_quality",
    ActionType.NOOP: "view_self",
}

# DAG 任务类型 → 执行策略 (R4-A 只真实执行只读类; 写/shell 类进 ASK 待批)
_DAG_AUTO_TYPES = ("analyze", "verify")
_DAG_ASK_TYPES = ("create", "modify", "execute")


@dataclass
class ActionVerdict:
    """单个动作的裁决结果。"""
    action_type: str
    verdict: str                    # auto | ask | deny
    reason: str = ""
    status: str = ""                # dispatched status: done | failed | pending | denied
    summary: str = ""


@dataclass
class BridgeReport:
    """一次 process() 的执行汇总 (审计可见)。"""
    processed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = ""                # core_loop | dag_task | manual
    decision_text: str = ""
    verdicts: list[ActionVerdict] = field(default_factory=list)

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for v in self.verdicts:
            counts[v.verdict] = counts.get(v.verdict, 0) + 1
        return {
            "source": self.source,
            "total": len(self.verdicts),
            "by_verdict": counts,
            "executed": [v.action_type for v in self.verdicts
                         if v.verdict == "auto" and v.status == "done"],
            "pending": [v.action_type for v in self.verdicts if v.verdict == "ask"],
            "denied": [v.action_type for v in self.verdicts if v.verdict == "deny"],
        }


class DecisionBridge:
    """决策铰链 — 把自治决策接到 capability_reality 真实执行。"""

    def __init__(
        self,
        dispatcher: Optional[ActionDispatcher] = None,
        guard: Optional[PermissionGuard] = None,
        audit: Optional[ExecutionAudit] = None,
        agent_id: str = "decision_bridge",
        pending_store: Optional[Any] = None,    # AUD-F12: PendingStore (SQLite 持久化)
    ) -> None:
        self._dispatcher = dispatcher or ActionDispatcher()
        self._guard = guard or PermissionGuard()
        self._audit = audit or ExecutionAudit()
        self._agent_id = agent_id
        self._registry: Any = None
        self._pending_store = pending_store     # AUD-F12: 有 store 则跨进程存活
        self._pending: list[dict] = []          # 无 store 时的内存回退（诚实降级）
        self._reports: list[BridgeReport] = []

    # ── 装配 ──────────────────────────────────────────────────────────────

    def attach_default_handlers(self, registry: Any = None) -> "DecisionBridge":
        """把 capability_reality 发现的能力注册为 dispatcher 真实执行器。

        registry 为 None 时自动运行 AdapterDiscovery 扫描 (CR55-04:
        不假设能力存在 — 只注册环境真实可用的能力)。
        """
        if registry is None:
            from ocos.capability_reality.adapter_discovery import AdapterDiscovery
            discovery = AdapterDiscovery()
            registry, _report = discovery.run()
        self._registry = registry

        self._dispatcher.register_handler(
            ActionType.HEALTH_CHECK, self._handler_health_check)
        self._dispatcher.register_handler(
            ActionType.CONSOLIDATE_MEMORY, self._handler_consolidate)
        self._dispatcher.register_handler(
            ActionType.REFLECT, self._handler_reflect)
        self._dispatcher.register_handler(
            ActionType.FEEDBACK_PROCESS, self._handler_feedback)
        self._dispatcher.register_handler(
            ActionType.NOOP, self._handler_noop)
        self._dispatcher.register_handler(
            ActionType.RUN_COMMAND, self._handler_run_command)
        self._dispatcher.register_handler(
            ActionType.HTTP_FETCH, self._handler_http_fetch)
        # D: 自我升级提案的人工批准执行器（字符串 action_type, 经
        # dispatch_by_name 触达 — 批准即应用, 人工 = authority）
        self._dispatcher.register_custom_handler(
            "self_upgrade", self._handler_self_upgrade)
        return self

    # ── 决策执行入口 ──────────────────────────────────────────────────────

    def process(self, core_loop_result: dict, attention_focus: str = "") -> BridgeReport:
        """处理一次 core_loop 决策输出 (step 7 → step 8 调用)。

        提取决策文本 → interpret → 分级 → AUTO 执行 → 审计。
        """
        report = BridgeReport(source="core_loop")

        text = self._extract_decision_text(core_loop_result)
        report.decision_text = text
        if not text:
            return report

        actions = self._dispatcher.interpret_decision(text, attention_focus)
        self._supplement_interpretation(text, actions)
        for action in actions:
            verdict = self._adjudicate(action)
            v = ActionVerdict(
                action_type=action.action_type.name,
                verdict=verdict[0],
                reason=verdict[1],
            )
            if verdict[0] == "auto":
                dispatched = self._dispatcher.dispatch(
                    action.action_type, action.target, action.payload)
                v.status = dispatched.status
                v.summary = self._summarize(dispatched)
                self._audit_action(dispatched)
            elif verdict[0] == "ask":
                v.status = "pending"
                self._enqueue_pending(
                    action_type=action.action_type.name,
                    target=action.target,
                    payload=action.payload,
                    text=text,
                )
                logger.info("DecisionBridge: %s queued for approval (R4-B Outbox)",
                            action.action_type.name)
            else:
                v.status = "denied"
                logger.warning("DecisionBridge: %s denied — %s",
                               action.action_type.name, verdict[1])
            report.verdicts.append(v)

        self._reports.append(report)
        return report

    def execute_dag_task(self, task: Any) -> dict:
        """TaskDAG 任务 → 真实执行 (R4-A: 只读类 AUTO, 写/shell 类 ASK 待批)。

        EchoAgent 保留为无能力匹配时的回退 (既有行为不破坏)。
        """
        task_type = getattr(task, "task_type", "execute")
        description = getattr(task, "description", "")

        if task_type in _DAG_ASK_TYPES:
            # 写文件 / shell 执行 = 高危 → 待批 (R4-B Outbox)
            self._enqueue_pending(
                action_type=f"dag_{task_type}",
                target="dag_task",
                payload={"task_id": getattr(task, "task_id", ""),
                         "description": description},
                text=description,
            )
            return {"status": "pending_approval",
                    "reason": "high-risk DAG task requires approval (R4-B)"}

        if task_type in _DAG_AUTO_TYPES:
            # 只读分析/验证 → 真实执行 (fs stat/read 或 registry 健康)
            result = self._dag_readonly_execute(description)
            if result is not None:
                if result.get("ok"):
                    self._audit_record(
                        contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                        status="completed",
                        summary=f"dag_{task_type}: {str(result.get('output', ''))[:200]}",
                    )
                    return {"status": "completed", "result": result}
                # 执行器失败 → 诚实失败 (不伪装 completed, 不静默回退 echo)
                self._audit_record(
                    contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                    status="failed",
                    summary=f"dag_{task_type}: {str(result.get('error', ''))[:200]}",
                )
                return {"status": "failed", "result": result}

        return {"status": "echo_fallback"}      # 无能力匹配 → 既有 EchoAgent 行为

    # ── 裁决 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _supplement_interpretation(text: str, actions: list[DispatchedAction]) -> None:
        """dispatcher 只识别 write/research/reflect 三类关键字 (冻结面零改动);
        bridge 在其落 NOOP 时补充 health/consolidate 识别。"""
        if not any(a.action_type is ActionType.NOOP for a in actions):
            return
        low = text.lower()
        if any(k in low for k in ("health check", "system health", "health monitor")):
            actions[:] = [DispatchedAction(
                ActionType.HEALTH_CHECK, "system", {"prompt": text[:200]})]
        elif any(k in low for k in ("consolidat", "organize memory")):
            actions[:] = [DispatchedAction(
                ActionType.CONSOLIDATE_MEMORY, "memory", {"prompt": text[:200]})]
        elif any(k in low for k in ("run command", "执行命令", "跑一下", "运行命令")):
            # PW-4.1: 命令文本从消息中提取（`...` 反引号优先, 否则整句）
            import re as _re
            m = _re.search(r"`([^`]+)`", text)
            command = m.group(1).strip() if m else text[:200]
            actions[:] = [DispatchedAction(
                ActionType.RUN_COMMAND, "sandbox",
                {"command": command, "prompt": text[:200]})]

    def _adjudicate(self, action: DispatchedAction) -> tuple[str, str]:
        """风险分级 + PermissionGuard 语义双检。返回 (verdict, reason)。"""
        # 1. 禁区
        if action.action_type in DENY_ACTIONS:
            return "deny", f"action {action.action_type.name} in DENY list"

        # 2. 中危 → ASK 待批 (R4-B)
        if action.action_type in ASK_ACTIONS:
            return "ask", f"action {action.action_type.name} requires approval (R4-B Outbox)"

        # 3. AUTO 路径: PermissionGuard 语义双检
        semantic = ACTION_SEMANTICS.get(action.action_type)
        if semantic is not None:
            result = self._guard.check(semantic, {
                "caller": "autonomous_loop", "source": "self",
            })
            if not result.allowed:
                return "deny", f"permission denied for {semantic}: {result.violations}"

        if action.action_type in AUTO_ACTIONS:
            return "auto", f"action {action.action_type.name} is low-risk"

        return "ask", f"action {action.action_type.name} not classified"

    # ── 真实执行器 (handler, 全部走 capability_reality 沙盒) ──────────────

    def _handler_health_check(self, action: DispatchedAction) -> dict:
        """健康检查 — fs 只读探测 + registry 健康汇总 (真实执行)。"""
        if self._registry is None:
            return {"error": "no capability registry attached"}
        fs_result = self._exec_fs("stat", os.path.expanduser("~"))
        return {
            "healthy": fs_result.get("ok", False),
            "filesystem": fs_result,
            "capabilities_total": self._registry.count(),
            "capabilities_healthy": self._registry.healthy_count(),
        }

    def _handler_consolidate(self, action: DispatchedAction) -> dict:
        """记忆整理 — 写 consolidation 快照到 ~/.ocos/executions/ (真实执行)。"""
        payload = {"kind": "consolidation",
                   "topic": action.payload.get("topic", action.payload.get("prompt", ""))[:200],
                   "reason": "autonomous memory consolidation"}
        return self._exec_fs("write", self._exec_path("consolidation"), json.dumps(payload, ensure_ascii=False))

    def _handler_reflect(self, action: DispatchedAction) -> dict:
        """反思 — 写 reflection 记录 (真实执行)。"""
        payload = {"kind": "reflection",
                   "topic": action.payload.get("topic", "")[:200],
                   "prompt": action.payload.get("prompt", "")[:500]}
        return self._exec_fs("write", self._exec_path("reflection"), json.dumps(payload, ensure_ascii=False))

    def _handler_feedback(self, action: DispatchedAction) -> dict:
        """反馈处理 — 写 feedback 记录 (真实执行)。"""
        payload = {"kind": "feedback",
                   "content": action.payload.get("prompt", "")[:500]}
        return self._exec_fs("write", self._exec_path("feedback"), json.dumps(payload, ensure_ascii=False))

    def _handler_noop(self, action: DispatchedAction) -> dict:
        return {"noop": True, "reason": action.payload.get("reason", "")}

    def _handler_run_command(self, action: DispatchedAction) -> dict:
        """PW-4.1: 沙盒命令真实执行 — operations/SandboxOps 闸门。

        四重防护: 命令黑名单（永久拦截）→ 白名单（最小集）→ 路径沙盒
        → 审计。仅经 ASK 人工批准后触达。
        """
        command = (action.payload or {}).get("command", "")
        if not command:
            return {"ok": False, "error": "empty command"}
        try:
            import os as _os
            from ocos.operations.sandbox_ops import SandboxCommand, SandboxOps
            workdir = "/tmp/ocos_sandbox"
            _os.makedirs(workdir, exist_ok=True)  # 沙盒工作目录（SandboxOps 不自建）
            result = SandboxOps(strict=True).execute(
                SandboxCommand(command=command, workdir=workdir, timeout=30.0))
            return {"ok": result.success, "blocked": result.blocked,
                    "block_reason": result.block_reason,
                    "exit_code": result.exit_code,
                    "stdout": (result.stdout or "")[:500],
                    "stderr": (result.stderr or "")[:300]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handler_http_fetch(self, action: DispatchedAction) -> dict:
        """PW-4.1: 白名单 URL 抓取 — operations/SearchOps。"""
        payload = action.payload or {}
        url = payload.get("url", "")
        if not url:
            return {"ok": False, "error": "empty url"}
        try:
            from ocos.operations.search_ops import SearchOps, SearchQuery
            result = SearchOps().search(SearchQuery(
                query=payload.get("query", url), url=url,
                params=payload.get("params", {}) or {}, timeout=10.0))
            return {"ok": result.success, "status_code": result.status_code,
                    "results": result.results[:10], "error": result.error}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handler_self_upgrade(self, action: DispatchedAction) -> dict:
        """D: 应用已批准的自我升级 — 追加到 ~/.ocos/self_knowledge.md。

        人工批准 = authority（宪法禁 modify_self 的自主路径, 但主人显式
        批准的提案例外）。下次 ChatResponder 构建提示词时生效。
        """
        from ocos.interaction.converse import ChatResponder
        change = (action.payload or {}).get("change", "")
        if not change:
            return {"ok": False, "error": "empty change payload"}
        applied = ChatResponder.apply_self_upgrade(change)
        return {"ok": True, "applied": applied}

    # ── capability_reality 调用 ───────────────────────────────────────────

    def _exec_fs(self, operation: str, path: str, content: str = "") -> dict:
        """通过 registry 中真实发现的 filesystem 能力执行 (沙盒, safe_roots 约束)。"""
        if self._registry is None:
            return {"ok": False, "error": "no capability registry attached"}
        cap = self._registry.get("filesystem")
        if cap is None or cap.executor is None:
            return {"ok": False, "error": "filesystem capability unavailable"}
        from ocos.capability_reality.adapter_types import ExecutionContext
        ctx = ExecutionContext(
            execution_id=f"EXEC-{uuid.uuid4().hex[:8]}",
            capability_name="filesystem",
            params={"operation": operation, "path": path, "content": content},
            sandboxed=True,
            timeout=10.0,
        )
        try:
            # registry 契约: executor 是 Callable (discovery 注册 adapter.execute);
            # 兼容带 .execute 的执行器对象两种形态
            executor = cap.executor
            fn = executor.execute if hasattr(executor, "execute") else executor
            result = fn(ctx)
            return {"ok": result.ok, "output": result.output, "error": result.error}
        except Exception as e:          # noqa: BLE001 — 执行器异常归一化
            return {"ok": False, "error": str(e)}

    def _dag_readonly_execute(self, description: str) -> Optional[dict]:
        """DAG 只读任务真实执行 — 仅当描述显式命中路径时执行 fs stat。

        不做 os.path.exists 兜底 (那会让路径匹配恒真, 任何任务都退化成
        对 home 目录的探测); 无匹配返回 None → 回退既有 EchoAgent 行为。
        """
        desc_lower = description.lower()
        # 按长度降序: 最长(最特异)路径优先, 避免前缀遮蔽
        # (如 /home/laogao 遮蔽 /home/laogao/Documents)
        path_candidates = sorted(
            (p for p in (os.path.expanduser("~"), "/tmp", "/home/laogao/Documents")
             if p and p.lower() in desc_lower),
            key=len, reverse=True,
        )
        if path_candidates:
            return self._exec_fs("stat", path_candidates[0])
        return None

    def _exec_path(self, kind: str) -> str:
        """执行产物落点 (safe root 内: ~/.ocos/executions/)。"""
        base = os.path.join(os.path.expanduser("~"), ".ocos", "executions")
        os.makedirs(base, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return os.path.join(base, f"{kind}-{ts}-{uuid.uuid4().hex[:6]}.json")

    # ── 审计 ──────────────────────────────────────────────────────────────

    def _audit_action(self, dispatched: DispatchedAction) -> None:
        contract_id = f"BRIDGE-{uuid.uuid4().hex[:8]}"
        if dispatched.status == "done":
            self._audit.log_complete(
                contract_id, self._agent_id,
                f"{dispatched.action_type.name}: {self._summarize(dispatched)[:200]}",
            )
        else:
            self._audit.log_failure(
                contract_id, self._agent_id, str(dispatched.result)[:200],
            )

    def _audit_record(self, contract_id: str, status: str, summary: str) -> None:
        if status == "completed":
            self._audit.log_complete(contract_id, self._agent_id, summary)
        else:
            self._audit.log_failure(contract_id, self._agent_id, summary)

    @staticmethod
    def _summarize(dispatched: DispatchedAction) -> str:
        if isinstance(dispatched.result, dict):
            return json.dumps(dispatched.result, ensure_ascii=False)[:200]
        return str(dispatched.result)[:200]

    @staticmethod
    def _extract_decision_text(core_loop_result: dict) -> str:
        """从 core_loop result 提取决策文本 (递归取 based_on)。"""
        ar = core_loop_result.get("action_result") or {}
        based = ar.get("based_on") or core_loop_result.get("based_on")
        if isinstance(based, str):
            return based
        if isinstance(based, dict):
            for key in ("message", "thought", "content", "text", "summary"):
                val = based.get(key)
                if isinstance(val, str) and val:
                    return val
            return DecisionBridge._extract_decision_text(based)
        return ""

    # ── 待批队列 ──────────────────────────────────────────────────────────

    def _enqueue_pending(self, action_type: str, target: str,
                         payload: dict, text: str) -> None:
        """入队待批动作 — 有 PendingStore 则持久化，否则内存回退（诚实降级）。"""
        if self._pending_store is not None:
            self._pending_store.enqueue(
                action_type=action_type, target=target,
                payload=payload, text=text, source=self._agent_id,
            )
            return
        self._pending.append({
            "action_type": action_type,
            "target": target,
            "payload": payload,
            "text": text[:200],
            "queued_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── 查询 ──────────────────────────────────────────────────────────────

    @property
    def pending_actions(self) -> list[dict]:
        """待批动作 — 持久化 store 优先，内存回退。"""
        if self._pending_store is not None:
            return self._pending_store.list_by_status("pending")
        return list(self._pending)

    @property
    def recent_reports(self) -> list[BridgeReport]:
        return list(self._reports)

    @property
    def audit_records(self) -> list[Any]:
        return list(self._audit._records) if hasattr(self._audit, "_records") else []

    @property
    def dispatcher(self) -> ActionDispatcher:
        return self._dispatcher


__all__ = [
    "DecisionBridge", "BridgeReport", "ActionVerdict",
    "AUTO_ACTIONS", "ASK_ACTIONS", "DENY_ACTIONS",
]
