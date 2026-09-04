"""ocos.daemon.factory — 生产装配层（P1-B import 规则合规）。

将 CLI 入口的组件组装逻辑下沉到 daemon 包，使
ocos.interaction.cli.commands 只依赖 ocos.daemon 门面，
不再直连 agent/capability/runtime 内核组件（宪法 import 规则）。

用法:
    from ocos.daemon.factory import build_master_agent
    agent = build_master_agent(agent_id="ocos")
"""

from __future__ import annotations

from typing import Any, Optional


def _make_confidence_source(db_path: str):
    """FIX-6: L8 元认知置信度 source（DecisionBridge.execute_dag_task 消费）。

    签名: callable(description, task_type) → 含 should_escalate/reason 的对象。
    用 CapabilityConfidence 评估；学习规则 best-effort 加载，失败/为空 → 返回
    "none"（安全不干预，仅当前无历史时保持默认分级）。
    """
    def _load_rules() -> list[dict]:
        try:
            from ocos.engines.learning_engine import LearningEngine
            engine = LearningEngine(db_path=db_path) if db_path else LearningEngine()
            rules: list[dict] = []
            for model in engine.list_models():
                for rule in (getattr(model, "rules", None) or ()):
                    if isinstance(rule, dict):
                        rules.append(rule)
            return rules
        except Exception:
            return []

    def _source(description: str, task_type: str = "analyze"):
        from ocos.learning.metacognition import CapabilityConfidence
        rules = _load_rules()
        return CapabilityConfidence.evaluate(
            description, rules, task_type=task_type)

    return _source


def build_master_agent(agent_id: str):
    """组装真实组件 MasterAgent — 全部生产实现，零 Mock。"""
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

    wm = WorkingMemory()
    engines = build_cognitive_engines(working_memory=wm)

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
        # （此前工厂不装, master_agent.decide 的 constitution 检查永不执行）
        constitution=BehavioralConstitution(),
        **engines,
    )


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

    return HealthLoop(
        runtime=runtime,
        examiner=CognitiveExaminer(),
        alerts=alerts,
        homeostasis=HomeostasisManager(),
        interval_ticks=interval_ticks,
        db_path=os.environ.get("OCOS_DB_PATH",
                               str(Path.home() / ".ocos" / "ocos.db")),
    )


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
    if agent is not None:
        attach = getattr(agent, "attach_decision_bridge", None)
        if attach is not None:
            attach(bridge)
        else:  # 裸对象兜底 (仅测试用) — 生产 AgentRuntime 走公开方法
            agent._decision_bridge = bridge
    return bridge
