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

import asyncio
import json
import logging
import os
import re
import uuid
from types import SimpleNamespace
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ocos.autonomous_runtime.action_dispatcher import (
    ActionDispatcher,
    ActionType,
    DispatchedAction,
)
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.interaction.base import PermissionGuard, ALLOWED_ACTIONS
from ocos.execution.pending import approval_disabled

logger = logging.getLogger(__name__)

# ── P0-1/P1-1 (2026-09-08 事件复盘): 创作/分析类任务判定 ─────────────────
# 事件链: 「制定升级计划」目标 → 规划 LLM 输出 ANSWER|<计划正文> → 旧闸门
# 裸词「验证」命中描述末尾的"验证标准" → 误判执行意图 → 强制重试 → LLM 被
# 迫交出 cat --version 式噪声探针（受注入的「只读示例: <cli> --version」
# 话术引导）→ exit 0 → ✓ 成功，计划正文整体丢弃。
# 创作类任务的天然交付物是 ANSWER 正文（或 LLM 自主 FILE_WRITE），
# 不应被强制 RUN，也不应注入智能体清单样例话术（跑偏磁铁）。
_AUTHORING_ANALYSIS_RE = re.compile(
    r"总结|复盘|分析|自省|反思|回顾|归纳|自检报告|"
    r"制定|编制|起草|撰写|编写|规划|设计|计划|方案|蓝图|路线图")
# 创作交付类（要求正文交付物）— 瘦 ANSWER 门槛只对这类生效；
# 纯分析/复盘类（总结/反思/回顾）短结论合法，不设门槛（UX-J+ 不回归）
_AUTHORING_DELIVERABLE_RE = re.compile(
    r"制定|编制|起草|撰写|编写|计划|方案|蓝图|路线图")

# ── 风险分级表 (设计冻结: 低危 AUTO / 中危 ASK / 禁区 DENY) ──────────────
AUTO_ACTIONS: frozenset[ActionType] = frozenset({
    ActionType.CONSOLIDATE_MEMORY,   # 记忆整理 (fs 只读/内部)
    ActionType.HEALTH_CHECK,         # 健康检查 (fs stat / registry 汇总)
    ActionType.REFLECT,              # 反思 (内部记录)
    ActionType.FEEDBACK_PROCESS,     # 反馈处理 (内部记录)
    ActionType.NOOP,                 # 空操作
    ActionType.QUERY_DB,             # P2-1: 只读 SQLite 查询 (系统自检/数据分析)
})

ASK_ACTIONS: frozenset[ActionType] = frozenset({
    ActionType.WRITE_CHAPTER,        # OpenTale 写章节 (中危, 可配置)
    ActionType.SEARCH_WEB,           # 网络检索 (中危)
    ActionType.RUN_COMMAND,          # PW-4.1: 沙盒命令 (黑/白名单闸门后真实执行)
    ActionType.HTTP_FETCH,           # PW-4.1: 白名单 URL 抓取
    ActionType.FILE_WRITE,           # S1.1: 文件写入 — 强制审批（不受 APPROVAL_MODE 影响）
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
        db_path: Optional[str] = None,          # PW-1.4: 执行留痕 event_memory
        permission_gateway: Optional[Any] = None,  # S3.2: 入口网关前检（None→惰性默认）
        learning_source: Optional[Any] = None,  # P1.2: 学习产物检索源（None→无注入）
        world_source: Optional[Any] = None,  # P2.1: 世界状态检索源（None→无注入）
        agent_source: Optional[Any] = None,  # AGI: 智能体软件检索源（None→无注入）
        installer: Optional[Any] = None,  # AGI: 智能体安装执行器 fn(name)->result（None→禁安装）
        autonomous_goal_sink: Optional[Any] = None,  # L3: 自主目标落地 fn(payload)（None→待批提案无法执行）
        constitution_sink: Optional[Any] = None,  # L4-1: 宪法版本落库 fn(payload)（None→修改提案无法应用）
    ) -> None:
        self._dispatcher = dispatcher or ActionDispatcher()
        self._guard = guard or PermissionGuard()
        self._audit = audit or ExecutionAudit()
        self._agent_id = agent_id
        self._registry: Any = None
        self._pending_store = pending_store     # AUD-F12: 有 store 则跨进程存活
        self._db_path = db_path
        self._autonomous_goal_sink = autonomous_goal_sink  # L3: 自主目标落地通道
        self._constitution_sink = constitution_sink        # L4-1: 宪法版本落库通道
        self._permission_gateway = permission_gateway  # S3.2（None→惰性默认实例）
        self._lifecycle_store: Any = None       # PW-1.4: event_memory EventStore（惰性）
        # P1.2 (AGI 计划): 学习产物检索源 — fn(description) -> artifacts 列表
        # （None=无注入，走原始 prompt 基线路径）
        self._learning_source: Any = learning_source
        # P2.1 (AGI 计划): 世界状态检索源 — fn(description) -> world context dict
        # （None=无注入；默认零传感器空世界也返回 available=False 不注入）
        self._world_source: Any = world_source
        # AGI 能力补全: 智能体软件检索源 — fn(description) -> 可用智能体清单
        # （None=无注入）；动态放行 CLI 前缀集（沙盒 extra_allow）
        self._agent_source: Any = agent_source
        self._agent_clis: frozenset = frozenset()
        # AGI 自我增强: 智能体安装执行器 — fn(name) -> {ok, executed, ...}
        # （None=未接入，安装动作直接拒绝；审批必经 execute_approved 触达）
        self._installer: Any = installer
        # P2-2: LLM 日预算 — 超限后任务转待批（诚实降级，不烧 token）
        self._llm_calls_today: int = 0
        self._llm_calls_date: str = ""
        self._textgen: Any = None
        self._pending: list[dict] = []          # 无 store 时的内存回退（诚实降级）
        self._reports: list[BridgeReport] = []
        # Phase 49-D (L8): 元认知置信度源 (注入 learning rules 查询函数)
        # signature: confidence_source(task_desc, task_type) -> ConfidenceVerdict
        self._confidence_source: Any = None

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
        # P2-1: 只读数据库查询（系统自检、数据分析）
        self._dispatcher.register_handler(
            ActionType.QUERY_DB, self._handler_query_db)
        # D: 自我升级提案的人工批准执行器（字符串 action_type, 经
        # dispatch_by_name 触达 — 批准即应用, 人工 = authority）
        self._dispatcher.register_custom_handler(
            "self_upgrade", self._handler_self_upgrade)
        # PW-3.1: 系统修复提案的人工批准执行器
        self._dispatcher.register_custom_handler(
            "system_repair", self._handler_system_repair)
        # PW-4.2: 文件操作执行器（digital_world file_ops, 需审批）
        self._dispatcher.register_custom_handler(
            "file_op", self._handler_file_op)
        # AGI 自我增强: 智能体下载/安装执行器（需审批, 经 execute_approved 触达）
        self._dispatcher.register_custom_handler(
            "agent_install", self._handler_agent_install)
        # L3 (升级方案 v1.0): 自主目标提案的人工批准执行器 — 批准即写
        # goals 表 PENDING（source='autonomous'），daemon 自动认领执行
        self._dispatcher.register_custom_handler(
            "autonomous_goal", self._handler_autonomous_goal)
        # L4-1: 价值观宪法修改的人工批准执行器 — 批准即落新版本
        # （人格演变可追溯；MODIFY_CONSTITUTION 永须人工审批）
        self._dispatcher.register_custom_handler(
            "constitution_update", self._handler_constitution_update)
        # UX-F1: DAG 任务 LLM 执行器 — 任务描述→具体动作→真实执行
        for dag_action in ("dag_create", "dag_modify", "dag_execute", "dag_verify"):
            self._dispatcher.register_custom_handler(
                dag_action, self._handler_dag_task)
        return self

    def attach_confidence_source(self, source: Any) -> "DecisionBridge":
        """Phase 49-D (L8): 注入元认知置信度源。

        source 为可调用对象: source(task_desc, task_type) -> ConfidenceVerdict
        返回 verdict.should_escalate=True 时, 写类任务升级 ASK (治理增强)。
        """
        self._confidence_source = source
        return self

    def attach_learning_source(self, source: Any) -> "DecisionBridge":
        """P1.2 (AGI 计划): 注入学习产物检索源。

        source 为可调用对象: fn(description) -> list[dict]，每项含
        {artifact_id, type, text, confidence}（见 learning_artifacts）。
        None/未注入 = 决策 prompt 无学习产物注入（基线路径）。
        """
        self._learning_source = source
        return self

    def attach_world_source(self, source: Any) -> "DecisionBridge":
        """P2.1 (AGI 计划): 注入世界状态检索源。

        source 为可调用对象: fn(description) -> world context dict（含
        available/entities，见 WorldStore.cognitive_world_state）。空世界
        （默认零传感器）返回 available=False → 不注入，优雅降级。
        """
        self._world_source = source
        return self

    def attach_agent_source(self, source: Any) -> "DecisionBridge":
        """AGI 能力补全: 注入智能体软件检索源。

        source 为可调用对象: fn(description) -> list[dict]，每项含
        {name, available, kind, cli_path, version, api_endpoint}（见
        AgentDiscovery 发现结果）。规划 LLM 据此知道本机有哪些智能体软件
        可用及如何调用（自动分析 → 接入 → 调用 的规划侧闭环）。
        """
        self._agent_source = source
        return self

    def attach_agent_clis(self, clis: set) -> "DecisionBridge":
        """AGI 能力补全: 注入动态放行 CLI 前缀集（沙盒 extra_allow）。

        仅放行 AgentDiscovery 确认存在的智能体软件可执行名/绝对路径；
        放行后 LLM 规划的 `<agent> <args>` 命令可经沙盒真实执行。
        """
        cleaned = {str(c).strip() for c in (clis or set()) if str(c).strip()}
        self._agent_clis = frozenset(cleaned)
        return self

    def attach_installer(self, fn: Any) -> "DecisionBridge":
        """AGI 自我增强: 注入智能体安装执行器。

        fn(name) -> {ok, executed, output, error, ...}（真实下载/安装 + 重发现；
        由 daemon 装配层构造并持 white-list AgentInstaller）。未注入 → 安装
        动作直接拒绝（fail-closed，绝不执行任意安装）。
        """
        self._installer = fn
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

        # S3.2: 网关前检 — 反向控制/注入模式直接 DENY（带审计）
        deny_reason = self._gateway_scan(text)
        if deny_reason is not None:
            # 个人使用模式：回环/localhost 类 SSRF 文本信号放行（同
            # execute_dag_task 的豁免逻辑），反向控制/注入类仍拦。
            from ocos.operations.sandbox_ops import sandbox_disabled
            if sandbox_disabled() and "ssrf" in deny_reason.lower():
                logger.info("SSRF text signal in decision text allowed "
                            "under personal mode: %s", deny_reason[:80])
                deny_reason = None
        if deny_reason is not None:
            v = ActionVerdict(
                action_type="DECISION_TEXT", verdict="deny",
                reason=deny_reason, status="denied",
                summary="blocked by permission gateway pre-check")
            report.verdicts.append(v)
            self._audit.log_failure(
                contract_id=f"GATEWAY-{uuid.uuid4().hex[:8]}",
                agent_id=self._agent_id,
                error=f"decision text blocked: {text[:200]}")
            logger.warning("DecisionBridge: decision text denied by "
                           "gateway pre-check — %s", deny_reason)
            self._reports.append(report)
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

        # S3.2: 网关前检 — 反向控制/注入模式的任务描述直接拒绝
        deny_reason = self._gateway_scan(description)
        if deny_reason is not None:
            # 个人使用模式（OCOS_SANDBOX_DISABLED=true）：owner 已声明信任
            # 本机目标，任务描述中出现回环地址/localhost URL（如"探测
            # http://127.0.0.1:8900/health"）不再按 SSRF 文本拦截 —
            # 反向控制/命令注入类规则仍然生效。
            from ocos.operations.sandbox_ops import sandbox_disabled
            if sandbox_disabled() and "ssrf" in deny_reason.lower():
                logger.info("SSRF text signal in task description allowed "
                            "under personal mode: %s", deny_reason[:80])
                deny_reason = None
        if deny_reason is not None:
            self._audit_record(
                contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                status="failed",
                summary=f"gateway_blocked: {deny_reason[:120]}")
            return {"status": "failed",
                    "reason": f"权限网关拦截: {deny_reason}"}


        # Phase 49-D (L8): 元认知置信度门 — 低置信写类任务升级 ASK
        # (治理增强: 历史成功率低的写类动作不自动执行, 不烧 LLM token;
        #  审批关闭时跳过 — ASK 通道停用)
        # P3.1 (AGI 计划): 经验豁免 — 低置信但命中高置信同类经验 → 不升级，
        # 经验支持直接执行（置信度驱动策略：无经验才保守）。
        if (self._confidence_source is not None and not approval_disabled()
                and task_type in _DAG_ASK_TYPES):
            try:
                if self._experience_supports(description):
                    pass  # 经验豁免：同类高置信经验存在，不升级 ASK
                else:
                    verdict = self._confidence_source(description, task_type)
                    if getattr(verdict, "should_escalate", False):
                        self._enqueue_pending(
                            action_type=f"dag_{task_type}",
                            target="dag_task",
                            payload={"task_id": getattr(task, "task_id", ""),
                                     "description": description,
                                     "metacognition": getattr(
                                         verdict, "reason", "")},
                            text=f"{description} (低置信升级待批)",
                        )
                        return {
                            "status": "pending_approval",
                            "reason": (f"metacognition: low confidence "
                                       f"({getattr(verdict, 'reason', '')})"),
                        }
            except Exception as _mc_e:
                logger.debug("metacognition gate failed (non-blocking): %s",
                             _mc_e)

        # UX-F1: 目标由人工创建（→目标/CLI）= 隐式授权其子任务；
        # LLM 优先转换为具体动作真实执行（沙盒白名单+敏感路径拦截仍生效），
        # 转换失败/写类动作 → 待批。仅当无 LLM 时才走 ASK/echo 旧路径。
        # 注: 目标语境由调用方前置进 description（Step6 chat 单任务 = 完整
        # 目标描述；模板分解任务 = "目标 — 子任务名"），bridge 不反向查库。
        if self._llm_available():
            llm = self._handler_dag_task(SimpleNamespace(payload={
                "description": description, "task_id": getattr(task, "task_id", ""),
                "auto_readonly": task_type in _DAG_AUTO_TYPES}))
            if llm.get("ok"):
                self._audit_record(
                    contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                    status="completed",
                    summary=f"dag_{task_type}: {str(llm.get('stdout', llm.get('applied', '')))[:150]}")
                return {"status": "completed", "result": llm}
            if llm.get("pending"):
                # S1.1: FILE_WRITE 强制审批 — 待批而非失败/执行
                self._audit_record(
                    contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                    status="pending",
                    summary=f"dag_{task_type}: {str(llm.get('error', ''))[:150]}")
                return {"status": "pending_approval",
                        "reason": str(llm.get("error", "file_write requires approval"))}
            # UX-G: LLM 判定不可执行（描述模糊/无动作）→ 诚实 failed，
            # 落入 goal_result 摘要；不再堆无法批准的待批噪音
            # FIX-失败遮蔽: 真实原因若藏在 blocked/stderr/exit_code 里，
            # 会被默认兜底掩盖成 "LLM 无法执行此任务"— 用显式提取函数,
            # 让执行者/用户看到真实失败原因而非模糊文案。
            return {"status": "failed",
                    "reason": self._execution_failure_reason(llm, description)}

        if task_type in _DAG_ASK_TYPES:
            # 审批关闭: 无 LLM 且写类动作无执行器（批准也只能 blocked）→ 诚实失败
            if approval_disabled():
                return {"status": "failed",
                        "reason": ("无语言核心且审批已关闭"
                                   "（OCOS_APPROVAL_MODE=auto）— "
                                   "写类任务无法执行")}
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
            if result is None and self._llm_available():
                # UX-F1: 描述无路径匹配 → LLM 转换为只读白名单命令自主执行
                # （低危 auto:governed：白名单+分段校验+敏感路径拦截全生效）
                llm = self._handler_dag_task(SimpleNamespace(payload={
                    "description": description, "task_id": "",
                    "auto_readonly": True}))
                if llm.get("ok"):
                    self._audit_record(
                        contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                        status="completed",
                        summary=f"dag_{task_type}: {str(llm.get('stdout', ''))[:150]}")
                    return {"status": "completed", "result": llm}
                # LLM 判定不可执行 → 诚实 failed（归档进 goal_result）
                return {"status": "failed",
                        "reason": (llm.get("error") or llm.get("block_reason")
                                   or "LLM 无法转为只读动作")}
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

        # UX-F1: LLM 可用时，任何未匹配类型都先尝试 LLM 转换（杜绝 EchoAgent
        # 假成功）；无 LLM 才回退 EchoAgent（诚实保留旧行为）
        if self._llm_available():
            llm = self._handler_dag_task(SimpleNamespace(payload={
                "description": description, "task_id": getattr(task, "task_id", ""),
                "auto_readonly": task_type in _DAG_AUTO_TYPES}))
            if llm.get("ok"):
                self._audit_record(
                    contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                    status="completed",
                    summary=f"dag_{task_type}: {str(llm.get('stdout', llm.get('applied', '')))[:150]}")
                return {"status": "completed", "result": llm}
            if llm.get("pending"):
                # S1.1: FILE_WRITE 强制审批 — 待批而非失败/执行
                self._audit_record(
                    contract_id=f"DAG-{uuid.uuid4().hex[:8]}",
                    status="pending",
                    summary=f"dag_{task_type}: {str(llm.get('error', ''))[:150]}")
                return {"status": "pending_approval",
                        "reason": str(llm.get("error", "file_write requires approval"))}
            self._pending.append({
                "action_type": f"dag_{task_type}",
                "target": "dag_task",
                "payload": {"task_id": getattr(task, "task_id", ""),
                            "description": description,
                            "llm_reason": llm.get("error", "")},
                "text": description[:200],
                "queued_at": datetime.now(timezone.utc).isoformat(),
            })
            return {"status": "pending_approval",
                    "reason": llm.get("error", "LLM 无法执行此任务")}
        return {"status": "echo_fallback"}      # 无 LLM → 既有 EchoAgent 行为

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

        # 2. 中危 → ASK 待批 (R4-B) — 审批关闭时自动放行
        if action.action_type in ASK_ACTIONS:
            if approval_disabled():
                return "auto", (f"action {action.action_type.name} "
                                f"auto-approved (approval off)")
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

        # 审批关闭: 未分类动作尝试执行（未注册执行器时 dispatch 为 no-op）
        if approval_disabled():
            return "auto", (f"action {action.action_type.name} "
                            f"not classified (approval off)")
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
        2026-09-07: OCOS_SANDBOX_DISABLED=true（个人使用模式）→ 白名单与
        敏感路径检查整体关闭，仅保留灾难黑名单。
        """
        command = (action.payload or {}).get("command", "")
        if not command:
            return {"ok": False, "error": "empty command"}

        # O4: writer 前置 Python sqlite3 降级 — 检测 sqlite3 binary 命令，
        #     只读 SELECT 用 Python sqlite3 库直接执行，绕开 binary 缺失
        #     或沙盒拦截导致的失败（capability_offline belief 触发 writer
        #     被 GoalGenesis 拦截的根因之一）。
        _sqlite3_fallback = self._try_sqlite3_fallback(command)
        if _sqlite3_fallback is not None:
            return _sqlite3_fallback
        # UX-F1 安全加固: 复合命令（; && ||）分段校验——白名单是前缀匹配，
        # 不分段则 "uname -a; <危险命令>" 会绕过白名单
        import re as _re
        segments = [s.strip() for s in _re.split(r";|&&|\|\|", command) if s.strip()]
        SENSITIVE_PREFIXES = ("/etc", "/root", "/proc", "/sys", "/boot",
                              "/dev", "/var/log",
                              "/home/laogao/.ssh", "/home/laogao/.config")
        # P6 (2026-09-01): 公开只读系统信息文件 — 精确放行（world-readable,
        # 无密钥无凭据）; 此前 /etc 前缀一刀切误伤 cat /etc/os-release
        # （宿主机信息收集是常见合法任务）。敏感文件仍被前缀规则拦截。
        # UX-I+ (2026-09-04): 补 /proc 只读系统指标文件 — "分析宿主机"类
        # 目标常编译出 cat /proc/cpuinfo|meminfo，误拦导致任务假性失败。
        PUBLIC_READONLY_PATHS = frozenset({
            "/etc/os-release",
            "/proc/cpuinfo", "/proc/meminfo", "/proc/loadavg",
            "/proc/uptime", "/proc/version",
        })
        # UX-J+ (2026-09-06): 无害设备文件放行 — "> /dev/null 2>&1" 是
        # 脚本静默输出的惯用法，/dev 前缀一刀切误拦（智能体发现目标实测
        # 被拦一次并触发无谓重试）。同族无凭据/无危害设备一并精确放行。
        HARMLESS_DEV_DEVICES = frozenset({
            "/dev/null", "/dev/zero", "/dev/full",
            "/dev/random", "/dev/urandom",
        })
        try:
            from ocos.operations.sandbox_ops import SandboxOps, sandbox_disabled
            if not sandbox_disabled():
                for seg in segments:
                    # AGI 能力补全: extra_allow 放行已发现智能体 CLI（沙盒动态白名单）
                    if not SandboxOps._is_allowed(seg, self._agent_clis):
                        return {"ok": False, "blocked": True,
                                "block_reason": f"白名单外命令段: {seg[:60]}"}
                    # 敏感路径拦截: 命令参数指向系统敏感目录即拒绝
                    for token in _re.findall(r"[~/][\w./-]*", seg):
                        resolved = os.path.abspath(os.path.expanduser(token))
                        if (resolved in PUBLIC_READONLY_PATHS
                                or resolved in HARMLESS_DEV_DEVICES):
                            continue  # 公开只读文件 / 无害设备文件放行
                        if any(resolved.startswith(p) for p in SENSITIVE_PREFIXES):
                            return {"ok": False, "blocked": True,
                                    "block_reason": f"敏感路径: {token[:50]}"}
        except Exception:
            pass
        try:
            import os as _os
            from ocos.operations.sandbox_ops import SandboxCommand, SandboxOps
            workdir = "/tmp/ocos_sandbox"
            _os.makedirs(workdir, exist_ok=True)  # 沙盒工作目录（SandboxOps 不自建）

            def _exec(cmd: str):
                # AGI 能力补全: 动态放行已发现智能体 CLI（默认空集 = 行为不变）
                r = SandboxOps(strict=True,
                               extra_allow=self._agent_clis).execute(
                    SandboxCommand(command=cmd, workdir=workdir, timeout=30.0))
                return (r.success, r.blocked, r.block_reason, r.exit_code,
                        r.stdout or "", r.stderr or "")

            def _is_crash(resp) -> bool:
                # 崩溃特征: 栈溢出保护触发 或 进程被信号杀死(exit_code<0,如 -6 SIGABRT)
                err = (resp[5] or "").lower()
                return ("stack smashing" in err) or (resp[3] is not None and resp[3] < 0)

            r0 = _exec(command)
            # 崩溃兜底: 复合命令("a; b; c")在沙箱内偶发栈崩溃 → 拆分为单段
            # 逐个执行并聚合, 规避单条大复合 shell 命令触碰栈保护; 已在上方对
            # 各段做过白名单/敏感路径校验, 兜底仅执行合法段。
            if _is_crash(r0) and len(segments) > 1:
                outs: list[str] = []
                errs: list[str] = []
                all_ok, rc = True, 0
                for seg in segments:
                    rr = _exec(seg)
                    if rr[3] not in (None, 0):
                        rc = rr[3]; all_ok = False
                    if rr[5]:
                        errs.append(rr[5])
                    if rr[4]:
                        outs.append(rr[4])
                resp = {"ok": all_ok, "blocked": r0[1],
                        "block_reason": r0[2],
                        "exit_code": 0 if rc == 0 and not errs else rc,
                        "stdout": "\n".join(outs)[:1200],
                        "stderr": "; ".join(errs)[:300]}
            else:
                resp = {"ok": r0[0], "blocked": r0[1], "block_reason": r0[2],
                        "exit_code": r0[3], "stdout": r0[4][:1200],
                        "stderr": r0[5][:300]}
            self._mark_external_agent_call(command, resp)
            return resp
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # O4: sqlite3 binary → Python sqlite3 降级拦截
    def _try_sqlite3_fallback(self, command: str) -> dict | None:
        """拦截 sqlite3 binary shell 命令，只读 SELECT 用 Python sqlite3 库
        直接执行。返回 None 表示不是 sqlite3 命令，走原有 subprocess 路径。

        解析支持两种常见形式:
          sqlite3 path/to/db "SELECT ..."
          sqlite3 path/to/db SELECT ... (无引号)
        """
        import re as _re
        import os as _os
        # 匹配前缀: sqlite3 /path/to/db "SQL" 或 sqlite3 /path/to/db SQL
        m = _re.match(
            r'^\s*sqlite3\s+([^\s]+)\s+"([^"]+)"\s*$', command)
        if not m:
            m = _re.match(
                r'^\s*sqlite3\s+([^\s]+)\s+(.+?)\s*$', command)
        if not m:
            return None  # 不是 sqlite3 命令 → 走原路径

        db_path = _os.path.expanduser(m.group(1))
        sql = m.group(2).strip()

        # 安全闸门: 只允许只读语句
        if not sql.upper().startswith(("SELECT", "PRAGMA", "EXPLAIN", "WITH")):
            return None  # 写操作 → 走原路径（可能被沙盒/黑名单拦截）

        # 路径闸门: 只允许 ocos 数据库或 tmp 文件
        _ocos_dir = _os.path.expanduser("~/.ocos")
        _tmp_dir = "/tmp"
        if not (db_path.startswith(_ocos_dir)
                or db_path.startswith(_tmp_dir)
                or db_path == ":memory:"):
            return None

        if not _os.path.exists(db_path):
            return {"ok": False, "exit_code": 1,
                    "stderr": f"sqlite3 binary fallback: db not found: {db_path}",
                    "stdout": ""}

        try:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row
            cur = conn.execute(sql)
            rows = cur.fetchall()
            # 列头 + 行数据（模拟 sqlite3 -column 输出）
            cols = [d[0] for d in cur.description] if cur.description else []
            if cols and rows:
                sep = "|"
                out_lines = [sep.join(cols)]
                for r in rows:
                    out_lines.append(sep.join(str(c) for c in r))
                stdout = "\n".join(out_lines)
            elif rows:
                out_lines = []
                for r in rows:
                    out_lines.append(sep.join(str(c) for c in r))
                stdout = "\n".join(out_lines)
            else:
                stdout = "(empty)"
            conn.close()
            return {"ok": True, "exit_code": 0, "stdout": stdout,
                    "stderr": "", "_via_python_sqlite3": True}
        except Exception as e:
            return {"ok": False, "exit_code": 1,
                    "stderr": f"sqlite3 fallback error: {e}", "stdout": ""}

    def _mark_external_agent_call(self, command: str, resp: dict) -> None:
        """V6: 外部智能体 CLI 真实调用打点（执行时信号，非文本猜测）。

        命令段二进制命中动态白名单 _agent_clis（AgentDiscovery 发现层
        注入）即记 external_agent_call → learning.jsonl，ok 取沙盒执行
        真值。vitals _social_metrics 消费产出 social_call_success_rate。
        """
        try:
            import os as _os
            names: set[str] = set()
            for c in self._agent_clis:
                names.add(c)
                names.add(_os.path.basename(c))
            hit = ""
            for seg in command.replace(";", "&&").split("&&"):
                tok = seg.strip().split()
                if tok and (tok[0] in names
                            or _os.path.basename(tok[0]) in names):
                    hit = tok[0]
                    break
            if hit:
                self._audit_learning_mark(
                    "external_agent_call", agent=_os.path.basename(hit),
                    ok=bool(resp.get("ok")))
        except Exception:
            logger.debug("external agent call mark failed", exc_info=True)

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

    def _handler_query_db(self, action: DispatchedAction) -> dict:
        """P2-1: 只读 SQLite 查询 — 系统自检、数据分析。

        限制: 仅允许 SELECT 语句, 禁止写入/修改/schema 操作。
        安全: 只读主数据库, 不暴露凭据路径。
        """
        from pathlib import Path
        import sqlite3
        query = (action.payload or {}).get("query", "")
        if not query:
            return {"ok": False, "error": "empty query"}
        # 安全检查: 仅允许 SELECT, 禁止写入/修改
        cleaned = query.strip().lower()
        if any(kw in cleaned for kw in ("insert", "update", "delete", "drop",
                                         "alter", "create", "replace",
                                         "truncate", "attach", "detach")):
            return {"ok": False, "error": "write operations not allowed"}
        if not cleaned.startswith("select"):
            return {"ok": False, "error": "only SELECT queries allowed"}
        try:
            # S3.8 (白皮书 P3): 使用实例 db_path（原硬编码 ~/.ocos/ocos.db
            # ——daemon 用自定义 db_path 时 QUERY_DB 查错库）
            db_path = self._db_path or str(Path.home() / ".ocos" / "ocos.db")
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            results = [dict(r) for r in rows[:200]]  # 限制返回行数
            conn.close()
            return {"ok": True, "columns": cols, "rows": results, "count": len(rows)}
        except sqlite3.Error as e:
            return {"ok": False, "error": f"sqlite: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handler_self_upgrade(self, action: DispatchedAction) -> dict:
        """PW-2.1: 应用已批准的自我升级 — 走 evolution 治理链。

        人工批准 = authority（自治路径在 propose_upgrade 守门即封死;
        主权冻结域的提案连待批都进不了）。真实应用 + 快照可回滚。
        """
        from ocos.agent.self_evolution_link import apply_approved
        payload = action.payload or {}
        change = payload.get("change", "")
        if not change:
            return {"ok": False, "error": "empty change payload"}
        out = apply_approved(proposal_id=payload.get("proposal_id", ""),
                             title=payload.get("title", ""), change=change)
        return {"ok": out["ok"], "applied": out.get("applied", ""),
                "error": out.get("error", ""),
                "rollback_snapshot": out.get("rollback_snapshot", "")}

    def _handler_autonomous_goal(self, action: DispatchedAction) -> dict:
        """L3: 应用已批准的自主目标提案 — 经注入的 sink 写 goals 表。

        人工批准 = authority（LEVEL1 提案未经批准永不执行）。写库职责
        由装配层注入（autonomous_goal_sink）— ocos.execution 不直接
        import ocos.goal.store（import 规则硬约束）。失败原因透明返回。
        """
        payload = action.payload or {}
        goal_id = payload.get("goal_id", "")
        description = payload.get("description", "")
        if not goal_id or not description:
            return {"ok": False, "error": "missing goal_id/description payload"}
        if self._autonomous_goal_sink is None:
            return {"ok": False,
                    "error": "no autonomous_goal_sink attached (装配层未注入落地通道)"}
        try:
            self._autonomous_goal_sink(payload)
            return {"ok": True, "goal_id": goal_id,
                    "detail": "已写入 goals 表 PENDING，daemon 将自动认领执行"}
        except Exception as e:
            return {"ok": False, "error": f"autonomous goal save failed: {e}"}

    def _handler_constitution_update(self, action: DispatchedAction) -> dict:
        """L4-1: 应用已批准的宪法修改 — 经注入的 sink 落新版本。

        人工批准 = authority（MODIFY_CONSTITUTION 属人工审批动作，
        未经批准永不生效）。落库职责由装配层注入（constitution_sink）
        — ocos.execution 不直接依赖 constitution 模块。全量快照语义。
        """
        payload = action.payload or {}
        principles = payload.get("principles")
        reason = payload.get("reason", "")
        if not isinstance(principles, list) or not principles:
            return {"ok": False, "error": "missing/empty principles payload"}
        if self._constitution_sink is None:
            return {"ok": False,
                    "error": "no constitution_sink attached (装配层未注入落库通道)"}
        try:
            out = self._constitution_sink(payload)
            version = out.get("version", "?") if isinstance(out, dict) else "?"
            return {"ok": True, "version": version,
                    "detail": f"宪法新版本 v{version} 已落库（{len(principles)} 条原则）"}
        except Exception as e:
            return {"ok": False, "error": f"constitution save failed: {e}"}

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
        self._record_lifecycle(
            "action", (dispatched.action_type.name
                       if hasattr(dispatched.action_type, "name")
                       else str(dispatched.action_type)),
            {"status": dispatched.status,
             "summary": self._summarize(dispatched)[:200]})
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
        self._record_lifecycle("result", self._agent_id,
                               {"status": status, "summary": summary[:200]})
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

    def _handler_system_repair(self, action) -> dict:
        """PW-3.1: 系统修复 — 白名单步骤 + checkpoint/rollback。"""
        from ocos.daemon.repair_link import execute_system_repair
        payload = action.payload or {}
        if not self._db_path:
            return {"ok": False, "error": "no db_path — 无法执行数据级修复"}
        return execute_system_repair(payload, self._db_path)

    def _handler_agent_install(self, action) -> dict:
        """AGI 自我增强: 智能体下载/安装执行器（仅经审批触达）。

        由 execute_approved("agent_install", ...) 调用；payload 需带 agent 名
        与 approval_id。真实安装由注入的 installer fn 承担（白名单 AgentInstaller
        + 重发现）。未接入 installer → fail-closed 拒绝。
        """
        payload = action.payload or {}
        name = (payload.get("agent") or payload.get("target") or "").strip()
        return self._handle_install_action(
            name, payload.get("approval_id"), already_approved=True)

    def _probe_host_capabilities(self) -> dict:
        """P1-SELFBOOT: 探测宿主机真实能力（不依赖 LLM 判断）。

        返回 {"curl": bool, "python3": bool, "wget": bool, "internet": bool}
        — 用于 NONE 自举重试时给 LLM 注入真实硬件事实，
        防止它凭空假设"没有联网能力"。
        """
        import shutil
        result = {
            "curl": shutil.which("curl") is not None,
            "wget": shutil.which("wget") is not None,
            "python3": shutil.which("python3") is not None,
            "git": shutil.which("git") is not None,
            "internet": False,
        }
        # 外网连通性探测（单次请求，1s 超时）
        try:
            import urllib.request
            import urllib.error
            req = urllib.request.Request(
                "https://api.github.com", method="HEAD")
            urllib.request.urlopen(req, timeout=1).read(0)
            result["internet"] = True
        except Exception:
            try:
                # 回退: DNS 解析
                import socket
                socket.setdefaulttimeout(2)
                socket.create_connection(("1.1.1.1", 53))
                result["internet"] = True
            except Exception:
                result["internet"] = False
        return result

    def _handle_install_action(self, name: str, approval_id: Any,
                               already_approved: bool = False) -> dict:
        """AGI 自我增强: 安装动作统一入口 — 无审批 → 入待批；已审批 → 执行。

        安全: 未接入 installer 直接拒绝（fail-closed）；agent 名来自规划 LLM
        输出，仅作为白名单查表键传给 AgentInstaller（installer 内部再校验）。
        """
        if not name:
            return {"ok": False, "error": "empty agent name for install"}
        if self._installer is None:
            return {"ok": False, "error": "没有可用安装执行器 — 安装被拒"}
        if not approval_id and not already_approved:
            self._enqueue_pending(
                action_type="agent_install",
                target=name,
                payload={"agent": name},
                text=f"AGENT_INSTALL {name} (智能体下载/安装 — 强制审批)")
            return {"ok": False, "pending": True,
                    "error": f"agent {name} 安装需人工审批 — 已入待批队列"}
        try:
            res = self._installer(name)
            return res if isinstance(res, dict) else {"ok": bool(res)}
        except Exception as e:
            return {"ok": False, "executed": False,
                    "error": f"install failed: {e}"}

    def _handler_file_op(self, action) -> dict:
        """PW-4.2: 文件操作 — digital_world/file_ops 宽语义后端。

        仅经审批触达（file_write/delete 属 APPROVAL_REQUIRED）；
        受保护路径（/etc、~/.ssh 等）由 file_ops 内建拒绝。
        """
        payload = action.payload or {}
        op_type = payload.get("op_type", "")
        target = payload.get("target", "")
        if not target:
            return {"ok": False, "error": "empty target"}
        approval_id = payload.get("approval_id")
        if not approval_id:
            return {"ok": False,
                    "error": "file op requires approval_id（必须经审批流触达）"}
        if not self._verify_approval(approval_id):
            return {"ok": False,
                    "error": f"invalid or unapproved approval_id: {approval_id}"}
        try:
            from ocos.digital_world.base import DigitalOperation
            from ocos.digital_world import file_ops
            handlers = {"file_read": file_ops.file_read,
                        "file_write": file_ops.file_write,
                        "file_delete": file_ops.file_delete}
            handler = handlers.get(op_type)
            if handler is None:
                return {"ok": False,
                        "error": f"unsupported file op: {op_type}"}
            op = DigitalOperation(
                op_id=f"OP-{uuid.uuid4().hex[:10]}", op_type=op_type,
                target=target, requester=self._agent_id,
                params=payload.get("params", {}) or {},
                approval_id=payload.get("approval_id"))
            result = handler(op)
            return {"ok": result.status == "success",
                    "status": result.status,
                    "output": (result.output or "")[:300],
                    "error": result.error or ""}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _handler_dag_task(self, action) -> dict:
        """UX-F1: DAG 任务执行 — LLM 把任务描述转换为具体动作并真实执行。

        动作格式（LLM 严格输出，每行一个动作、最多 4 行）:
            RUN|<只读白名单命令>       → SandboxOps 真实执行（多行逐条执行并聚合 stdout）
            FILE_WRITE|<路径>|<内容>   → digital_world file_ops
            NONE|<为什么无法执行>      → 诚实失败
        未接入语言核心（无 LLM key）→ 诚实 blocked。
        """
        payload = action.payload or {}
        description = payload.get("description", "") or payload.get("text", "")
        if not description:
            return {"ok": False, "error": "empty task description"}

        if not self._llm_available():
            return {"ok": False,
                    "error": "需要语言核心（LLM key）才能把任务描述转换为可执行动作",
                    "honest_blocked": True}
        budget_ok, budget_reason = self._llm_budget_ok()
        if not budget_ok:
            return {"ok": False, "error": budget_reason, "honest_blocked": True}

        try:
            import asyncio
            tg = self._get_textgen()
            # S3.7: 代理隔离已下沉到 provider（trust_env=False）——
            # 删除进程级 env pop/restore（并发竞态）
            if True:
                _rules = (
                    "把上述任务转换为可直接执行的动作。每行一个动作、最多 4 行，格式严格为：\n"
                    "RUN|<命令>（本地只读优先: uname/df/free/uptime/ls/cat/head/"
                    "tail/grep/find/ps/whoami/date/env/hostname/id/sqlite3；任务要求联网"
                    "访问/抓取/调研外部内容（GitHub/网页/API）时必须用 "
                    "RUN|curl -s <url> 真实抓取，禁止省略联网部分只用本地命令"
                    "应付。所有 curl 都加 --max-time 15（防止挂起耗尽执行"
                    "超时）。\n"
                    "⚠️ Python 解析 JSON 必须防御性：先检查 key 存在再访问。"
                    "错误示范: python3 -c \"...json.load(sys.stdin)['items']...\" "
                    "（当 API 返回非预期结构时直接 KeyError 崩溃）。"
                    "正确示范: python3 -c \"import json,sys; d=json.load(sys.stdin); "
                    "items=d.get('items') or d.get('results') or []; "
                    "[print(r.get('full_name','')) for r in items[:5]]\" \n"
                    "GitHub 调研配方: 先"
                    "RUN|curl -s --max-time 15 \"https://api.github.com/search/repositories?"
                    "q=关键词&per_page=5&sort=stars\" | python3 -c \"import json,"
                    "sys; d=json.load(sys.stdin); items=d.get('items',[]); "
                    "[print(r['full_name'],'|',r['stargazers_count'],'|',"
                    "(r.get('description') or '')[:150]) for r in items]\" "
                    "提取精简字段（必须用 d.get() 防御），再对代表性项目用 "
                    "RUN|curl -s --max-time 15 -H \"Accept: "
                    "application/vnd.github.raw\" "
                    "\"https://api.github.com/repos/<owner>/<repo>/readme\" "
                    "抓取 README（注意: raw.githubusercontent.com 在部分网络"
                    "不可达，一律走 api.github.com）\n"
                    "查对话历史/成长叙事/记忆 → 不要尝试读 markdown/jsonl 文件，"
                    "直接用: RUN|sqlite3 /home/laogao/.ocos/ocos.db \"SELECT rowid,"
                    "action, substr(decision,1,100), created_at FROM episodes "
                    "ORDER BY rowid DESC LIMIT 20\" \n"
                    "宿主机环境探查标准命令集（任务含'检查/分析宿主机/系统环境/"
                    "硬件/部署可行性'时必须覆盖，尤其 GPU——漏查 GPU 会使部署"
                    "方案的显存估算失真）: RUN|uname -a  RUN|df -h  RUN|free -h"
                    "  RUN|nproc  RUN|swapon --show  RUN|nvidia-smi --query-gpu="
                    "name,memory.total --format=csv（无 NVIDIA 卡会失败，改用"
                    " RUN|lspci | grep -iE 'vga|3d'）\n"
                    "ANSWER|<结论文本>（纯分析/总结/复盘类任务且所需信息已在上下文中时"
                    "使用——直接给出归纳结论，不执行任何命令）\n"
                    "AGENT_INSTALL|<智能体名>（任务要求下载/安装某智能体时用）\n"
                    "FILE_WRITE|<绝对路径>|<文件内容>\n"
                    "NONE|<一句话说明为什么无法执行>\n"
                    "单一操作只输出一行；复合任务（如同时查看系统版本/磁盘/内存）"
                    "输出多条 RUN 行，且必须覆盖任务描述的全部关键部分"
                    "（联网调研与本地检查都要有对应动作，不可只做其中一半）。"
                    "curl 优先于 Python 脚本——能用一行 curl 解决的就不用 Python。"
                    "不要输出任何解释。"
                )
                prompt = f"任务描述：{description}\n\n{_rules}"
                # FIX-4: 注入同类历史任务结果 → 规划 LLM 可见历史成败经验
                prior = self._prior_task_results(description)
                if prior:
                    prompt = f"{prior}\n\n{prompt}"
                # L7 学习闭环: 失败先验 — cause 级矫正程序（正向程序指引，
                # 非失败叙事，规避 FIX-4 负反馈结构）
                f_prior = self._failure_prior_hint(description)
                if f_prior:
                    prompt = f"{f_prior}\n\n{prompt}"
                # V2 技能重放: 已验证技能图步骤复用（经验→技能→重放读侧）
                skill_hint = self._skill_replay_hint(description)
                if skill_hint:
                    prompt = f"{skill_hint}\n\n{prompt}"
                # 记忆直接参与决策 — 统一记忆决策上下文（量化 + 归因 + 类型分布）
                memory_ctx = self._memory_decision_context(description)
                if memory_ctx:
                    prompt = f"{memory_ctx}\n\n{prompt}"
                # 记忆冲突回落 — 记忆命中但世界无对象 → 显式回落防过时误导
                conflict = self._memory_conflict_hint(description)
                if conflict:
                    prompt = f"{conflict}\n\n{prompt}"
                # P2.1 (AGI 计划): 注入世界状态（感知→世界模型→决策）
                world = self._prior_world(description)
                if world:
                    prompt = f"{world}\n\n{prompt}"
                # AGI 能力补全: 注入可用智能体软件清单（自动分析 → 规划可见）
                agents = self._prior_agents(description)
                if agents:
                    prompt = f"{agents}\n\n{prompt}"
                # P0-C (2026-09-10): DB Schema 注入 — sql_schema_mismatch 根因修复
                # 只给列名，不给修复建议（让 LLM 自己决定）
                # 双触发: (1) description 含 DB/SQL 关键词
                #        (2) agent 是 researcher/writer/analyst 类（自然会查 DB）
                _db_kw = ("sql", "sqlite", "episodes", "数据库", "schema",
                          "表", "查询", "统计", "检索", "聚合", "分布",
                          "sqlite3", ".db", "数据库")
                _db_agents = ("researcher", "writer", "analyst", "archivist",
                              "critic")
                _agent_id_lc = (getattr(self, "_agent_id", "") or "").lower()
                _desc_lc = description.lower()
                if any(kw in _desc_lc for kw in _db_kw) or \
                        any(a in _agent_id_lc for a in _db_agents):
                    schema_ctx = self._schema_context()
                    if schema_ctx:
                        prompt = f"{schema_ctx}\n\n{prompt}"
                # UX-J+: 复盘/总结/学习类任务注入真实 goal_result 结论 —
                # 此前 LLM 拿不到执行结果，跑偏到文件系统扫描来"复盘"
                # （实测学习总结目标以 ls/扫目录代替记忆查询，部分达成）
                retro = self._retrospect_hint(description)
                if retro:
                    prompt = f"{retro}\n\n{prompt}"
                # 自我认知事实块 — 自省/差距类任务防"缺失自身能力"幻觉
                # （2026-09-07 对话审计：LLM 误称系统无自我模型/学习闭环）
                sk = self._self_knowledge_hint(description)
                if sk:
                    prompt = f"{sk}\n\n{prompt}"
                # 数字生命·启动自省先验 — 环境快照注入（适应力读侧），
                # 让目标执行基于本boot实测环境而非过时记忆/幻觉
                boot = self._boot_context_hint()
                if boot:
                    prompt = f"{boot}\n\n{prompt}"
                # AGI 能力补全: 任务显式引用已发现智能体 → 强制规划为直接调用
                # （抑制"调用 XX 智能体"漂移成通用系统分析的模板固化倾向）
                agent_hint = self._agent_hint(description)
                if agent_hint:
                    prompt = f"{agent_hint}\n\n{prompt}"
                # P2.2 (AGI 计划): 世界前置校验注记（目标对象不在世界模型 → 诚实说明）
                hint = self._world_hint(description)
                if hint:
                    prompt = f"{hint}\n\n{prompt}"
                raw = asyncio.run(tg._provider.generate(
                    prompt,
                    system_prompt="你是 OCOS 的任务执行规划器。只输出指定格式的动作行。",
                    temperature=0.1, max_tokens=2000))
                raw = raw.strip()
                # P3 (2026-09-08 事件复盘): 规划原始输出落日志 — 此前规划/
                # 重试/丢弃路径零观测，"计划正文被闸门丢弃"类事故无法取证
                _raw_lines = raw.splitlines() if raw else []
                logger.info("PLANNER-OUT (%d lines): %s", len(_raw_lines),
                            (_raw_lines[0] if _raw_lines else "")[:120])
        except Exception as e:
            return {"ok": False, "error": f"LLM 规划失败: {e}"}

        def _convert(feedback_text: str) -> str:
            """UX-K: 被沙盒拦截后带反馈重试一次。"""
            return asyncio.run(tg._provider.generate(
                f"{prompt}\n\n【上次尝试被拒绝】{feedback_text}\n"
                "请改用白名单内的只读命令重新输出，或输出 NONE|原因。",
                system_prompt="你是 OCOS 的任务执行规划器。只输出指定格式的单行动作。",
                temperature=0.1, max_tokens=2000))

        def _first_line(text: str) -> str:
            t = text.strip()
            if t.startswith("```"):
                t = t.strip("`").lstrip()
            return t.splitlines()[0].strip()

        # AGI 能力补全: 保真闸门 — 任务显式引用已发现智能体但规划输出未调用它
        # → 一次带强反馈的纠正（确定性拉回，抑制"调用 XX 智能体"漂移成
        # uname/df 系统分析；沿用 UX-K 重试通道，仍失败则诚实失败）。
        try:
            _forced = self._agent_forced_call(description)
            if _forced and not any(
                    _forced in _ln for _ln in raw.splitlines()):
                _raw2 = _first_line(_convert(
                    f"任务明确要求调用智能体「{_forced}」，你的输出未调用它。"
                    f"请只输出 RUN|{_forced} <参数>（只读示例: "
                    f"RUN|{_forced} --version），不要输出其他系统命令。"))
                logger.info("AGENT-GUARD: forced=%s corrected_to=%s",
                            _forced, _raw2[:100])
                if _raw2.startswith("RUN|"):
                    raw = _raw2
        except Exception:
            pass

        def _run_one(command: str, auto_readonly: bool) -> dict:
            """UX-F1: 单命令执行（含只读校验 + 沙盒拦截带反馈重试一次）。

            UX-J+ 实测修复: 拦截重试后结果必须携带实际执行的命令
            （"_executed_command"）— 此前聚合标签仍用原命令，把转换后
            命令的输出挂在原命令名下（curl 被拦→转成 openclaw --version
            → episode 记成 "$ curl … OpenClaw 版本"，两轮生产测试的
            "输出失真"均由此而来），LLM 汇总与记忆随之被误导。

            CHAT-ROUTE FIX (2026-09-07): auto_readonly 写符号拒绝此前
            提示"需转待批"却从不入队（诚实性缺口）；且个人使用模式
            （OCOS_SANDBOX_DISABLED=true）下 owner 已声明信任写命令——
            灾难黑名单（rm -rf / 等）仍在 SandboxOps._is_allowed 下游
            生效，此处直接放行。非个人模式维持拒绝语义（文案不再撒谎）。
            """
            if auto_readonly and any(
                    k in command.lower() for k in
                    ("write", "echo >", ">", "tee ", "rm", "mv", "mkdir")):
                from ocos.operations.sandbox_ops import sandbox_disabled
                if not sandbox_disabled():
                    return {"ok": False,
                            "error": ("自主路径仅允许只读命令——写操作被拒"
                                      "（未入待批队列；写文件请用 FILE_WRITE"
                                      "| 动作以进入强制审批）")}
            run_result = self._handler_run_command(
                SimpleNamespace(payload={"command": command}))
            if not run_result.get("ok") and run_result.get("blocked"):
                # UX-K: 沙盒拦截（白名单外/敏感路径）→ 带反馈重试一次
                raw2 = _first_line(_convert(run_result.get("block_reason", "")))
                if raw2.startswith("RUN|"):
                    _retried_cmd = raw2[4:].strip()
                    run_result = self._handler_run_command(
                        SimpleNamespace(payload={"command": _retried_cmd}))
                    if run_result.get("ok"):
                        run_result["_executed_command"] = _retried_cmd
            # Phase 1 (Mutation): 回传原始 command → agent_runtime 需它生成 mutation_policy
            run_result.setdefault("command", command)
            return run_result

        # UX-I+: 多动作任务（"uname/df/free/uptime 汇总"类）— LLM 可输出
        # 多条 RUN 行，逐条真实执行后聚合 stdout；任一命令失败即诚实失败
        _auto_ro = bool(payload.get("auto_readonly"))
        # FIX-5b: planning NONE| 只允许重试一次（防无限重规划烧 token）
        _retried_none = False
        _lines = [ln.strip().strip("`") for ln in raw.splitlines() if ln.strip()]
        # Phase 2 (Mutation): 同时用 ActionParser 解析，assert 等价性
        # 确保提炼前后行为完全一致（Phase 3 接 Mutation Engine 时 actions 将成为消费入口）
        _actions = self._parse_actions(raw)
        _reconstructed = self._actions_to_lines(_actions)
        if _reconstructed != _lines:
            # 不 crash，但记录 error（Phase 2 纯重构，不应出现不等价）
            logger.error("Phase2-PARSE-DIVERGENCE: _lines vs _actions_to_lines differ! "
                         "lines=%d actions=%d", len(_lines), len(_reconstructed))
        # UX-J+ 实测新增: ANSWER| — 认知型任务（复盘/总结/分析）所需信息
        # 已在注入上下文（如复盘素材）时，LLM 直接给出文字结论。此前只能
        # 用 NONE|（被判"无法执行→failed"）或违心跑系统采集命令（跑偏），
        # 两轮生产测试的复盘目标先后以这两种方式失败。
        _answer_idx = next((i for i, ln in enumerate(_lines)
                            if ln.startswith("ANSWER|")), None)
        # CHAT-ROUTE FIX (2026-09-07): ANSWER| 防幻觉闸门 —
        # 实测（T3 写文件/T5 探针）LLM 对执行类任务直接输出
        # "ANSWER|文件已创建…验证成功"即落 success=true，无任何真实
        # 执行证据（幻觉叙述蒙混过关）。规则：
        #   a) ANSWER 与 RUN/FILE_WRITE/AGENT_INSTALL 共存 → 剔除
        #      ANSWER 行，以真实动作分支为准；
        #   b) 纯 ANSWER 且描述含执行意图（动词/命令词）→ 带反馈重试
        #      一次要求真实动作，仍 ANSWER → 诚实失败；
        #   c) 纯 ANSWER 且确为分析/总结/复盘/创作类 → 维持放行
        #      （UX-J+ 本意 + P0-1 修复：制定计划/方案/设计的交付物
        #      就是正文，强制 RUN 会丢弃交付物并诱发噪声探针）。
        _EXEC_INTENT_RE = re.compile(
            r"执行|运行|写入|创建|新建|删除|探测|安装|下载|清空|"
            r"curl|wget|pip|apt|\bcat\b|\bls\b|\bdf\b|\bfree\b|"
            # P0-1: 「验证」收紧为目标词邻接模式（裸词曾误命中"验证标准"）
            r"验证.{0,8}(文件|目录|安装|执行|结果|成功|可用|生效|连通|修复)|"
            r"读取.{0,10}(文件|目录)|报告.{0,10}(状态|数据|结果|使用)")
        _has_real_action = any(
            ln.startswith(("RUN|", "FILE_WRITE|", "AGENT_INSTALL|"))
            for ln in _lines)
        if _answer_idx is not None and _has_real_action:
            logger.info("ANSWER-GUARD: dropped ANSWER| line — real action "
                        "present in plan (%s)", description[:60])
            _lines = [ln for ln in _lines if not ln.startswith("ANSWER|")]
            _answer_idx = None
        if _answer_idx is not None and not _has_real_action:
            _desc_is_exec = bool(_EXEC_INTENT_RE.search(description))
            # P0-1: 创作/分析类豁免（模块级共享正则，与 _prior_agents 一致）
            _desc_is_authoring = bool(
                _AUTHORING_ANALYSIS_RE.search(description))
            if _desc_is_authoring:
                logger.info("ANSWER-GUARD: authoring/analysis task — "
                            "ANSWER allowed as deliverable (%s)",
                            description[:60])
            if _desc_is_exec and not _desc_is_authoring:
                if not _retried_none:
                    _retried_none = True
                    # P3 (2026-09-08 事件复盘): 重试路径此前零观测，
                    # 事后取证只能靠 LLM 调用时序反推
                    logger.info("ANSWER-GUARD: pure ANSWER with exec "
                                "intent — retry for real action (%s)",
                                description[:60])
                    raw2 = _first_line(_convert(
                        "该任务需要真实执行证据，禁止直接给文字结论（你的"
                        " ANSWER 会被判为幻觉）。请输出 RUN|<命令> 或 "
                        "FILE_WRITE|<绝对路径>|<内容>；确实无法执行才输出"
                        " NONE|原因。"))
                    logger.info("ANSWER-GUARD: retry produced: %s",
                                raw2[:120])
                    if raw2.startswith("RUN|"):
                        _rr2 = _run_one(raw2[4:].strip(), _auto_ro)
                        if _rr2.get("ok"):
                            return {"ok": True, "blocked": False,
                                    "exit_code": 0,
                                    # P2: 自我模型能力实测归因（shell 实测）
                                    "capability": "shell",
                                    "stdout": f"$ {raw2[4:].strip()}\n"
                                              f"{_rr2.get('stdout', '')}"[:4000]}
                        return _rr2
                    if raw2.startswith("FILE_WRITE|"):
                        # 落入下方 FILE_WRITE 分支：同步 _lines/_raw 状态，
                        # 且必须清 _answer_idx（旧索引指向已丢弃的 ANSWER 行）
                        _lines = [raw2]
                        raw = raw2
                        _answer_idx = None
                    elif not raw2.startswith(("ANSWER|", "NONE|")):
                        _lines = [raw2]
                        raw = raw2
                        _answer_idx = None
                    else:
                        return {"ok": False,
                                "error": (f"执行类任务被 LLM 幻觉应答，"
                                          f"重试仍拒绝真实执行: "
                                          f"{raw2[:120]}"),
                                "honest_blocked": True}
                else:
                    return {"ok": False,
                            "error": ("执行类任务被 LLM 幻觉应答（ANSWER "
                                      "无真实执行证据）"),
                            "honest_blocked": True}
            elif (_desc_is_authoring
                  and _AUTHORING_DELIVERABLE_RE.search(description)
                  and not _retried_none):
                # P0-2 扩展 (2026-09-08 E2E 复测发现): 瘦 ANSWER 防空洞 —
                # 元描述（"我将直接给出计划结论"）不是交付物，落 ✓ 同样是
                # 假完成（cat --version 事件的文本变体）。创作交付类任务
                # ANSWER 过瘦 → 带反馈重试一次索要正文，仍瘦 → 诚实失败。
                _ans_first = _lines[_answer_idx][7:].strip()
                _ans_rest = "\n".join(_lines[_answer_idx + 1:]).strip()
                _ans_body = (f"{_ans_first}\n{_ans_rest}".strip()
                             if _ans_rest else _ans_first)
                if len(_ans_body) < 60:
                    _retried_none = True
                    logger.info("ANSWER-GUARD: thin ANSWER (%d chars) for "
                                "authoring task — retry for real content "
                                "(%s)", len(_ans_body), description[:60])
                    # 注: 不走 _convert（其"改用只读命令"话术会把 LLM 推向
                    # RUN 噪声探针），直接带反馈重新生成交付物正文
                    _cand = asyncio.run(tg._provider.generate(
                        f"{prompt}\n\n【上次输出被判空洞】你的 ANSWER 只是元"
                        "描述（说明你将做什么），不是交付物。请直接输出完整"
                        "的计划/方案正文本身（分阶段、分条目、含具体安排/内"
                        "容），格式仍为 ANSWER|<正文>，不要输出任何解释或元"
                        "描述。",
                        system_prompt="你是 OCOS 的任务执行规划器。只输出指定格式的动作行。",
                        temperature=0.1, max_tokens=2000)).strip()
                    if _cand.startswith("```"):
                        _cand = _cand.strip("`").lstrip()
                    if _cand.startswith("FILE_WRITE|"):
                        _lines = [_cand.splitlines()[0]]
                        raw = _lines[0]
                        _answer_idx = None
                    elif _cand.startswith("ANSWER|"):
                        _lines = _cand.splitlines()
                        _answer_idx = 0
                        _new_first = _lines[0][7:].strip()
                        _new_rest = "\n".join(_lines[1:]).strip()
                        _new_body = (f"{_new_first}\n{_new_rest}".strip()
                                     if _new_rest else _new_first)
                        if len(_new_body) < 60:
                            return {"ok": False,
                                    "error": (f"创作类任务交付物空洞：ANSWER "
                                              f"仅 {len(_new_body)} 字且为元"
                                              "描述，重试后仍未产出实质正文"),
                                    "honest_blocked": True}
                        # 正文达标 → 落入下方通用 ANSWER 收集分支返回全文
                    else:
                        return {"ok": False,
                                "error": ("创作类任务交付物空洞：重试未产出 "
                                          f"ANSWER|正文（got: {_cand[:80]}）"),
                                "honest_blocked": True}
        if _answer_idx is not None:
            # UX-J+ fix: ANSWER| 的结论常是多行文本（首行 "ANSWER|标题"，
            # 正文跟在后续行）——只取 ln[7:] 会丢正文（实测复盘结论只剩
            # 标题 9 字符）。收集该行起的全部内容。
            _first = _lines[_answer_idx][7:].strip()
            _rest = "\n".join(_lines[_answer_idx + 1:]).strip()
            _answer = f"{_first}\n{_rest}".strip() if _rest else _first
            return {"ok": True, "blocked": False, "exit_code": 0,
                    "stdout": _answer[:4000]}
        _run_cmds = [ln[4:].strip() for ln in _lines if ln.startswith("RUN|")]
        if _run_cmds:
            outs: list[str] = []
            for _cmd in _run_cmds:
                _rr = _run_one(_cmd, _auto_ro)
                if not _rr.get("ok"):
                    return _rr
                # UX-J+: 标签用实际执行的命令（拦截重试转换后 ≠ 原命令）
                _label = _rr.pop("_executed_command", _cmd)
                outs.append(f"$ {_label}\n{_rr.get('stdout', '')}")
            raw_out = "\n\n".join(outs)
            # FIX-5: 多命令 → 一次 LLM 结论摘要（Observation→Reasoning）。
            # 保留原始 stdout 端到端（[实验]约束 deny 丢弃真实输出），
            # 仅在其前附结论，让 goal_result/面板呈现"分析"而非"粘贴"。
            # 单命令不汇总（避免无谓 token）；预算不足/失败 → 回退原始输出。
            final = raw_out[:4000]
            if len(_run_cmds) > 1:
                summary = self._summarize_execution(description, raw_out[:3000])
                if summary:
                    final = f"【结论摘要】{summary}\n\n【原始输出】\n{raw_out[:3500]}"
            return {"ok": True, "blocked": False, "exit_code": 0,
                    # P2: 自我模型能力实测归因（shell 实测）
                    "capability": "shell",
                    "stdout": final[:4000]}
        raw = _lines[0] if _lines else raw
        # FIX-5b: planning LLM 偶发输出 "NONE|"（判定无法执行）→ 带反馈重规划一次。
        # 弱模型较易对中文多命令任务误判不可执行；复用它已输出的理由让模型
        # 再给一次具体的 RUN 指令，显著降低偶发失败率。仍 NONE 则诚实失败。
        #
        # P1-SELFBOOT (2026-09-09): 自举重试 — 先探测宿主机真实能力
        # （curl/wget/python 是否可用、网络是否通），把事实注入重试 prompt
        # 让 LLM 基于硬件重规划，而不是凭空假设"没有联网能力"。
        if raw.startswith("NONE|") and not _retried_none:
            _retried_none = True
            _no = raw[5:].strip()
            # ── P1-SELFBOOT: 宿主机能力快扫（零依赖子进程） ──
            _cap_probe = self._probe_host_capabilities()
            # 联网类任务（搜索/调研/查）失败时，特别强调 curl + 网络通
            _internet_hint = ""
            if re.search(r"搜索|调研|联网|外网|抓取|最新|GitHub|www|http",
                        description, re.IGNORECASE):
                curl_ok = _cap_probe.get("curl", False)
                net_ok = _cap_probe.get("internet", False)
                py_ok = _cap_probe.get("python3", False)
                _internet_hint = (
                    f"【宿主机真实能力探测】curl={'✓' if curl_ok else '✗'} "
                    f"python3={'✓' if py_ok else '✗'} 外网连通={'✓' if net_ok else '✗'}\n"
                )
                if curl_ok and net_ok:
                    _internet_hint += (
                        "→ curl 和网络都可用，完全可以用 RUN|curl -s --max-time 15 "
                        "真正抓取外部内容。请输出具体的 curl 命令行，不要再说无法联网。\n")
                elif curl_ok and not net_ok:
                    _internet_hint += "→ curl 可用但外网不通（可能是代理/DNS问题）。"
                elif not curl_ok and py_ok:
                    _internet_hint += "→ curl 不可用但 python3 可用，可考虑"
                    _internet_hint += "用 python3 -c 或 python 脚本加 requests/urllib 抓取。"

            raw2 = _first_line(_convert(
                f"规划器判定：{_no}\n{_internet_hint}"
                "请基于以上真实能力重新规划，输出具体 RUN| 或 ANSWER| 动作行。"))
            if raw2.startswith("RUN|"):
                _rr2 = _run_one(raw2[4:].strip(), _auto_ro)
                if _rr2.get("ok"):
                    return {"ok": True, "blocked": False, "exit_code": 0,
                            # P2: 自我模型能力实测归因（shell 实测）
                            "capability": "shell",
                            "stdout": f"$ {raw2[4:].strip()}\n{_rr2.get('stdout','')}"[:4000]}
                return _rr2
            if not raw2.startswith("NONE|"):
                raw = raw2
        if raw.startswith("AGENT_INSTALL|"):
            name = raw.split("|", 1)[1].strip()
            return self._handle_install_action(name, payload.get("approval_id"))
        if raw.startswith("FILE_WRITE|"):
            parts = raw.split("|", 2)
            if len(parts) == 3:
                # S1.1 (白皮书 P1-1): FILE_WRITE 强制审批 — 不再自造
                # approval_id ("task-approved") 绕过守门；无 approval_id
                # 一律入待批队列，无论 OCOS_APPROVAL_MODE 为何值。
                approval_id = payload.get("approval_id")
                if not approval_id:
                    self._enqueue_pending(
                        action_type="file_op",
                        target=parts[1].strip(),
                        payload={"op_type": "file_write",
                                 "target": parts[1].strip(),
                                 "params": {"content": parts[2]}},
                        text=f"FILE_WRITE {parts[1].strip()} "
                             f"(LLM 规划写文件 — 强制待批)")
                    return {"ok": False, "pending": True,
                            "error": ("file_write requires approval — "
                                      "已入待批队列，等待人工批准")}
                _fw = self._handler_file_op(SimpleNamespace(payload={
                    "op_type": "file_write", "target": parts[1].strip(),
                    "params": {"content": parts[2]},
                    "approval_id": approval_id}))
                if _fw.get("ok"):
                    # P2: 自我模型能力实测归因（filesystem 实测）
                    _fw["capability"] = "filesystem"
                return _fw
            return {"ok": False, "error": f"FILE_WRITE 格式错误: {raw[:80]}"}
        if raw.startswith("NONE|"):
            return {"ok": False, "error": f"任务无法执行: {raw[5:].strip()}"}
        return {"ok": False, "error": f"LLM 输出格式不符: {raw[:80]}"}

    def _execution_failure_reason(self, llm: dict, description: str) -> str:
        """FIX-失败遮蔽: 提取执行失败的**真实原因**，替代模糊默认文案。

        优先级: block_reason(沙盒拦截) → error(规划/NONE) → blocked+stderr/
        exit_code 诊断 → 明确兜底（不再用含糊的 "LLM 无法执行此任务"）。
        """
        if llm.get("block_reason"):
            return f"命令被沙盒拦截: {llm['block_reason']}"
        if llm.get("error"):
            # error == 与当前已知（可能间接）是动作/模型原因
            return str(llm["error"])
        parts: list[str] = []
        if llm.get("blocked"):
            parts.append("命令被沙盒拦截（未提供具体原因）")
        if llm.get("stderr"):
            parts.append(f"stderr: {str(llm['stderr'])[:160]}")
        ec = llm.get("exit_code")
        if ec not in (None, 0):
            parts.append(f"exit_code={ec}")
        if parts:
            return "; ".join(parts)
        return f"执行失败（任务: {description[:60]}）：命令被沙盒拦截或模型未能生成可执行动作，且无更多诊断信息"

    def _get_textgen(self):
        """P3-2: 复用缓存的 TextGenerator。"""
        if self._textgen is None:
            from ocos.engines.text_generator import get_text_generator
            self._textgen = get_text_generator()
        return self._textgen

    def _experience_supports(self, description: str,
                             min_confidence: float = 0.7) -> bool:
        """P3.1 (AGI 计划): 经验豁免判定 — 同类高置信经验存在 → True。

        置信度驱动策略：低置信写类任务若检索到高置信（>=0.7）同类经验，
        说明该路径已被验证过，允许直接执行（不升级 ASK）；否则保守升级。
        """
        if getattr(self, "_learning_source", None) is None:
            return False
        try:
            artifacts = self._learning_source(description) or []
        except Exception as e:
            logger.debug("experience support check failed: %s", e)
            return False
        return any(
            float(a.get("confidence", 0.0)) >= min_confidence
            for a in artifacts
        )

    def _memory_decision_context(self, description: str,
                                 limit: int = 5) -> str:
        """记忆直接参与决策 — 统一记忆决策上下文（用户方向）。

        把历史经验/信念/技能/反思聚合为一个**结构化量化决策块**注入规划
        prompt：不只给文本让 LLM 参考，还带**命中条数/类型分布/高置信计数**
        等可量化摘要，使记忆成为决策的一等依据（ocos 作为"生命体"干活时
        优先问记忆），而非仅为抽象 Skill 而存在。带 artifact_id 可审计。

        无记忆/未注入 learning_source → ""（基线路径，行为不变）。
        """
        if getattr(self, "_learning_source", None) is None:
            return ""
        try:
            artifacts = self._learning_source(description) or []
        except Exception as e:
            logger.debug("memory decision context failed: %s", e)
            return ""
        artifacts = [a for a in artifacts if a and a.get("text")]
        if not artifacts:
            return ""
        # 量化摘要: 命中数 / 类型分布 / 高置信计数 / 平均置信度
        n = len(artifacts)
        by_type: dict[str, int] = {}
        high_conf = 0
        conf_sum = 0.0
        for a in artifacts:
            t = a.get("type", "?")
            by_type[t] = by_type.get(t, 0) + 1
            c = float(a.get("confidence", 0.0))
            conf_sum += c
            if c >= 0.7:
                high_conf += 1
        # 依 score（技能>信念>知识>反思）排序，取 top-k
        ordered = sorted(artifacts,
                         key=lambda a: (a.get("score", 0), a.get("confidence", 0)),
                         reverse=True)[:limit]
        type_desc = ", ".join(f"{k}={v}" for k, v in
                              sorted(by_type.items(), key=lambda x: -x[1]))
        head = (f"【记忆决策上下文】命中{n}条相关记忆 "
                f"(类型: {type_desc}; 高置信≥0.7: {high_conf}; "
                f"平均置信 {conf_sum / max(n, 1):.2f})")
        lines = [head]
        for a in ordered:
            aid = str(a.get("artifact_id", ""))[:40]
            text = str(a.get("text", ""))[:110]
            c = float(a.get("confidence", 0.0))
            lines.append(
                f"- [{a.get('type', '?')}] {text} "
                f"(conf={c:.2f}, artifact={aid})")
        try:
            from ocos.monitoring.manager import record_global
            record_global("memory_decision_injected", float(n))
        except Exception:
            pass
        return "\n".join(lines)

    # ── P0-C (2026-09-10): Schema Context — episodes 表列名注入 ──────────

    def _schema_context(self) -> str:
        """P0-C: episodes 表真实列名摘要（只给事实，不给修复建议）。

        只在 DB 路径已知时生效；无 DB / 查询失败 → ""（优雅降级）。
        这是消灭 SQL 幻觉（LLM 编造 content / artifact 等不存在列）的根因修复。
        """
        if not getattr(self, "_db_path", None):
            return ""
        import sqlite3 as _sqlite3
        try:
            conn = _sqlite3.connect(self._db_path)
            cols = conn.execute(
                "PRAGMA table_info(episodes)"
            ).fetchall()
            conn.close()
        except Exception:
            return ""
        if not cols:
            return ""
        col_lines = [f"  - {c[1]} ({c[2]})" for c in cols]
        return (
            "【DB Schema】episodes 表真实列结构（查询前请据此构造 SQL）:\n"
            + "\n".join(col_lines)
        )

    def _memory_conflict_hint(self, description: str) -> str:
        """记忆冲突回落: 记忆给出建议但世界模型无对应对象时显式回落。

        动机: 记忆（经验/信念/技能）可能过时或不适配当前现实；当**记忆命中**
        （学习源有相关产物）却**世界模型可用且查无对象**时，说明记忆所依赖的
        前提在当前现实不成立 → 提示规划 LLM 回落：优先依据命令实际输出/世界
        事实判定，不要盲目套用历史做法。

        无记忆 / 世界不可用 / 世界有对象 → ""（不误报冲突，基线不变）。
        """
        memory_hit = False
        if getattr(self, "_learning_source", None) is not None:
            try:
                memory_hit = bool(self._learning_source(description) or [])
            except Exception:
                memory_hit = False
        if not memory_hit:
            return ""
        if self._world_source is None:
            return ""
        ctx = {}
        try:
            ctx = self._world_source(description) or {}
        except Exception:
            return ""
        if not ctx.get("available"):
            return ""
        entities = ctx.get("entities") or []
        if entities:
            return ""  # 世界有对象 → 记忆可适用，无冲突
        try:
            from ocos.monitoring.manager import record_global
            record_global("memory_conflict_fallback", 1.0)
        except Exception:
            pass
        return ("【记忆冲突回落】存在相关历史经验，但当前世界模型中未检索到"
                "对应对象；历史记忆可能过时或不适用于当前现实。请优先依据命令"
                "实际输出与世界状态判定，不要盲目套用历史做法，必要时诚实说明。")

    def _prior_world(self, description: str, limit: int = 5) -> str:
        """P2.1 (AGI 计划): 世界状态注入任务执行规划器。

        与 MasterAgent.think/plan 侧的 world_context 消费互补：本方法把
        当前世界实体状态带给**执行规划 LLM**，让 RUN 命令选择/参数化
        基于世界事实（感知→世界模型→决策，修复只写不读断点）。

        空世界/未注入 → ""（优雅降级，基线路径）。
        """
        if self._world_source is None:
            return ""
        try:
            ctx = self._world_source(description) or {}
        except Exception as e:
            logger.debug("world state retrieval failed: %s", e)
            return ""
        if not ctx.get("available"):
            return ""
        entities = ctx.get("entities") or []
        if not entities:
            return ""
        lines = ["【世界状态】"]
        for ent in entities[:limit]:
            name = ent.get("name") or ent.get("entity_id") or "?"
            etype = ent.get("entity_type") or "?"
            state = ent.get("state") or {}
            state_str = ", ".join(f"{k}={v}" for k, v in
                                  list(state.items())[:4])
            lines.append(f"- {name} ({etype}) [{state_str}]")
        try:
            from ocos.monitoring.manager import record_global
            record_global("world_state_injected", float(len(entities[:limit])))
        except Exception:
            pass
        return "\n".join(lines)

    def _prior_agents(self, description: str, limit: int = 8) -> str:
        """AGI 能力补全: 注入可用智能体软件清单到规划 prompt。

        使规划 LLM 知道本机有哪些智能体软件（openclaw/codex/claude/...）、
        调用方式（CLI 路径 / HTTP 端点）与版本 — 任务涉及"调用 XX"时可规划
        出真实可执行的命令，而非漂移成通用系统分析或诚实失败。
        """
        if self._agent_source is None:
            return ""
        try:
            agents = self._agent_source(description) or []
        except Exception as e:
            logger.debug("agent source retrieval failed: %s", e)
            return ""
        if not agents:
            return ""
        # P1-1 (2026-09-08 事件复盘): 创作/分析类任务不注入智能体清单 —
        # 「制定升级计划」被强制 RUN 后，LLM 抓住注入的「只读示例:
        # <cli> --version」话术，输出 cat 版本号噪声。创作类任务的交付物
        # 是正文，清单只会成为跑偏磁铁；描述显式引用智能体名的照常注入。
        _explicit_ref = any(
            str(a.get("name", "")) and str(a.get("name", "")) in description
            for a in agents)
        if not _explicit_ref and _AUTHORING_ANALYSIS_RE.search(description or ""):
            return ""
        lines = ["【可用智能体软件】"]
        for a in agents[:limit]:
            name = str(a.get("name", "?"))
            if not a.get("available"):
                lines.append(f"- {name}: 未发现（不可调用）")
                continue
            kind = a.get("kind", "cli")
            if kind == "cli":
                ver = f" ({str(a.get('version', ''))[:40]})" \
                    if a.get("version") else ""
                lines.append(f"- {name}: CLI {a.get('cli_path', '')}{ver}")
                # 关键引导: 明确该 CLI 已获白名单放行、可在 RUN| 行直接执行
                # （否则规划 LLM 常把"调用智能体"漂移成通用系统分析）。
                # 调用名用 _agent_invoke — name↔命令名错位时给绝对路径
                _inv = self._agent_invoke(a)
                lines.append(
                    f"  → 可直接执行: {_inv} <参数>"
                    f"（只读示例: {_inv} --version）")
            elif kind == "http":
                lines.append(f"- {name}: HTTP {a.get('api_endpoint', '')}")
        try:
            from ocos.monitoring.manager import record_global
            record_global("agent_injected", float(len(agents[:limit])))
        except Exception:
            pass
        return "\n".join(lines)

    def _agent_hint(self, description: str) -> str:
        """AGI 能力补全: 任务显式引用已发现智能体 → 强制规划为直接调用。

        规划 LLM 常把"调用 XX 智能体"漂移成通用系统分析（uname/df 模板
        固化）；当描述命中已发现可用 agent 名时，追加强制指令把规划拉回
        真实调用。未命中/未注入 → ""（基线路径不变）。
        """
        if self._agent_source is None or not description:
            return ""
        try:
            agents = self._agent_source(description) or []
        except Exception:
            return ""
        hints: list[str] = []
        for a in agents:
            name = str(a.get("name", ""))
            # python3 为测试辅助/通用运行时，不算外部智能体软件
            if not name or name in ("python3",) or not a.get("available"):
                continue
            if name in description:
                if a.get("kind", "cli") == "cli":
                    _inv = self._agent_invoke(a)
                    hints.append(
                        f"任务明确引用智能体「{name}」：请直接输出 RUN|{_inv} <参数>"
                        f"（已获白名单放行，只读示例: RUN|{_inv} --version），"
                        "不要改用 uname/df 等其他系统命令，也不要拆分分析子任务。")
                else:
                    hints.append(
                        f"任务明确引用智能体「{name}」（HTTP "
                        f"{a.get('api_endpoint', '')}）：请输出 "
                        "RUN|curl -s <该端点> 或诚实说明无法调用。")
        if not hints:
            return ""
        return "【智能体调用强制指令】\n" + "\n".join(hints)

    def _agent_forced_call(self, description: str) -> str:
        """AGI 能力补全: 任务显式引用的已发现可用智能体名（保真闸门用）。

        描述命中已发现可用 CLI 智能体（codex 等）→ 返回可执行调用名
        （_agent_invoke: name↔命令名错位时为 cli_path 绝对路径），调用方
        据此在规划输出未调用它时强制纠正；未命中/不可用 → ""（不干预）。
        """
        if self._agent_source is None or not description:
            return ""
        try:
            agents = self._agent_source(description) or []
        except Exception:
            return ""
        for a in agents:
            name = str(a.get("name", ""))
            if not name or name in ("python3",) or not a.get("available"):
                continue
            if a.get("kind", "cli") != "cli":
                continue  # 保真闸门仅针对 CLI（HTTP 走提示引导）
            if name in description:
                return self._agent_invoke(a)
        return ""

    @staticmethod
    def _agent_invoke(a: dict) -> str:
        """智能体可执行调用名 — name 与 cli_path 命令名一致用短名，
        错位时退回 cli_path 绝对路径（防 RUN|<名> 落地 127，如 opentale
        误配 ln 候选的时代命令名与实际 CLI 不一致）。"""
        name = str(a.get("name", ""))
        path = str(a.get("cli_path", "") or "")
        if path and os.path.basename(path) != name:
            return path
        return name or path

    def _boot_context_hint(self) -> str:
        """启动自省先验 — 本 boot 环境实测快照注入（适应力读侧）。

        数据源: ~/.ocos/boot_context.json（daemon 每次启动时由
        boot_awareness 写入，全部为实测真值）。让目标执行基于当前
        boot 的真实环境（GPU/网络/磁盘/重启状态）规划，而非过时记忆
        或幻觉。文件缺失/解析失败 → ""（诚实沉默，零开销）。
        """
        try:
            import json as _json
            from pathlib import Path as _Path
            p = _Path.home() / ".ocos" / "boot_context.json"
            d = _json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        net_txt = {"full": "内外网畅通", "domestic_only": "仅国内可达"
                   "（国际外联任务预计失败，勿承诺外部调研）",
                   "offline": "完全离线（外联任务不可行，仅本地能力）"
                   }.get(d.get("network_state"), "未知")
        reboot = ""
        if d.get("reboot_detected"):
            dt = d.get("downtime_h")
            reboot = f"（宿主机经历重启" + (
                f"，停机约 {dt:.1f}h）" if dt else "）")
        gpu = d.get("gpu") or "未检出"
        return ("【宿主环境快照（本 boot 启动自省实测）】"
                f"GPU={gpu}；网络={net_txt}；"
                f"磁盘可用={d.get('disk_avail_g')}G；"
                f"内存可用={d.get('mem_avail_g')}G；"
                f"CPU={d.get('cpu_cores')}核{reboot}")

    def _self_knowledge_hint(self, description: str) -> str:
        """自我认知事实块 — 自省/差距/总结类任务注入真实能力事实。

        缺陷史（2026-09-07 对话审计）: 执行器 LLM 只见复盘素材，不知道
        系统已具备的能力（自我模型/学习闭环/持久记忆/自主目标生成），
        在"AI 与数字生命差距"类任务中产出"无自我模型、无经验沉淀、
        完全被动"等关于自身的幻觉结论。本块全部为实测真值，无 LLM
        参与生成；非自省类任务 → ""（零开销）。
        """
        if not self._db_path or self._db_path == ":memory:":
            return ""
        text = description or ""
        if not any(k in text for k in
                   ("复盘", "总结", "差距", "自我", "自身", "能力",
                    "数字生命", "成长", "反思", "学习")):
            return ""
        facts: list[str] = ["【自我能力事实（实测真值，分析自身必须引用）】"]
        try:
            from ocos.self.agent_self_model import AgentSelfModel
            facts.append(AgentSelfModel(self._db_path).render())
        except Exception:
            logger.debug("self knowledge hint: self model unavailable",
                         exc_info=True)
        try:
            import sqlite3 as _sq
            conn = _sq.connect(self._db_path)
            ep = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            lessons = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE source='lesson'"
            ).fetchone()[0]
            goals7d = conn.execute(
                "SELECT COUNT(*) FROM goals WHERE status='COMPLETED' "
                "AND updated_at >= ?",
                ((datetime.now(timezone.utc)
                  - timedelta(days=7)).isoformat(),)).fetchone()[0]
            skills = 0
            try:
                skills = conn.execute(
                    "SELECT COUNT(*) FROM skill_graph").fetchone()[0]
            except _sq.OperationalError:
                pass
            conn.close()
            injections = sum(
                1 for m in self._read_learning_marks()
                if m.get("type") == "lesson_prior_injected")
            facts.append(
                f"  持久记忆: episodes={ep}, lessons={lessons}, "
                f"技能图={skills}")
            facts.append(
                f"  学习闭环: lesson 先验注入（累计）={injections}；"
                f"近7天完成目标={goals7d}（自主提案经认领执行——"
                f"系统具备自主目标生成能力）")
        except Exception:
            logger.debug("self knowledge hint: db stats unavailable",
                         exc_info=True)
        facts.append(
            "【事实约束】上述为系统已具备能力的实测证据。分析自身/差距时"
            "必须以此为据，不得声称系统缺失自我模型、经验沉淀、持久记忆、"
            "自主目标生成或学习闭环；真实差距应指向证据中的具体短板"
            "（如证据不完整、模板固化），并区分'我作为执行器看到的上下文'"
            "与'系统整体能力'。")
        out = "\n".join(facts)[:1400]
        logger.info("self knowledge hint injected: %d chars (desc=%s)",
                    len(out), text[:40])
        return out

    def _retrospect_hint(self, description: str) -> str:
        """UX-J+: 复盘/总结/学习类任务 → 注入最近 goal_result 结论摘要。

        实测学习总结目标因拿不到真实执行记录，跑偏到 ls/扫目录"复盘"
        （部分达成）。此处把最近 goal_result episode 的【结论摘要】直接
        作为复盘素材注入，并显式禁止文件系统取材。非复盘类任务 → ""。
        """
        if not self._db_path or self._db_path == ":memory:":
            return ""
        text = description or ""
        if not any(k in text for k in
                   ("复盘", "总结", "学习", "回顾", "经验沉淀")):
            return ""
        try:
            import sqlite3 as _sq
            conn = _sq.connect(self._db_path)
            rows = conn.execute(
                "SELECT substr(decision,1,800), created_at FROM episodes "
                "WHERE tags LIKE '%goal_result%' "
                "ORDER BY rowid DESC LIMIT 4").fetchall()
            conn.close()
        except Exception as e:
            logger.debug("retrospect hint query failed: %s", e)
            return ""
        if not rows:
            return ""
        lines = ["【近期目标执行结果（复盘素材，真实记录）】"]
        for d, t in rows:
            head = str(d).split("【原始输出】")[0].strip()
            lines.append(f"[{str(t)[:16]}]\n{head[:500]}")
        lines.append(
            "以上为真实执行记录——复盘/总结必须**只基于这些内容**作答，"
            "禁止重新执行 uname/df/free/ls 等系统采集命令，禁止扫描文件"
            "系统获取信息。")
        logger.info("retrospect hint injected: %d chars (desc=%s)",
                    sum(len(x) for x in lines), text[:40])
        return "\n\n".join(lines)

    def _world_hint(self, description: str) -> str:
        """P2.2 (AGI 计划): 世界模型前置校验注记。

        世界可用但描述中未发现任何已知实体 → 返回注记（提示规划器：
        目标引用的对象不在当前世界模型中，应诚实说明而非空跑/编造）。
        空世界/未注入 → ""（默认零传感器优雅降级，不阻断任务）。
        """
        if self._world_source is None or not description:
            return ""
        try:
            ctx = self._world_source(description) or {}
        except Exception as e:
            logger.debug("world hint retrieval failed: %s", e)
            return ""
        if not ctx.get("available"):
            return ""
        entities = ctx.get("entities") or []
        if not entities:
            return ""
        names = {str(e.get("name") or e.get("entity_id") or "")
                 for e in entities}
        names = {n for n in names if n}
        if not names:
            return ""
        # 描述与已知实体名是否重叠（2-gram / 子串）
        desc = description
        overlap = any(
            n in desc or any(g in n for g in
                             {desc[i:i + 2] for i in range(len(desc) - 1)}
                             if g.strip())
            for n in names)
        if overlap:
            return ""
        return ("注：目标引用的对象不在当前世界模型中"
                f"（已知实体: {', '.join(sorted(names)[:5])}）— "
                "若任务依赖该对象，请说明无法获取而非编造结果")

    # ── Phase 2 (Mutation): ActionParser — 结构化 LLM 输出 ──────────

    def _parse_actions(self, raw_text: str) -> list[dict]:
        """Phase 2: 从 LLM raw 输出解析结构化 Action 列表。

        冻结约束 (Architecture v1.2):
          - Parsing only. No inference. No completion. No planning.
          - 只识别 RUN|/NONE|/ANSWER|/FILE_WRITE|/AGENT_INSTALL 五种类型。
          - 未知类型 → 忽略（保持和现有 _lines 循环一致）。
          - 与 bridge.py line 1424 原有 _lines 循环行为 1:1 等价。

        返回: [{"type":"RUN", "command":"..."}, {"type":"NONE", "reason":"..."}, ...]
        """
        lines = [ln.strip().strip("`") for ln in (raw_text or "").splitlines()
                 if ln.strip()]
        actions: list[dict] = []
        for ln in lines:
            if ln.startswith("RUN|"):
                actions.append({"type": "RUN", "command": ln[4:].strip()})
            elif ln.startswith("NONE|"):
                actions.append({"type": "NONE", "reason": ln[5:].strip()})
            elif ln.startswith("ANSWER|"):
                actions.append({"type": "ANSWER", "content": ln[7:].strip()})
            elif ln.startswith("FILE_WRITE|"):
                parts = ln.split("|", 2)
                actions.append({
                    "type": "FILE_WRITE",
                    "path": parts[1].strip() if len(parts) > 1 else "",
                    "content": parts[2].strip() if len(parts) > 2 else "",
                })
            elif ln.startswith("AGENT_INSTALL|"):
                actions.append({
                    "type": "AGENT_INSTALL",
                    "name": ln.split("|", 1)[1].strip(),
                })
            # 未知类型 → 忽略
        return actions

    def _actions_to_lines(self, actions: list[dict]) -> list[str]:
        """Phase 2: Action dict 列表 → _lines 格式（临时，Phase 3 后逐步替换）。"""
        result = []
        for a in actions:
            t = a.get("type", "")
            if t == "RUN":
                result.append(f"RUN|{a.get('command', '')}")
            elif t == "NONE":
                result.append(f"NONE|{a.get('reason', '')}")
            elif t == "ANSWER":
                result.append(f"ANSWER|{a.get('content', '')}")
            elif t == "FILE_WRITE":
                result.append(f"FILE_WRITE|{a.get('path', '')}|{a.get('content', '')}")
            elif t == "AGENT_INSTALL":
                result.append(f"AGENT_INSTALL|{a.get('name', '')}")
        return result

    def _prior_task_results(self, description: str, limit: int = 2) -> str:
        """FIX-4: 同类任务历史结果 — 任务转换前的执行经验注入。

        FIX-4v2: 仅注入**成功（✓/✅）**历史。此前把失败历史一并注入会在
        同一任务反复失败时形成负反馈循环：规划 LLM 看到"同类历史全 ✗
        无法执行"→ 跟随输出 NONE| → 又记为失败 → 循环自我强化。有成功
        经验时才注入；无成功历史则空（走原始 prompt）。
        """
        if not self._db_path or not description:
            return ""
        desc = description.strip()
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT decision FROM episodes "
                "WHERE source='goal_result' AND action='goal_result' "
                "ORDER BY created_at DESC LIMIT 40").fetchall()
            conn.close()
        except Exception as e:
            logger.debug("prior task results failed: %s", e)
            return ""

        dg = {desc[i:i + 2] for i in range(len(desc) - 1)}
        if not dg:
            return ""
        hits: list[str] = []
        for r in rows:
            d = str(r["decision"] or "").strip()
            if not d:
                continue
            # FIX-4v2: 只取成功记录, 避免失败历史诱导规划器输出 NONE
            if not d.startswith("✓") and not d.startswith("✅"):
                continue
            snippet = d.split("→", 1)[0] if "→" in d else d
            sg = {snippet[i:i + 2] for i in range(len(snippet) - 1)}
            if not sg:
                continue
            overlap = len(dg & sg) / max(len(dg | sg), 1)
            if overlap >= 0.2:
                hits.append(d[:400])
                if len(hits) >= limit:
                    break
        if not hits:
            return ""
        return "同类历史任务结果:\n" + "\n".join(hits)

    # ── L7/L8 学习闭环: 失败先验消费（2026-09-07 立项）─────────────────

    #: cause → 矫正性程序（正向"先做什么"，非失败叙事——规避 FIX-4
    #: 负反馈循环：其成因为失败结果史诱导规划器跟随 ✗/NONE 先例，程序式
    #: 指引不含该诱导结构，且不提供 NONE 逃逸框）
    _CAUSE_PROCEDURES: dict = {
        "ambiguous_task": "先澄清目标边界与成功标准（拆解为明确子步骤），再逐步执行",
        "execution_error": "先校验输入与工具可用性，分小步执行并在每步后核对结果再继续",
        "permission_denied": "先核验所需权限/审批是否具备，缺失则先走审批提案，不要直接执行",
        # Phase A0+: timeout 升级为 C 类五要素模板（cause_to_procedure 自动生成的 timeout 通用退化模板）
        # 格式对齐: 【<任务域>程序】先<正向步骤>；每批<批量上限>；<等待条件>。禁止<失败签名>。成功=<条件>
        "timeout": "【超时规避程序】先检查当前操作规模；分批执行；等每批完成。禁止单次执行过多。成功=不超时",
        "tool_unavailable": "先探测所需工具/命令是否可用，不可用时改用替代方案或诚实说明",
        "llm_conversion_failed": "输出严格遵循要求的动作行格式（每行一条，不附加解释）",
    }

    def _failure_prior_hint(self, description: str) -> str:
        """L7: 失败先验 — 按 cause 注入矫正性程序指引（学习闭环消费侧）。

        此前 lesson 只进统计管道不消费（同型失败持续复发，failure_
        recurrence=100%）。与 _prior_task_results 的分工：后者注入同类
        **成功**历史；本方法注入 cause 级**矫正程序**。匹配两级：
          a. 定向——任务描述与 lesson.goal_pattern bi-gram 重叠 ≥0.20；
          b. cause 级兜底——无定向命中时取 30 天内复发（≥2 条）最近的
             cause（复发本身即模式匹配失效的信号）。
        上限 1 块防提示膨胀；命中即 learning.jsonl 留痕 + 打点（L8 观测）。
        """
        if not self._db_path or not description:
            return ""
        desc = description.strip()
        if not desc:
            return ""
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.now(timezone.utc)
                      - timedelta(days=30)).isoformat()
            rows = conn.execute(
                "SELECT tags, context, created_at FROM episodes "
                "WHERE source='lesson' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 60", (cutoff,)).fetchall()
            conn.close()
        except Exception as e:
            logger.debug("failure prior query failed: %s", e)
            return ""
        dg = {desc[i:i + 2] for i in range(len(desc) - 1)}
        if not dg:
            return ""
        registry: dict = {}
        for r in rows:
            try:
                tags = json.loads(r["tags"] or "[]")
            except (ValueError, TypeError):
                tags = []
            cause = next((t for t in (tags if isinstance(tags, list) else [])
                          if t and t != "failure_lesson"), None)
            if not cause or cause not in self._CAUSE_PROCEDURES:
                continue
            info = registry.setdefault(
                cause, {"count": 0, "goal_pattern": "", "seen": ""})
            info["count"] += 1
            if not info["seen"]:
                info["seen"] = str(r["created_at"] or "")
            if not info["goal_pattern"]:
                try:
                    ctx = json.loads(r["context"] or "{}")
                except (ValueError, TypeError):
                    ctx = {}
                info["goal_pattern"] = str(ctx.get("goal_pattern", "") or "")
        if not registry:
            return ""
        chosen: list = []                       # [(cause, mode)]
        for cause, info in registry.items():    # a) 定向匹配
            gp = info["goal_pattern"].strip()
            if not gp:
                continue
            sg = {gp[i:i + 2] for i in range(len(gp) - 1)}
            if sg and len(dg & sg) / max(len(dg | sg), 1) >= 0.20:
                chosen.append((cause, "pattern"))
        if not chosen:                          # b) 复发 cause 兜底
            recurred = [(i["seen"], c) for c, i in registry.items()
                        if i["count"] >= 2]
            if recurred:
                recurred.sort(reverse=True)
                chosen.append((recurred[0][1], "recurrence"))
        if not chosen:
            return ""
        cause, mode = chosen[0]
        self._audit_learning_mark("lesson_prior_injected", cause=cause,
                                  mode=mode)
        # Phase A0+: 优先用 cause_to_procedure(cause, goal_pattern) 动态生成，
        # fallback 静态 _CAUSE_PROCEDURES[cause]（确保非 timeout cause 也有退化）
        gp = registry.get(cause, {}).get("goal_pattern", "")
        procedure_text = ""
        try:
            from ocos.learning.experience_learning import cause_to_procedure
            procedure_text = cause_to_procedure(cause, gp)
        except Exception:
            pass
        if not procedure_text and cause in self._CAUSE_PROCEDURES:
            procedure_text = self._CAUSE_PROCEDURES[cause]
        elif not procedure_text:
            return ""
        return (f"【执行程序提示】针对{cause}类任务，请按以下程序执行：\n"
                f"{procedure_text}")

    def _skill_registry(self):
        """技能注册表（主库同目录 capability.db；无库返回 None）。"""
        if not self._db_path:
            return None
        try:
            from pathlib import Path as _P
            from ocos.capability.skill_registry import SkillRegistry
            reg = SkillRegistry(
                db_path=str(_P(self._db_path).parent / "capability.db"))
            reg.init_db()
            return reg
        except Exception as e:
            logger.debug("skill registry unavailable: %s", e)
            return None

    def _skill_replay_hint(self, description: str) -> str:
        """V2 技能重放（提示级）: 已验证技能图 → 按其步骤执行。

        经验→技能闭环的读侧：dream 巩固合成的 SkillGraph（同型成功经验
        ≥2 次）经 bi-gram 匹配任务描述（≥0.30），命中即把技能图步骤注入
        规划 prompt（"按已验证步骤执行"），并 learning.jsonl 留痕——
        vitals skill_replay_hit_rate = 命中/触发。图执行级重放（引擎路由）
        由 supervisor capability_hints.skill_graph_id 路径承载，不在此层。
        """
        if not self._db_path or not description:
            return ""
        reg = self._skill_registry()
        if reg is None:
            return ""
        try:
            graphs = reg.list_graphs()
        except Exception as e:
            logger.debug("skill graphs load failed: %s", e)
            return ""
        if not graphs:
            return ""                       # 无技能库 → 不打点（无重放通道）
        desc = description.strip()
        dg = {desc[i:i + 2] for i in range(len(desc) - 1)}
        if not dg:
            return ""
        best = None
        for g in graphs:
            name = (g.name or "").strip()
            text = f"{g.name} {g.description}".strip()
            sg = {text[i:i + 2] for i in range(len(text) - 1)}
            if not sg:
                continue
            ov = len(dg & sg) / max(len(dg | sg), 1)
            # 名字级强信号：合成技能的 name 即任务模式，完整出现于
            # 任务描述时整体 Jaccard 常被描述噪声稀释到阈值下 —
            # 直接视为命中（名字 ≥4 字防短名误配）
            if len(name) >= 4 and name in desc:
                ov = 1.0
            if ov >= 0.30 and (best is None or ov > best[1]):
                best = (g, ov)
        if best is None:
            self._audit_learning_mark("skill_replay", matched=False)
            return ""
        g = best[0]
        try:
            full = reg.load_graph(g.id) or g   # list_graphs 不含完整 skill
        except Exception:
            full = g
        steps = [f"{i+1}. {s.description or s.name}"
                 for i, s in enumerate(full.skills[:5])]
        self._audit_learning_mark("skill_replay", matched=True,
                                  graph_id=g.id)
        return ("【技能重放】同类任务已有已验证技能图《%s》，"
                "优先按以下已验证步骤执行：\n%s" % (g.name, "\n".join(steps)))

    def _read_learning_marks(self) -> list[dict]:
        """learning.jsonl 全量解析（坏行跳过）— 与 vitals 同数据源。"""
        try:
            from pathlib import Path as _P
            base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
            audit_dir = (_P(base).expanduser() if base
                         else _P.home() / ".ocos" / "audit")
            path = audit_dir / "learning.jsonl"
            if not path.exists():
                return []
            out: list[dict] = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
            return out
        except Exception:
            logger.debug("learning marks read failed", exc_info=True)
            return []

    def _audit_learning_mark(self, mark_type: str, **fields: Any) -> None:
        """L8: 学习闭环观测 — learning.jsonl 留痕 + 进程级打点。

        OCOS_AUDIT_DIR 可覆写（测试/多实例隔离，与 autonomy.jsonl 同
        约定）。vitals 的 _learning_metrics 消费该文件产出消费观测指标。
        """
        try:
            from pathlib import Path as _P
            base = os.environ.get("OCOS_AUDIT_DIR", "").strip()
            audit_dir = (_P(base).expanduser() if base
                         else _P.home() / ".ocos" / "audit")
            path = audit_dir / "learning.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            entry = {"ts": datetime.now(timezone.utc).isoformat(),
                     "type": mark_type, **fields}
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("learning audit mark failed", exc_info=True)
        try:
            from ocos.monitoring.manager import record_global
            record_global(mark_type, 1.0,
                          labels={k: str(v) for k, v in fields.items()
                                  if k in ("cause", "matched")})
        except Exception:
            pass

    def _summarize_execution(self, task_description: str,
                             execution_text: str) -> str:
        """FIX-5: 多命令执行结果的结论性摘要（Observation→Reasoning 闭环）。

        把聚合 stdout 喂给一次 LLM，产出中文结论摘要（关键数据/是否达成）。
        预算不足返回 ""（回退原始输出）；LLM 异常也返回 ""（诚实降级，
        不因摘要失败而丢弃真实 stdout）。
        """
        if not execution_text:
            return ""
        budget_ok, budget_reason = self._llm_budget_ok()
        if not budget_ok:
            logger.warning("summary skipped (budget): %s", budget_reason)
            return ""
        try:
            import asyncio
            tg = self._get_textgen()
            if True:  # S3.7: 代理隔离已下沉到 provider
                prompt = (
                    f"任务：{task_description[:200]}\n\n"
                    f"以下是该任务多条命令的执行输出：\n{execution_text[:3000]}\n\n"
                    "请用中文给出结论性摘要：提取关键数据/结果，判断是否达成任务。"
                    "若任务要求总结/方案/计划类交付物，基于执行输出直接产出该"
                    "交付物正文（可到 500 字）；否则控制在 200 字以内。"
                    "不要复述命令输出全文，只输出摘要。"
                )
                raw = asyncio.run(tg._provider.generate(
                    prompt,
                    system_prompt="你是 OCOS 的执行结果分析器。只输出结论摘要。",
                    temperature=0.2, max_tokens=800))
                return raw.strip()
        except Exception as e:
            logger.warning("execution summary failed (fallback to raw): %s", e)
            return ""

    def _llm_budget_ok(self) -> tuple[bool, str]:
        """P2-2: LLM 日预算 — 默认 500 次/天（OCOS_LLM_DAILY_CAP 可调）。"""
        import os as _os
        today = datetime.now(timezone.utc).date().isoformat()
        if self._llm_calls_date != today:
            self._llm_calls_date = today
            self._llm_calls_today = 0
        cap = int(_os.environ.get("OCOS_LLM_DAILY_CAP", "500"))
        if self._llm_calls_today >= cap:
            return False, f"LLM 日预算已用尽（{cap}/天）— 任务转待批明日再试"
        self._llm_calls_today += 1
        # S3.5: LLM 调用计数器（进程级监控埋点；未装配时静默 no-op）
        try:
            from ocos.monitoring.manager import record_global
            record_global("ocos_llm_calls_total", 1.0)
        except Exception:
            pass
        return True, ""

    def _llm_available(self) -> bool:
        import os
        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return True
        from ocos.engines.text_generator import _read_llm_config
        return bool(_read_llm_config().get("api_key"))

    def execute_approved(self, action_type_name: str,
                         payload: dict | None = None):
        """PW-1.4: 审批后的统一执行入口 — dispatch + 生命周期留痕。

        approvals（CLI/API/REPL）统一走这里, 保证每笔批准动作都有
        ExecutionAudit + event_memory 留痕。
        S1.1 (白皮书 P1-1): payload 携带 approval_id 时必须能溯源到
        pending_actions 表中已批准的行, 伪造 ID 一律拒绝并留痕。
        """
        payload = dict(payload or {})
        approval_id = payload.get("approval_id")
        if approval_id and not self._verify_approval(approval_id):
            self._record_lifecycle(
                "result", self._agent_id,
                {"status": "blocked",
                 "summary": f"forged/unapproved approval_id: {approval_id}"})
            from types import SimpleNamespace
            return SimpleNamespace(
                action_type=action_type_name, target="approval-check",
                payload=payload, status="failed",
                result={"ok": False,
                        "error": f"invalid or unapproved approval_id: "
                                 f"{approval_id}"})
        dispatched = self.dispatcher.dispatch_by_name(
            action_type_name, payload)
        if dispatched is None:
            self._record_lifecycle(
                "result", self._agent_id,
                {"status": "blocked", "summary": f"no executor: {action_type_name}"})
            return dispatched
        self._record_lifecycle(
            "action", (action_type_name
                       if isinstance(action_type_name, str)
                       else action_type_name),
            {"status": dispatched.status,
             "summary": self._summarize(dispatched)[:200]})
        return dispatched

    # ── PW-1.4: 执行生命周期留痕（event_memory） ─────────────────────────

    def _record_lifecycle(self, event_type: str, source: str,
                          payload: Any) -> None:
        """能力执行 → event_memory 生命周期事件（SQLite 持久化, 失败不阻断）。"""
        try:
            if not self._db_path or self._db_path == ":memory:":
                return
            from ocos.event_memory.event_store import EventStore
            from ocos.event_memory.event_types import (
                CognitiveEvent, CognitiveEventType, EventConfidence,
            )
            from ocos.storage.connection import get_connection
            if self._lifecycle_store is None:
                conn = get_connection(self._db_path)
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS event_store (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE,
                        event_type TEXT,
                        payload TEXT,
                        source TEXT,
                        created_at TEXT
                    )""")
                conn.commit()
                self._lifecycle_store = EventStore(connection=conn)
            etype = (CognitiveEventType(event_type)
                     if event_type in [e.value for e in CognitiveEventType]
                     else CognitiveEventType.ACTION)
            self._lifecycle_store.append(CognitiveEvent(
                event_id=f"EVT-{uuid.uuid4().hex[:12]}",
                event_type=etype, source=source,
                payload=payload, confidence=EventConfidence.CERTAIN,
            ))
        except Exception as e:
            logger.debug("lifecycle record failed: %s", e)

    # ── S3.2: 入口权限网关前检 ───────────────────────────────────────────

    def _gateway_scan(self, text: str) -> str | None:
        """决策文本进入裁决管线前的权限网关扫描（白皮书 P2-5 生产接线）。

        返回 None = 放行；否则返回拦截原因。网关故障 fail-closed。
        未注入时惰性创建默认 PermissionGateway（与 ChatResponder S1.3
        同模式——bridge 下游另有 PermissionGuard 语义双检 + 沙盒白名单）。
        """
        try:
            from ocos.capability.permission_gateway import PermissionGateway
        except Exception as e:
            logger.warning("permission gateway unavailable, skip scan: %s", e)
            return None
        if self._permission_gateway is None:
            self._permission_gateway = PermissionGateway()
        from types import SimpleNamespace
        contract = SimpleNamespace(
            contract_id=f"bridge-{self._agent_id}",
            agent_id="decision_bridge",
            action="decision_text",
            input_spec={"text": str(text)[:2000]})
        try:
            result = self._permission_gateway.validate(
                contract, scope="text")
        except Exception as e:
            logger.warning("gateway scan error (fail-closed): %s", e)
            return f"gateway error: {e}"
        if getattr(result, "allowed", True):
            return None
        violations = getattr(result, "violations", None) or []
        return ("; ".join(str(v) for v in violations[:3])
                or getattr(result, "reason", "") or "denied by gateway")[:200]

    # ── 待批队列 ──────────────────────────────────────────────────────────

    def _verify_approval(self, approval_id: str) -> bool:
        """S1.1 (白皮书 P1-1): approval_id 必须对应 pending_actions 表中
        已批准（status='approved'）的行；无 PendingStore 时 fail-closed。
        """
        if self._pending_store is None:
            logger.warning("approval verification failed (no pending store, "
                           "fail-closed): approval_id=%s", approval_id)
            return False
        try:
            row = self._pending_store.get(str(approval_id))
        except Exception as e:
            logger.warning("approval verification error: %s", e)
            return False
        if row is None or row.get("status") != "approved":
            logger.warning("approval verification failed: approval_id=%s "
                           "(missing or not approved)", approval_id)
            return False
        return True

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
