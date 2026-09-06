"""ocos.daemon.factory — 生产装配层（P1-B import 规则合规）。

将 CLI 入口的组件组装逻辑下沉到 daemon 包，使
ocos.interaction.cli.commands 只依赖 ocos.daemon 门面，
不再直连 agent/capability/runtime 内核组件（宪法 import 规则）。

用法:
    from ocos.daemon.factory import build_master_agent
    agent = build_master_agent(agent_id="ocos")
"""

from __future__ import annotations

import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def _make_confidence_source(db_path: str):
    """FIX-6: L8 元认知置信度 source（DecisionBridge.execute_dag_task 消费）。

    签名: callable(description, task_type) → 含 should_escalate/reason 的对象。
    用 CapabilityConfidence 评估；学习规则 best-effort 加载，失败/为空 → 返回
    "none"（安全不干预，仅当前无历史时保持默认分级）。
    """
    def _load_rules(description: str) -> list[dict]:
        """FIX-02 Option A: 从 SQLite episodes 表统计近期历史规则。

        直接查 DB 替代 LearningEngine（原构造签名不兼容），返回
        [{task_pattern, success_rate, success_count, fail_count}] 格式。
        失败/无数据 → 返回 []（安全兜底，不干预决策）。
        """
        if not db_path:
            return []
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # 查近 30 天 goal_result episodes
            cur.execute("""
                SELECT outcome
                FROM episodes
                WHERE action = 'goal_result'
                  AND created_at >= datetime('now', '-30 days')
                ORDER BY created_at DESC
                LIMIT 50
            """)
            rows = cur.fetchall()
            conn.close()

            # 统计与当前描述匹配的 bi-gram 成功率
            # FIX-02: 使用本地函数替代外部依赖（避免引入新模块）
            def tokenize_bi_grams(text: str) -> set:
                """简单 bi-gram 分词：相邻字符对。"""
                text = text.strip()
                return {text[i:i+2] for i in range(len(text) - 1)} if len(text) >= 2 else set()

            desc_gms = tokenize_bi_grams(description.lower())
            if not desc_gms:
                return []

            success_count = 0
            fail_count = 0
            for row in rows:
                try:
                    out = __import__('json').loads(row["outcome"] or "{}")
                    words = set(out.get("words", []) or [])
                    if words & desc_gms:
                        if out.get("success"):
                            success_count += 1
                        else:
                            fail_count += 1
                except Exception:
                    continue

            if success_count + fail_count == 0:
                return []
            success_rate = success_count / (success_count + fail_count)
            return [{
                "task_pattern": description[:50],
                "success_rate": success_rate,
                "success_count": success_count,
                "fail_count": fail_count,
            }]
        except Exception:
            return []

    def _source(description: str, task_type: str = "analyze"):
        from ocos.learning.metacognition import CapabilityConfidence
        rules = _load_rules(description)
        return CapabilityConfidence.evaluate(
            description, rules, task_type=task_type)

    return _source


def build_master_agent(agent_id: str, db_path: Optional[str] = None):
    """组装真实组件 MasterAgent — 全部生产实现，零 Mock。

    FIX-17: 注入 proactive_output_callback，使主动输出能进入对话流。
    """
    from ocos.agent.capability_manager import CapabilityManager
    from ocos.agent.execution_manager import ExecutionManager
    from ocos.agent.goal_stack import GoalStack
    from ocos.agent.intent import Intent
    from ocos.agent.master_agent import MasterAgent
    from ocos.agent.state import AgentState
    from ocos.capability.attention import CognitiveAttentionController
    from ocos.constitution.behavioral import BehavioralConstitution
    from ocos.runtime.context_manager import WorkingMemory
    from ocos.self.identity_boundary import IdentityBoundary
    from ocos.interaction.inbox import UserInbox

    wm = WorkingMemory()
    engines = build_cognitive_engines(working_memory=wm)

    # FIX-17: 构建主动输出回调 → 写入 UserInbox outbound 通道
    proactive_output_callback = None
    if db_path and db_path != ":memory:":
        try:
            inbox = UserInbox(db_path=db_path)
            def _send(message: str) -> None:
                try:
                    inbox.post_outbound(message)
                    logger.info("Proactive output posted to inbox")
                except Exception as e:
                    logger.warning("Failed to post proactive output: %s", e)
            proactive_output_callback = _send
        except Exception as e:
            logger.warning("UserInbox unavailable for proactive output: %s", e)

    # P4.1 (AGI 计划): 技能习得生产装配 — SkillRegistry（SQLite 持久化）
    # 注入 master_agent；grow_skills_from_episodes 四段生命周期（只读候选
    # 自动提交、写类候选待审批）在 AgentRuntime 目标完成后触发。
    try:
        from ocos.capability.skill_registry import SkillRegistry
        _registry = SkillRegistry(db_path=db_path or "ocos/capability.db")
        _registry.init_db()
        _registry_holder = _registry
    except Exception as e:
        logger.warning("SkillRegistry unavailable: %s", e)
        _registry_holder = None

    return MasterAgent(
        agent_id=agent_id,
        identity=IdentityBoundary.create_default(),
        goal_stack=GoalStack(),
        intent=Intent(),
        attention=CognitiveAttentionController(),
        working_memory=wm,
        capability_manager=CapabilityManager(),
        execution_manager=ExecutionManager(),
        state=AgentState(),
        # FIX-6b: 装配行为宪法 → decide() 前置合规检查真实生效
        constitution=BehavioralConstitution(),
        # FIX-17: 注入主动输出回调 → 消息写入 UserInbox
        proactive_output_callback=proactive_output_callback,
        **engines,
    ), _registry_holder


def build_cognitive_engines(event_bus: Any = None, working_memory: Any = None) -> dict:
    """AUD-F9: 实例化 MasterAgent 五个认知阶段的真实引擎。

    此前 build_master_agent 不注册引擎 → think/decide/reflect/learn 走
    status:"stub" 降级（master_agent 诚实降级路径保留，工厂不再触发它）。
    """
    from ocos.engines.decision_making_engine import DecisionMakingEngine
    from ocos.engines.learning_engine import LearningEngine
    from ocos.engines.planning_engine import PlanningEngine
    from ocos.engines.reasoning_engine import ReasoningEngine
    from ocos.engines.reflection_engine import ReflectionEngine
    from ocos.events.event_bus import EventBus
    from ocos.runtime.context_manager import WorkingMemory

    eb = event_bus or EventBus()
    wm = working_memory or WorkingMemory(event_bus=eb)
    return {
        "reasoning_engine": ReasoningEngine(eb, wm),
        "planning_engine": PlanningEngine(eb, wm),
        "decision_engine": DecisionMakingEngine(eb, wm),
        "reflection_engine": ReflectionEngine(eb, wm),
        "learning_engine": LearningEngine(eb, wm),
    }


def build_health_loop(runtime=None, interval_ticks: int = 100):
    """GAP-P1-2: 装配稳态健康监控 — AlertManager(Log+File) + CognitiveExaminer。

    文件通道落盘 ~/.ocos/alerts/alerts.log（每行一个 JSON）。
    """
    import os
    from pathlib import Path
    from typing import Any, Optional

    from ocos.alerts.channels import FileChannel, LogChannel
    from ocos.alerts.manager import AlertManager
    from ocos.capability.homeostasis import HomeostasisManager
    from ocos.daemon.health_loop import HealthLoop
    from ocos.health_examination.cognitive_examiner import CognitiveExaminer

    alerts = AlertManager()
    alerts.register_channel(LogChannel())
    alerts_dir = Path(os.environ.get("OCOS_ALERTS_DIR", str(Path.home() / ".ocos" / "alerts")))
    alerts.register_channel(FileChannel(str(alerts_dir / "alerts.log")))

    # S3.5 (白皮书 P3): Monitoring 接入生产——Prometheus 指标 + /metrics。
    # HTTP 服务仅在生产装配显式开启（OCOS_MONITORING_ENABLED=true，默认
    # 9090 端口），避免测试/嵌入场景端口冲突；指标记录始终可用。
    monitoring = None
    try:
        from ocos.monitoring.manager import create_monitoring_manager
        from ocos.monitoring.manager import set_global_metrics
        monitoring = create_monitoring_manager()
        # S3.5: 挂接进程级指标 — bridge 等无实例模块经 record_global 埋点
        set_global_metrics(monitoring.metrics)
        if os.environ.get("OCOS_MONITORING_ENABLED", "").strip().lower() == "true":
            monitoring.start_http()
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "MonitoringManager unavailable (metrics disabled): %s", e)
        monitoring = None

    health_loop = HealthLoop(
        runtime=runtime,
        examiner=CognitiveExaminer(),
        alerts=alerts,
        homeostasis=HomeostasisManager(),
        interval_ticks=interval_ticks,
        db_path=os.environ.get("OCOS_DB_PATH",
                               str(Path.home() / ".ocos" / "ocos.db")),
    )
    if monitoring is not None:
        health_loop.monitoring = monitoring  # HealthLoop.tick 记录指标
    return health_loop


def build_perception_pipeline(sensors: Optional[list] = None,
                              file_semantics: bool = False):
    """GAP-P1-3: 组装感知链 — PerceptionEngine + WorldStore + 可选传感器。

    默认零传感器（零噪音）— sensors 由调用方按环境注入
    （如 FileSensor.watch(数据目录)）。
    PW-5.1: file_semantics=True 时为文件观察注入实体/状态解析器
    （entity=文件路径, state=exists/size），观察才会被 WorldValidator 接受。
    """
    from ocos.perception.pipeline import PerceptionPipeline
    from ocos.world_model.world_store import WorldStore

    entity_resolver = None
    state_resolver = None
    if file_semantics:
        def _file_meta(obs) -> dict:
            """文件观察的语义载荷: content（dict）或 metadata。"""
            for src_attr in ("content", "metadata"):
                v = getattr(obs, src_attr, None)
                if isinstance(v, dict) and v.get("operation"):
                    return v
            return {}

        def entity_resolver(obs):
            return _file_meta(obs).get("path") or None

        def state_resolver(obs):
            meta = _file_meta(obs)
            if meta.get("operation") == "created":
                return {"exists": True, "size": meta.get("size", 0)}
            return None

    pipeline = PerceptionPipeline(world=WorldStore(), infer_causality=True,
                                  entity_resolver=entity_resolver,
                                  state_resolver=state_resolver)
    for sensor in sensors or []:
        pipeline.register_sensor(sensor)
    return pipeline


def build_knowledge_registry(semantic_store=None):
    """GAP-P2-1: 组装知识平面 — KnowledgeRegistry + 可选 SemanticStore 镜像。

    semantic_store 缺省为 None（纯内存权威源）；生产装配应注入
    MemoryHub.semantic（同一 db_path 的 knowledge 表），register/update/
    remove 自动落库镜像，update 经 revision 递增就地覆盖。
    """
    from ocos.knowledge.store.registry import KnowledgeRegistry

    return KnowledgeRegistry(semantic_store=semantic_store)


def build_knowledge_abi(semantic_store=None):
    """AUD-F1: 知识平面统一入口 — KnowledgeABI(registry + lifecycle)。

    供引擎（consolidation/promotion 的 knowledge_abi 构造参数）与运行时
    装配使用；semantic_store 经 build_knowledge_registry 启用落库镜像。
    """
    from ocos.knowledge.knowledge_abi import KnowledgeABI
    from ocos.knowledge.store.lifecycle import KnowledgeLifecycle

    registry = build_knowledge_registry(semantic_store=semantic_store)
    return KnowledgeABI(registry=registry, lifecycle=KnowledgeLifecycle(registry))


def build_execution_bridge(agent: Any = None, agent_id: str = "decision_bridge",
                           db_path: str | None = None):
    """R4-A: 组装 DecisionBridge — 自治决策 → 真实任务执行铰链。

    装配: ActionDispatcher + PermissionGuard + ExecutionAudit +
    AdapterDiscovery 扫描的真实 capability_reality 能力 (注册为 handlers)。
    AUD-F12: 传 db_path 时挂载 PendingStore（ASK 待批队列 SQLite 持久化）。
    返回 bridge 实例; 调用方负责 attach 到 AgentRuntime (attach_decision_bridge)。
    """
    from ocos.execution.bridge import DecisionBridge

    pending_store = None
    if db_path:
        from ocos.execution.pending import PendingStore
        pending_store = PendingStore(db_path=db_path)

    bridge = DecisionBridge(agent_id=agent_id, pending_store=pending_store,
                            db_path=db_path)
    try:
        bridge.attach_default_handlers()
    except Exception as e:  # noqa: BLE001 — 能力发现失败不阻断装配
        import logging
        logging.getLogger(__name__).warning(
            "DecisionBridge capability discovery failed: %s", e)
    # FIX-6: 启用 L8 元认知置信度门 — attach_confidence_source 此前无生产调用者
    # （审计 P2）。装配 CapabilityConfidence 评估；无学习规则时返回 "none"
    # （安全不干预），有规则且写类低成功率 → 升级 ASK。失败不阻断装配。
    try:
        source = _make_confidence_source(db_path or "")
        if source is not None:
            bridge.attach_confidence_source(source)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).debug(
            "confidence source attach skipped: %s", e)
    # P1.2 (AGI 计划): 学习产物检索源 — 绑定 AgentRuntime.learning_artifacts，
    # 让决策 prompt 注入历史信念/知识（方法论级经验复用）。agent 未装配或
    # 无该接口时跳过（基线路径，行为不变）。
    try:
        if agent is not None and hasattr(agent, "learning_artifacts"):
            bridge.attach_learning_source(agent.learning_artifacts)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).debug(
            "learning source attach skipped: %s", e)
    # AGI 能力补全: 自动分析本机智能体软件（openclaw/codex/claude/...）→
    # 注入规划上下文（规划 LLM 可见可用清单）+ 动态放行发现 CLI（沙盒
    # extra_allow）→ "调用 XX 智能体"类任务可规划并真实执行。失败不阻断。
    try:
        import json as _json
        import os as _os
        from ocos.capability.agent_discovery import AgentDiscovery

        _cfg: dict = {}
        _cfg_path = _os.path.join(_os.path.expanduser("~"), ".ocos", "config.json")
        if _os.path.exists(_cfg_path):
            try:
                with open(_cfg_path, encoding="utf-8") as _cf:
                    _cfg = _json.load(_cf) or {}
            except Exception:
                _cfg = {}
        _discovery = AgentDiscovery(config=_cfg)

        # 可刷新智能体源: 闭包持有可变清单；安装某智能体成功后重跑发现，
        # 使 "下载安装 → 重发现 → 可调用" 闭环在同一运行时内成立。
        _agents = _discovery.discover()

        def _refresh() -> None:
            nonlocal _agents
            _agents = _discovery.discover()
            _av = [a for a in _agents if a.available]
            bridge.attach_agent_clis(
                {a.cli_path for a in _av if a.kind == "cli" and a.cli_path}
                | {a.name for a in _av if a.kind == "cli"})

        def _agent_list(_desc, _as=_agents):  # noqa: ANN001
            return [{"name": a.name, "available": a.available,
                     "kind": a.kind, "cli_path": a.cli_path,
                     "version": a.version,
                     "api_endpoint": a.api_endpoint,
                     "installable": getattr(a, "installable", False),
                     "install_command": getattr(a, "install_command", "")}
                    for a in _as]

        bridge.attach_agent_source(_agent_list)
        _refresh()
        # AGI 自我增强: 注入安装执行器 — 白名单 AgentInstaller + 重发现。
        # 真实下载/安装只在人工审批(execute_approved)通过后由 bridge 调用。
        try:
            from ocos.capability.agent_installer import AgentInstaller
            _installer = AgentInstaller()

            def _install_fn(name: str) -> dict:
                res = _installer.install(name, approved=True)
                if res.get("ok") or res.get("executed"):
                    _refresh()
                    res["rediscovered"] = True
                return res

            bridge.attach_installer(_install_fn)
        except Exception as _ie:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).debug(
                "agent installer attach skipped: %s", _ie)
        import logging
        logging.getLogger(__name__).info(
            "AgentDiscovery: %d 个智能体软件可用 — %s",
            len([a for a in _agents if a.available]),
            _discovery.report()[:400])
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).debug(
            "agent discovery attach skipped: %s", e)
    if agent is not None:
        attach = getattr(agent, "attach_decision_bridge", None)
        if attach is not None:
            attach(bridge)
        else:  # 裸对象兜底 (仅测试用) — 生产 AgentRuntime 走公开方法
            agent._decision_bridge = bridge
    return bridge
