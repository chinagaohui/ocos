"""AgentRuntime — OCOS Agent 统一运行时。

集成 MasterAgent + 认知皮层 + 记忆系统 + 信念系统的
完整运行时。通过 Life Cycle 驱动，支持 Homeostasis 优先。

Phase 26: Tick Step 9 (result_ingest) 支持 ResultUnderstandingLayer
  验证→结构化→学习 全管道，自动更新 CapabilityExperienceMemory + KnowledgeGraph。
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
import threading
import time
import uuid
from collections import deque
from enum import Enum, auto
from typing import Any, Optional

from ocos.agent.master_agent import MasterAgent
from ocos.agent.capability_selector import CapabilitySelector
from ocos.agent.meta_controller import MetaController  # 22-D: 使用 ExecutiveController 别名
from ocos.agent.decision_loop import DecisionLoop
from ocos.capability.permission_gateway import PermissionDeniedError
from ocos.agent.cortex_activator import CortexActivator, CortexMode
from ocos.agent.belief_system import BeliefSystem
from ocos.agent.memory_consolidator import MemoryConsolidator
from ocos.agent.knowledge_base import KnowledgeBase
from ocos.agent.experience_store import ExperienceStore
from ocos.agent.engine_bridge import EngineBridge, ENGINE_REGISTRY
from ocos.agent.state import AgentStatus
from ocos.agent.metrics_collector import MetricsCollector
from ocos.agent.health_check import HealthCheck, HEALTHY
from ocos.agent.identity_anchor import IdentityAnchor
from ocos.agent.identity_store import IdentitySQLiteStore
from ocos.agent.goal_store import GoalSQLiteStore
from ocos.memory.hub import MemoryHub
from ocos.storage.working_memory import SQLiteWorkingMemory

# ── P0-2 (2026-09-08 事件复盘): 交付物相关性校验 ─────────────────────────
# 事件: 「制定升级计划」目标 → LLM 被迫输出 RUN|cat ... --version → exit 0
# → ✓ 成功。承诺的正文交付物缺席，命令回显冒充完成。规则: 任务描述要求
# 计划/方案/报告类正文交付物，而执行证据仅为 shell 命令回显（bridge 打标
# capability=shell，无 ANSWER 正文 / FILE_WRITE 落盘）→ 诚实降级为失败。
# 采集/查询类子任务（查/采集/读取等动词）以命令输出为承诺物，豁免。
_DELIVERABLE_GOAL_RE = re.compile(
    r"制定|编制|起草|撰写|编写|规划|设计|计划|方案|蓝图|路线图")
_DATA_COLLECT_RE = re.compile(
    r"查询|采集|获取|读取|查看|检查|列出|扫描|探测|执行|运行|汇总|统计|监控")

# 开发/构建类交付物（2026-09-08「开发虚拟人应用」假成功事件）：交付物 =
# 落盘工件（项目结构/代码/依赖），纯只读探查（ls/--version/cat）在物理上
# 不可能完成 → 命令行无写证据时诚实降级。不与采集豁免共用（开发类描述
# 里常带"检查/运行"字样，如"确保可运行"，豁免会让条款形同虚设）。
_BUILD_GOAL_RE = re.compile(
    r"(?<!者)(开发|实现|创建|构建|搭建|制作|安装|部署)")
# P0-2f 校准（2026-09-08「宿主机硬件画像」事件）: "部署可行性/部署方案评估"
# 属探查评估意图，不是构建动作——描述命中评估词时 build 闸门不适用，
# 否则纯只读画像任务（uname/df/free/nvidia-smi）被误降级【交付物缺失】
_BUILD_ASSESS_RE = re.compile(
    r"可行性|评估|分析|画像|调研|对比|选型")
# 写证据检测对象 = stdout 中 "$ " 前缀的命令标签行（UX-J+ 实际执行命令）。
# 高精度写指示符 — 命中任一即视为存在工件产出的可能：
#   - 重定向/经典写命令（>, tee, mkdir, ...）
#   - 包安装/构建（"install" 子串覆盖 npm/pip/apt install）
#   - 脚本执行 node/python — 排除 --version/--help 探查（本事件教训：
#     裸 "npm " 会把 npm --version 误判为写证据 → 假成功放行）
_WRITE_EVIDENCE_RE = re.compile(
    r">>|>|tee |mkdir|touch |mv |cp |rm |chmod|chown|sed -i"
    r"|ln -s|dd |git init|clone|unzip|tar |make|cmake"
    r"|install|npx |cargo |mvn |gradle|gcc|g\+\+|javac"
    r"|node (?!--)|python\d? (?!--)"          # 空格内置防回溯绕过 lookahead
    r"|npm (?:i |install|ci |run |exec |init|test)")
# 检测前剥离的伪写指示（丢弃输出类重定向不产生工件）
_WRITE_NOISE_RE = re.compile(r"2>&1|&>?/dev/null|\d?>\s*/dev/null")

# P0-2c (2026-09-08「GitHub 数字生命调研」事件): 总结器自认不完整降级。
# 事件: 用户授权"去 GitHub 学习数字生命并总结+升级方案"，规划器只规划了
# 描述括号里枚举的本地命令（uname/df/free），零联网动作；总结器诚实自述
# "任务未完整达成…缺少 GitHub 数字生命项目调研结果"，但描述含"检查/执行"
# 命中 _DATA_COLLECT_RE 被采集豁免放行 → ✓ 假成功落库。
# 规则: 【结论摘要】由固定 prompt（"判断是否达成任务"）生成的机器文本，
# 其显式自认不完整是最直接的诚实信号 — 只检查摘要段（【原始输出】之前），
# 避免原始命令输出中的引用误伤。与描述类正则（易被混合型目标绕过）互补。
_SELF_INCOMPLETE_RE = re.compile(
    r"未完整达成|未完整|部分达成|部分完成|未达成|任务未完成"
    r"|缺少[^。\n]{0,24}(调研|项目|方案|结果|数据|内容|清单|交付)"
    r"|未提供[^。\n]{0,24}(调研|项目|方案|清单|内容|数据)"
    r"|需补充|缺失[^。\n]{0,16}(调研|项目|方案|清单|内容)")


def _has_write_evidence(stdout: str) -> bool:
    """从执行输出提取 "$ " 命令标签行，检测是否存在写指示符。"""
    for line in str(stdout or "").splitlines():
        if not line.startswith("$ "):
            continue
        cmd = _WRITE_NOISE_RE.sub("", line[2:].lower())
        if _WRITE_EVIDENCE_RE.search(cmd):
            return True
    return False

logger = logging.getLogger(__name__)


# ── P1: chat 目标智能路由（agent_type / task_type） ──────────────

_INTERNET_KEYWORDS = re.compile(
    r"(调研|学习|搜索|查|查找|搜|联网|全网|国际|最新|GitHub|github|Google|google"
    r"|知乎|百度|必应|Bing|bing|研究|论文|paper|技术博客|tech|news|新闻"
    r"|访问\s+https?://|http://|https://|www\.|\bURL\b|\burl\b)",
    re.IGNORECASE,
)

_WRITE_KEYWORDS = re.compile(
    r"(写|创建|新建|生成|修改|编辑|修复|实现|添加|重构|部署|安装|配置"
    r"|写文件|落盘|保存|保存为|mkdir|touch|git\s+commit|git\s+push"
    r"|pip\s+install|npm\s+install|docker|systemctl\s+start)",
    re.IGNORECASE,
)

_ANALYZE_KEYWORDS = re.compile(
    r"(分析|评估|诊断|检查|验证|测试|benchmark|性能|对比|测量|探查"
    r"|梳理|总结|统计|监控|metrics|日志|log)",
    re.IGNORECASE,
)


def _infer_agent_type(description: str, domain: Any = None) -> str:
    """P1: 根据目标描述推断最合适的 agent_type。

    路由逻辑（优先级从上到下，首个匹配）：
      1. 含联网关键词（调研/搜索/URL）→ researcher
         （LLM bridge 会选 shell+curl/wget 或直接用 LLM 知识）
      2. 含写关键词（写/创建/修复/重构）→ code_executor
      3. 含分析关键词（分析/评估/诊断）→ researcher
      4. domain=writing → writer
      5. 默认 → researcher（最通用，只读）

    注: agent_type 主要影响 echo fallback 和元数据，真实执行由
        DecisionBridge.execute_dag_task → LLM 驱动。
    """
    if not description:
        return "researcher"
    d = description[:200]
    if _INTERNET_KEYWORDS.search(d):
        logger.debug("chat task routing: internet keyword → researcher")
        return "researcher"
    if _WRITE_KEYWORDS.search(d):
        logger.debug("chat task routing: write keyword → code_executor")
        return "code_executor"
    if _ANALYZE_KEYWORDS.search(d):
        logger.debug("chat task routing: analyze keyword → researcher")
        return "researcher"
    # domain fallback
    if domain is not None:
        dn = str(domain).lower()
        if "writing" in dn:
            return "writer"
    return "researcher"


def _infer_task_type(description: str, domain: Any = None) -> str:
    """P1: 根据描述推断 task_type（create|modify|analyze|execute|verify）。"""
    if not description:
        return "execute"
    d = description[:200]
    if _ANALYZE_KEYWORDS.search(d):
        return "analyze"
    if _WRITE_KEYWORDS.search(d):
        if re.search(r"(新建|创建|写|生成|实现)", d):
            return "create"
        return "modify"
    return "execute"


def _truncate_text(text: Any, max_chars: int) -> str:
    """UX-J+: 按行边界截断执行输出。

    此前硬切字符数会把行切成半行（实测 `uname -a && nproc` 的输出在
    `#28~24.0` 中间被切断、nproc 的 `12` 整行丢失），LLM 基于残行重组
    【原始输出】时张冠李戴，得出"nproc 返回 os-release 内容"这类失真
    结论并沉淀进记忆。现回退到最近行边界，尾附截断标记。
    """
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    nl = cut.rfind("\n")
    if nl > 0:
        cut = cut[:nl]
    return f"{cut}\n…（已截断，原文 {len(text)} 字符）"


class RuntimeState(Enum):
    """运行时状态。"""
    STOPPED = auto()
    BOOTING = auto()
    RUNNING = auto()
    SLEEPING = auto()
    ERROR = auto()
    SHUTDOWN = auto()


class AgentRuntime:
    """Agent 统一运行时。

    整合信号：
    - Life Cycle: BOOT → WAKE → OBSERVE → THINK → DECIDE → ACT → REFLECT → LEARN → SLEEP → DREAM
    - Homeostasis: 优先级高于 Goal（疲劳/阻塞时自动调整）
    - Memory: 每轮 cycle 自动巩固
    - Belief: 从经验中提炼信念
    """

    def __init__(
        self,
        agent: MasterAgent,
        engine_list: Optional[list[str]] = None,
        engine_bridge: Optional[EngineBridge] = None,
        working_capacity: int = 10,
        max_cycles: int = 100,
        consolidation_threshold: float = 0.5,
        belief_threshold: float = 0.6,
        homeostatic_check_interval: int = 3,
        *,
        db_path: str = ":memory:",
        # Phase 21: Optional persistence + dynamic engine loading
        engine_loader: Any = None,
    ):
        self.agent = agent
        self.selector = CapabilitySelector(engine_list or [])
        self.controller = MetaController(max_cycles=max_cycles)
        self.cortex = CortexActivator()
        self.memory = MemoryConsolidator(
            working_capacity=working_capacity,
            consolidation_threshold=consolidation_threshold,
        )
        self.beliefs = BeliefSystem(default_threshold=belief_threshold)
        self.knowledge = KnowledgeBase()
        self.experiences = ExperienceStore()
        self.engine_bridge = engine_bridge or EngineBridge()
        self.loop = DecisionLoop(agent, self.selector, self.controller, self.engine_bridge)

        self._db_path = db_path
        self._identity_store: Any = None
        self._goal_store: Any = None
        self._memory_hub: Any = None
        self._wm_store: Any = None
        self._engine_loader = engine_loader
        # UX-J 即时推送: goal_result episode 落库后的回调（daemon 注册
        # _push_goal_results，实现"完成即推"，避免等 5-tick 节拍）
        self._on_goal_result: Any = None

        self._state = RuntimeState.STOPPED
        self._homeostatic_check_interval = homeostatic_check_interval
        self._cycle_count = 0
        self._lock = threading.RLock()
        self.metrics = MetricsCollector()
        self.health = HealthCheck()

        # Phase 34A: EventBus — 感知神经中枢
        self._event_bus: Any = None  # EventBus, initialized in boot()
        # P1-2: 预算可配 — LLM 任务（每任务 3-12s）远超 500ms，
        # 固定 0.5s 会让告警永远在响（审计 P1-2）
        self._tick_budget: float = float(os.environ.get("OCOS_TICK_BUDGET", "0.5"))
        # Phase 24-A: PermissionGateway 集成 — 所有外部交互必经网关
        self._gateway: Any = None
        # Phase 26: ResultUnderstandingLayer — 验证→结构化→学习管道
        self._result_understanding_layer: Any = None
        # Phase 31: Execution Loop — TaskDAG → Orchestrator → Agent → Results
        self._active_dag: Any = None
        self._dag_cursor: int = 0
        self._dag_total: int = 0
        self._dag_tick_count: int = 0   # P2: DAG 存活 tick 计数 → 超时杀
        self._DAG_TICK_TIMEOUT: int = 200  # P2: 单 DAG 最多存活 200 tick ≈ 16min
        self._task_statuses: dict[str, str] = {}  # task_id → status
        self._recent_results: list[dict[str, Any]] = []
        self._result_mark: int = 0   # UX-F2+: 当前 DAG 起始下标（结果汇总按目标切片）
        self._result_cursor: int = 0  # Phase 32: cursor for step 9 ingestion
        # Phase 49-C (L4): 任务重试计数 — 失败→重规划 (最多 MAX_RETRY_PER_TASK 次)
        self._task_retry_count: dict[str, int] = {}
        self._orchestrator: Any = None
        # R4-A: DecisionBridge (自治决策 → 真实执行铰链), 由 factory 装配
        self._decision_bridge: Any = None
        self._last_core_loop_result: dict = {}
        # Phase 32: Attention wiring
        self._attention: Any = None
        # Phase 35: Attention decisions cache (step 2 → step 3)
        self._last_attention_decisions: list[Any] = []
        self._attention_report: Any = None     # Phase 36: cached for step 4/5/6
        self._last_ingestion_events: list[dict[str, Any]] = []
        # Phase 34D: Stability metrics
        self._tick_latencies: deque[float] = deque(maxlen=1000)
        self._tick_errors: int = 0
        self._boot_time: Optional[float] = None
        # UX-J+: 预算告警去重 — LLM 任务单 tick 17-29s 恒超 15s 预算，
        # 连续执行时每个 tick 都告警无信息量（实测 4 目标连刷 20+ 条）
        self._budget_warn_streak: int = 0

        # Phase G: User Model — 用户画像与记忆中枢
        self._user_memory: Any = None  # UserMemory, initialized in boot()

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def gateway(self) -> Any:
        """Phase 24-A: 延迟初始化 PermissionGateway。"""
        if self._gateway is None:
            from ocos.capability.permission_gateway import PermissionGateway
            self._gateway = PermissionGateway()
        return self._gateway

    def inject_user_message(self, text: str, sender: str = "cli") -> dict:
        """UX-P2: 用户消息 → 感知事件（下一 tick 被 Step 1 摄入）。

        daemon 从收件箱 drain 后调用；消息进入注意力管道（HIGH 严重性），
        认知循环的决策输出经 DecisionBridge 执行并可经 trace 观察。
        """
        try:
            ce = self.event_bus.push_user_message(text, sender=sender)
            logger.info("User message injected: %s (sender=%s)", ce.event_id, sender)
            return {"event_id": ce.event_id, "accepted": True}
        except Exception as e:
            logger.exception("inject_user_message failed")
            return {"accepted": False, "error": str(e)}

    @property
    def event_bus(self) -> Any:
        """Phase 34A: 延迟初始化 EventBus（感知神经中枢）。"""
        if self._event_bus is None:
            from ocos.perception_bus import EventBus
            self._event_bus = EventBus()
        return self._event_bus

    @property
    def _get_result_understanding_layer(self) -> Any:
        """Phase 26: 延迟初始化 ResultUnderstandingLayer。

        DEPRECATED（收敛裁决 R1，2026-09-08）：本层零生产调用，反思语义由
        分布式现役链承载（_record_failure_lesson + _replan_failed_task +
        dream 巩固）。裁决=ARCHIVE 不接线，见
        docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md。
        """
        if self._result_understanding_layer is None:
            from ocos.capability.result_understanding import ResultUnderstandingLayer
            self._result_understanding_layer = ResultUnderstandingLayer()
        return self._result_understanding_layer

    @property
    def orchestrator(self) -> Any:
        """Phase 31: 延迟初始化 CapabilityOrchestrator + echo_agent。"""
        if self._orchestrator is None:
            from ocos.capability.orchestrator import CapabilityOrchestrator
            from ocos.capability.echo_agent import EchoAgent
            from ocos.capability.agents import ResearchAgent, CodeAgent, SummarizerAgent, PlannerAgent
            self._orchestrator = CapabilityOrchestrator(
                providers={
                    "writer": EchoAgent(prefix="Writer"),
                    "researcher": ResearchAgent(prefix="Researcher"),
                    "reviewer": EchoAgent(prefix="Reviewer"),
                    "data_processor": EchoAgent(prefix="DataProcessor"),
                    "code_executor": CodeAgent(prefix="CodeExecutor"),
                    "summarizer": SummarizerAgent(prefix="Summarizer"),
                    "planner": PlannerAgent(prefix="Planner"),
                    "echo": EchoAgent(),
                },
                auto_learn=False,  # Phase 32 再开学习
            )
        return self._orchestrator

    @property
    def attention(self) -> Any:
        """Phase 35: CognitiveAttentionController — 唯一持有 Attention 决策权的组件。"""
        if self._attention is None:
            from ocos.capability.attention import CognitiveAttentionController
            self._attention = CognitiveAttentionController()
        return self._attention

    def boot(self) -> None:
        """启动运行时。Identity > Memory 顺序。"""
        with self._lock:
            if self._state == RuntimeState.RUNNING:
                logger.debug("Already running, skipping boot.")
                return
            if self._state == RuntimeState.SHUTDOWN:
                logger.warning("Cannot boot from SHUTDOWN state.")
                return

            logger.info("AgentRuntime booting...")
            self._state = RuntimeState.BOOTING

            # 0. Phase 21: 初始化持久化层
            self._init_persistence()

            # 0.5 Phase 34B: 恢复 Cognitive State（当前焦点/未完成任务/上次注意力）
            self._restore_working_memory()

            # 0.6 Phase 34E: 验证 Identity Continuity
            self._verify_identity_continuity()

            # Phase G: 初始化 User Model
            self._init_user_model()

            # Phase H: 初始化 Memory Recall
            self._init_memory_recall()

            # Phase I: 初始化 True Initiative
            self._init_true_initiative()

            # Phase L: 初始化 Goal Manager
            self._init_goal_manager()

            # 先于 agent.boot(): Phase 22-A 注入 EngineBridge 供 act() 真实化
            if hasattr(self.agent, "set_engine_bridge"):
                self.agent.set_engine_bridge(self.engine_bridge)

            # 1. 启动 Agent（遵守 Identity > Memory 顺序）
            self.agent.boot()

            # 2. 激活皮层
            self.cortex.activate()

            # 3. 注册健康检查
            self.health.register("event_bus", lambda: {"status": HEALTHY})
            self.health.register(
                "engine_bridge",
                lambda: {
                    "status": HEALTHY,
                    "engines": list(ENGINE_REGISTRY.keys()),
                },
            )

            # 4. 完成启动
            self._state = RuntimeState.RUNNING
            self._boot_time = time.time()
            logger.info("AgentRuntime running.")

    def _init_persistence(self) -> None:
        """Phase 21: 初始化持久化层 — Identity + Memory。

        Identity 优先级最高：先恢复/创建 Identity，再初始化 Memory。
        """
        from pathlib import Path

        db_path = self._db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Identity Store
        self._identity_store = IdentitySQLiteStore(db_path)
        self._identity_store.initialize()

        agent_id = self.agent.agent_id
        # Defense: 代理 agent_id 为 MagicMock 等非字符串时跳过
        if not isinstance(agent_id, str) or not agent_id.strip():
            logger.warning(
                "agent_id is not a valid string (%s), skipping persistence init.",
                type(agent_id).__name__,
            )
            return

        identity = self._identity_store.load(agent_id)

        if identity is None:
            # 首次启动 — 创建新 Identity
            agent_name = "OCOS Agent"
            if hasattr(self.agent, "identity") and hasattr(self.agent.identity, "get_name"):
                agent_name = self.agent.identity.get_name()
            identity = IdentityAnchor(
                agent_id=agent_id,
                name=agent_name,
            )
            self._identity_store.save(identity)
            logger.info("New identity created: %s", identity)
        else:
            logger.info("Identity restored from %s: %s", db_path, identity)

        # 注入恢复的 Identity（替换 MasterAgent 的临时 identity）
        self.agent.identity = identity

        # Goal Store
        self._goal_store = GoalSQLiteStore(db_path)
        self._goal_store.initialize()

        # 恢复 ACTIVE/PENDING Goal → 注入 GoalStack
        if hasattr(self.agent, "goal_stack") and hasattr(self.agent.goal_stack, "set_store"):
            self.agent.goal_stack.set_store(self._goal_store)
            restored_count = self.agent.goal_stack.restore_from_store()
            if restored_count > 0:
                logger.info("Goals restored: %d", restored_count)

        # Memory Hub
        self._memory_hub = MemoryHub(db_path)
        self._memory_hub.initialize()
        logger.info("MemoryHub initialized — %s", self._memory_hub.get_stats())

        # P1-A: BeliefSystem 持久化写路径接通（L6 门控 → hub.belief.save）
        self.beliefs.bind_hub(self._memory_hub)

        # GAP-P0-2: 统一 MemoryHub 为唯一 store 来源 → 回填 Agent 的 dream 巩固 store
        # （生产路径此前 MasterAgent 惰性建 :memory: store，信念/模式进程退出即丢）
        if hasattr(self.agent, "attach_memory_hub"):
            self.agent.attach_memory_hub(self._memory_hub)

        # Working Memory Store (Phase 21)
        if db_path != ":memory:":
            self._wm_store = SQLiteWorkingMemory(
                db_path, max_entries=1000, default_ttl=None,
            )
            logger.info("WorkingMemory store initialized at %s", db_path)

        # Dynamic Engine Loading (Phase 21)
        if self._engine_loader is not None:
            loaded = self._engine_loader.load_all()
            for engine_id, engine_instance in loaded.items():
                try:
                    engine_cls = type(engine_instance)
                    self.engine_bridge.register_engine_type(engine_id, engine_cls)
                except Exception as e:
                    logger.debug("EngineLoader: skip %s — %s", engine_id, e)
            self.engine_bridge.register_all()
            logger.info("Dynamic engines loaded: %s", self.engine_bridge.get_available_engines())

    def _init_user_model(self) -> None:
        """Phase G: 初始化 User Model — 用户画像与记忆中枢."""
        from ocos.memory.user import UserMemory
        db_path = self._db_path
        if db_path == ":memory:":
            db_path = "/tmp/ocos_user_model.db"
        self._user_memory = UserMemory(db_path)
        logger.info("UserModel initialized at %s", db_path)

    def _init_memory_recall(self) -> None:
        """Phase H: 初始化 MemoryRecall — 跨会话记忆检索."""
        from ocos.memory.recall import MemoryRecall

        self._memory_recall = MemoryRecall(memory_hub=self._memory_hub)
        # FIX-3: 回填到 MasterAgent → 认知轮 think() 的 recall_context() 可用
        # （此前只挂在本 runtime, agent._memory_recall 恒 None 断链）
        if hasattr(self.agent, "attach_memory_recall"):
            self.agent.attach_memory_recall(self._memory_recall)
        logger.info("MemoryRecall initialized. Ready for cross-session retrieval.")

    def _init_true_initiative(self) -> None:
        """Phase I: 初始化 TrueInitiative — 真正主动性引擎."""
        from ocos.initiative import TrueInitiative

        # 注入到 MasterAgent（注: 运行时的 agent 属性是 self.agent，
        # 历史用 _agent 导致永远取不到 → 注入一直没生效）
        agent_obj = self.agent
        if agent_obj is not None:
            agent_obj._true_initiative = TrueInitiative(
                user_memory=self._user_memory,
                memory_recall=self._memory_recall,
            )
            logger.info("TrueInitiative initialized. Proactive output ready.")
        else:
            logger.debug("MasterAgent not available, TrueInitiative skipped.")

    def _init_goal_manager(self) -> None:
        """Phase L: 初始化 GoalManager — 自主目标管理系统."""
        from ocos.autonomous import create_goal_manager

        goal_mgr = create_goal_manager()
        # 注入到 MasterAgent（注: 运行时的 agent 属性是 self.agent，
        # 历史用 _agent 导致永远取不到 → 注入一直没生效）
        agent_obj = self.agent
        if agent_obj is not None:
            agent_obj._goal_manager = goal_mgr
            logger.info("GoalManager initialized. Endogenous goal support ready.")
        else:
            logger.debug("MasterAgent not available, GoalManager skipped.")

    @property
    def user_memory(self) -> Any:
        """Phase G: 用户记忆中枢访问器."""
        return self._user_memory

    def _record_step_result(self, step_log: list, result: Any) -> None:
        """S3.9 (白皮书 P2): step 结果统一记账——含 error 字段时
        _tick_errors 自增（原无自增点，稳定性报告 error_rate 恒 0、
        high_error_rate 漂移旗标死逻辑）。
        """
        step_log.append(result)
        if isinstance(result, dict) and result.get("error"):
            self._tick_errors += 1

    def tick(self) -> dict[str, Any]:
        """Phase 22-C: 10 步持久化认知 Tick 循环。

        Steps:
          1. Event Ingestion — 从 EventBus 拉取事件
          2. Attention Update — 注意力模型更新
          3. WM Sync — 工作记忆持久化
          4. Goal Maintenance — 目标状态检查
          5. Execution Check — 执行状态扫描
          6. Planning Trigger — 触发计划
          7. Core Loop — observe→think→decide→act→reflect→learn
          8. Dispatch — 经 Bridge+Gateway 派发
          9. Result Ingest — 结果反刍
          10. Learning Consolidation — 经验巩固
        """
        if self._state != RuntimeState.RUNNING:
            return {"status": "not_running", "state": self._state.name}

        with self._lock:
            self._cycle_count += 1
            tick_start = time.monotonic()
            step_log: list[dict[str, Any]] = []

            # ── Step 1: Event Ingestion ──────────────────────────────
            self._record_step_result(step_log, self._tick_step_event_ingestion())

            # ── Step 2: Attention Update ─────────────────────────────
            self._record_step_result(step_log, self._tick_step_attention_update())

            # ── Step 3: WM Sync ──────────────────────────────────────
            self._record_step_result(step_log, self._tick_step_wm_sync())

            # ── Step 4: Goal Maintenance ─────────────────────────────
            self._record_step_result(step_log, self._tick_step_goal_maintenance())

            # ── Step 4.5: Homeostasis Regulation（P2-A 内生目标）────────
            self._record_step_result(step_log, self._tick_step_homeostasis_regulation())

            # ── Step 5: Execution Check ──────────────────────────────
            self._record_step_result(step_log, self._tick_step_execution_check())

            # ── Step 6: Planning Trigger ─────────────────────────────
            self._record_step_result(step_log, self._tick_step_planning_trigger())

            # ── Step 7: Core Loop (observe→think→decide→act→reflect→learn) ──
            self._record_step_result(step_log, self._tick_step_core_loop())

            # ── Step 8: Dispatch (Bridge + Gateway) ───────────────────
            self._record_step_result(step_log, self._tick_step_dispatch())

            # ── Step 9: Result Ingest ────────────────────────────────
            self._record_step_result(step_log, self._tick_step_result_ingest())

            # ── Step 10: Learning Consolidation ──────────────────────
            self._record_step_result(step_log, self._tick_step_learning_consolidation())

            # ── Budget & Graceful Degradation ────────────────────────
            tick_elapsed = time.monotonic() - tick_start
            self._tick_latencies.append(tick_elapsed)
            budget_ok = tick_elapsed < self._tick_budget
            if not budget_ok:
                self._budget_warn_streak += 1
                # 连续超预算只报首告警 + 每 10 tick 一次节奏采样；
                # 回到预算内即清零（下轮超预算重新首报）
                if (self._budget_warn_streak == 1
                        or self._budget_warn_streak % 10 == 0):
                    logger.warning(
                        "Tick budget exceeded: %.2fs > %.2fs (cycle=%d, "
                        "streak=%d)",
                        tick_elapsed, self._tick_budget, self._cycle_count,
                        self._budget_warn_streak,
                    )
            else:
                self._budget_warn_streak = 0

            result = {
                "status": "completed",
                "cycle": self._cycle_count,
                "cortex_mode": self.cortex.mode.name,
                "tick_elapsed_s": round(tick_elapsed, 4),
                "budget_ok": budget_ok,
                "steps": step_log,
                "memory": self.memory.get_stats(),
            }
            return result

    # ── 10 Steps ─────────────────────────────────────────────────────────────

    def _tick_step_event_ingestion(self) -> dict[str, Any]:
        """Step 1: Event Ingestion — EventBus → Normalizer → Attention Evaluation.

        Phase 34A + Phase 35: 完整感知链路。
          1. EventBus.ingest() 拉取待处理事件
          2. 存储事件供 step 2 (Attention) 使用
          3. 记录 EVENT_INGESTION_TRACE
        Phase 35: 决策逻辑移到 step 2 (Attention Update)，step 1 只负责采集。
        """
        traces: list[dict[str, Any]] = []
        events_for_attention: list[dict[str, Any]] = []
        try:
            eb = self.event_bus
            events = eb.ingest(max_events=10)
            if not events:
                self._last_ingestion_events = []
                return {"step": 1, "name": "event_ingestion", "status": "no_events", "traces": []}

            for event in events:
                # 获取当前活跃目标列表
                active_goals: list[str] = []
                try:
                    if self._goal_store is not None:
                        active_goals = [g.goal_id for g in self._goal_store.load_active()]
                except Exception as _gs_e:
                    # BR-04 B批（2026-08-25）：goal_store 读取失败留痕——
                    # 否则 active_goals=[] 静默缺失，注意力/检索缺目标上下文无感知。
                    logger.warning("goal_store.load_active failed (event loop): %s", _gs_e)

                candidate_score = event.candidate_score
                source_type = getattr(event, 'source_type', 'file_change')

                # Phase 35: 存储原始事件数据供 step 2 使用
                event_data = {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "summary": event.summary,
                    "candidate_score": candidate_score,
                    "source_type": source_type,
                    "active_goals": active_goals,
                }
                events_for_attention.append(event_data)

                # 记录简化的 trace（详细 trace 在 step 2 生成）
                traces.append({
                    "event_id": event.event_id,
                    "type": event.event_type,
                    "summary": event.summary,
                    "score": candidate_score,
                })

            # Phase 35: 存储事件供 step 2 使用
            self._last_ingestion_events = events_for_attention

            return {
                "step": 1, "name": "event_ingestion",
                "events": len(events),
                "traces": traces,
            }
        except Exception as e:
            logger.debug("Event ingestion skipped: %s", e)
            self._last_ingestion_events = []
            return {"step": 1, "name": "event_ingestion", "status": "no_ingestion", "error": str(e)}

    def _tick_step_attention_update(self) -> dict[str, Any]:
        """Step 2: Attention Update — Phase 35 核心认知控制管道。

        Freeze §7.1 完整路径:
          EventBus 事件(step 1) → B:AttentionScoringEngine.score() → C:CognitiveAttentionController.decide()
          → AttentionDecision[] → WM Allocation 路由(step 3)

        单写入点原则: 所有 current_focus 变更只来自此步骤的 CognitiveAttentionController。
        """
        try:
            controller = self.attention  # CognitiveAttentionController (C 层)
            events = self._last_ingestion_events

            if not events:
                # 无事件：推进疲劳 + 尝试恢复挂起焦点
                controller.tick(seconds=0.1)
                # Phase 36: 无事件也生成报告
                self._attention_report = controller.emit_report(tick_id=f"tick-{time.time()}")
                return {
                    "step": 2, "name": "attention_update",
                    "status": "no_events",
                    "focus_state": controller.focus_state.value,
                    "fatigue": round(controller.fatigue, 3),
                }

            # 获取活跃目标
            active_goals: list[str] = []
            try:
                if self._goal_store is not None:
                    active_goals = [g.goal_id for g in self._goal_store.load_active()]
            except Exception as _gs_e:
                # BR-04 B批（2026-08-25）：goal_store 读取失败留痕。
                logger.warning("goal_store.load_active failed (decision): %s", _gs_e)

            # Phase 35: 核心决策管道
            # events → score (B层内嵌) → decide (C层) → AttentionDecision[]
            import time as _time
            _start = _time.monotonic()
            decisions = controller.decide(events, active_goals=active_goals)
            _elapsed = _time.monotonic() - _start

            # 推进疲劳
            controller.tick(seconds=0.1)

            # 存储 decisions 供 step 3 (WM Sync) 使用
            self._last_attention_decisions = decisions

            # Phase 36: 生成 AttentionReport 供 step 4/5/6 读取
            self._attention_report = controller.emit_report(
                tick_id=f"tick-{_time.time()}",
                last_decisions_raw=decisions,
            )

            # 生成 step 2 摘要报告
            accepted_count = sum(1 for d in decisions if d.is_accepted)
            queued_count = sum(1 for d in decisions if d.decision.name == "QUEUED")
            deferred_count = sum(1 for d in decisions if d.decision.name == "DEFERRED")
            dismissed_count = sum(1 for d in decisions if d.is_dismissed)

            return {
                "step": 2,
                "name": "attention_update",
                "phase": 35,
                "pipeline": "events→score→decide→AttentionDecision",
                "events": len(events),
                "decisions": {
                    "total": len(decisions),
                    "ACCEPTED": accepted_count,
                    "QUEUED": queued_count,
                    "DEFERRED": deferred_count,
                    "DISMISSED": dismissed_count,
                },
                "focus": controller.current_focus,
                "focus_state": controller.focus_state.value,
                "fatigue": round(controller.fatigue, 3),
                "scoring_time_ms": round(_elapsed * 1000, 2),
                "interrupts_this_minute": len(controller._recent_interrupts),
            }
        except Exception as e:
            logger.error("Attention update failed: %s", e, exc_info=True)
            return {"step": 2, "name": "attention_update", "error": str(e)}

    def _tick_step_wm_sync(self) -> dict[str, Any]:
        """Step 3: WM Sync — 工作记忆持久化 + Phase 35 注意力分配指令执行。

        Phase 35: 执行 step 2 产生的 AttentionDecision 中的 wm_allocation 指令。
        路由规则（Freeze §5）:
          current_focus → WM slot_type=CURRENT_FOCUS
          environmental_scan → WM slot_type=ENVIRONMENTAL_SCAN (weight × 0.3)
          DISMISSED → 不写入 WM
        """
        result = {"step": 3, "name": "wm_sync"}
        wm_writes = 0

        # Phase 35: 执行 Attention WM 分配指令
        decisions = self._last_attention_decisions
        if decisions:
            for d in decisions:
                if d.wm_allocation is None:
                    continue
                if d.decision.value == "DISMISSED":
                    continue  # Freeze §5 规则3: DISMISSED 不写入 WM

                slot = d.wm_allocation.slot_type
                weight = d.wm_allocation.attention_weight
                event_id = d.wm_allocation.event_id

                # 写入 WorkingMemory Store
                if hasattr(self, "_wm_store") and self._wm_store is not None:
                    try:
                        self._wm_store.put(
                            key=f"attention:{slot}:{event_id}",
                            value={
                                "event_id": event_id,
                                "slot": slot,
                                "attention_weight": weight,
                                "decision": d.decision.value,
                            },
                            ttl=3600 if slot == "environmental_scan" else None,
                        )
                        wm_writes += 1
                    except Exception as _wm_e:
                        # BR-04 B批（2026-08-25）：工作记忆写入失败留痕，
                        # 否则缓存缺失无感知。
                        logger.warning("wm_store.put failed (attention): %s", _wm_e)

            # 清空 decisions cache
            self._last_attention_decisions = []

        # 周期性完整持久化
        if self._cycle_count % 5 == 0:
            self._persist_working_memory()
            result["persisted"] = True
        else:
            result["skipped"] = "not_sync_cycle"

        result["wm_writes_from_attention"] = wm_writes
        return result

    def _tick_step_homeostasis_regulation(self) -> dict[str, Any]:
        """Step 4.5: Homeostasis Regulation — 稳态偏差 → 内生目标（P2-A）。

        HomeostasisManager.regulate() 推导驱力并生成 SELF 级内生目标，
        经 GoalOriginEnforcer(Phase 25) 门控后写入 _goal_store，
        本 tick 的 Step 6 Planning Trigger 即可消费。
        失败降级：异常时返回 gated 状态，不中断 tick。
        """
        try:
            if self._goal_store is None:
                return {"step": "4.5", "name": "homeostasis_regulation",
                        "status": "no_goal_store"}

            from ocos.capability.homeostasis import HomeostasisManager
            from ocos.goal.enforcer import GoalOriginEnforcer

            hm = HomeostasisManager()
            enforcer = GoalOriginEnforcer(current_phase=25)

            # P2-B (2026-08-29): 好奇心注入 — Step 2 的 AttentionDecision[].score_trace.novelty
            # 最大值作为本 tick 新信息增量；fatigue 来自 CognitiveAttentionController。
            # 确定性来源：AttentionScoringEngine 输出（防伪造）；提取失败 → 0.0 降级不中断。
            novelty: float | None = None
            fatigue: float | None = None
            try:
                decisions = self._last_attention_decisions or []
                if decisions:
                    novelty = max(
                        d.score_trace.novelty for d in decisions
                        if d.score_trace is not None
                    )
                fatigue = getattr(self.attention, "fatigue", None)
            except Exception as _p2b_e:
                logger.debug("P2-B novelty extraction failed: %s", _p2b_e)

            result = hm.regulate(
                enforcer=enforcer,
                novelty=novelty,
                attention_fatigue=fatigue,
            )

            created = 0
            for goal in result.goals:
                # UX-F4: SELF 目标去重 + 每日限额 — 防止"探索新领域"
                # 同类目标无限堆积，挤占人工目标的分解名额
                try:
                    existing = self._goal_store.load_active()
                    if any(getattr(g, "description", "") == goal.description
                           for g in existing):
                        continue
                    today = datetime.now(timezone.utc).date().isoformat()
                    conn = self._goal_store.connection
                    n_today = conn.execute(
                        "SELECT COUNT(*) FROM goal WHERE origin_level='SELF' "
                        "AND created_at LIKE ?",
                        (f"{today}%",)).fetchone()[0]
                    if n_today >= 3:
                        continue
                except Exception as _dq_e:
                    logger.debug("SELF goal dedup check failed: %s", _dq_e)
                self._goal_store.save(goal)
                created += 1

            return {
                "step": "4.5", "name": "homeostasis_regulation",
                "drives": [d.drive.value for d in result.drives],
                "goals_created": created,
                "gated": len(result.gated),
                "actions": [a.name for a in result.actions],
            }
        except Exception as e:
            logger.warning("Homeostasis regulation failed: %s", e)
            return {"step": "4.5", "name": "homeostasis_regulation",
                    "gated": True, "error": str(e)}

    def _tick_step_goal_maintenance(self) -> dict[str, Any]:
        """Step 4: Goal Maintenance v2 — Phase 36 Attention-aware 目标维护。

        读取 AttentionReport，按推荐排序 Goal，限制深度，优先维护焦点 Goal。
        权限：读取 Goal 状态、触发维护检查。禁止：创建/删除/修改 priority。
        """
        try:
            report = self._attention_report

            if report is None:
                # 降级：无 AttentionReport 时回到 Phase 34 行为
                agent = self.agent
                if hasattr(agent, "goal_stack") and hasattr(agent.goal_stack, "get_active_count"):
                    return {"step": 4, "name": "goal_maintenance",
                            "active_goals": agent.goal_stack.get_active_count()}
                return {"step": 4, "name": "goal_maintenance", "status": "no_goal_stack"}

            # 1. 读取活跃 Goal
            goals = self._goal_store.load_active() if self._goal_store is not None else []

            if not goals:
                return {"step": 4, "name": "goal_maintenance", "active_total": 0}

            # 2. 按 Attention 推荐排序
            rec = report.recommendation
            prioritize = set(rec.prioritize_goals)
            deprioritize = set(rec.deprioritize_goals)

            ordered: list[dict] = []
            skipped: list[str] = []
            for g in goals:
                gid = g.get("id", g.get("goal_id", "?")) if isinstance(g, dict) else getattr(g, "goal_id", "?")
                if gid in deprioritize:
                    skipped.append(gid)
                    continue
                ordered.append(g)
            ordered.sort(
                key=lambda g: (
                    1 if (
                        g.get("id", "") if isinstance(g, dict)
                        else getattr(g, "goal_id", "")
                    ) in prioritize else 0,
                    g.get("priority", 0) if isinstance(g, dict) else getattr(g, "priority", 0),
                ),
                reverse=True,
            )

            # 3. 限制深度
            depth = max(rec.suggested_maintenance_depth, 1)
            ordered = ordered[:depth]

            # 4. 逐条维护检查（deadline staleness / progress 停滞检测）
            maintained: list[str] = []
            for g in ordered:
                gid = g.get("id", g.get("goal_id", "?")) if isinstance(g, dict) else getattr(g, "goal_id", "?")
                desc = g.get("description", "") if isinstance(g, dict) else getattr(g, "description", "")
                status = g.get("status", "") if isinstance(g, dict) else getattr(g, "status", "")
                logger.debug("Goal maintenance check: %s [%s] — %s", gid, status, desc[:60])
                maintained.append(gid)

            return {
                "step": 4,
                "name": "goal_maintenance",
                "phase": 36,
                "active_total": len(goals),
                "maintained": len(maintained),
                "skipped_by_attention": len(skipped),
                "attention_depth": depth,
            }

        except Exception as e:
            logger.error("Goal maintenance failed: %s", e, exc_info=True)
            return {"step": 4, "name": "goal_maintenance", "error": str(e)}

    def _tick_step_execution_check(self) -> dict[str, Any]:
        """Step 5: Execution Check v2 — Phase 36 Attention-aware。

        attention_block 是 ExecutionDecision（allowed=false），不是任务状态变更。
        禁止: Attention → Execution State Mutation (RUNNING → BLOCKED)。
        正确: ExecutionDecision: allowed=false, reason=ATTENTION_RESOURCE_UNAVAILABLE。
        """
        try:
            report = self._attention_report
            attention_allowed = True
            attention_block_reason = ""

            if report:
                if report.fatigue > 0.9:
                    attention_allowed = False
                    attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"
                elif report.mode in ("INTERRUPTED", "SUSPENDED"):
                    attention_allowed = False
                    attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"

            # 原有 controller 检查
            controller = self.controller
            stats = controller.get_stats() if hasattr(controller, "get_stats") else {}
            blocked = controller.is_blocked() if hasattr(controller, "is_blocked") else False

            return {
                "step": 5,
                "name": "execution_check",
                "phase": 36,
                "controller_blocked": blocked,
                "attention_allowed": attention_allowed,
                "attention_block_reason": attention_block_reason,
                "stats": stats,
            }
        except Exception as e:
            return {"step": 5, "name": "execution_check", "error": str(e)}

    def _tick_step_planning_trigger(self) -> dict[str, Any]:
        """Step 6: Planning Trigger v2 — Phase 36 三条件门控。

        Plan = Goal.ready AND Attention.available AND Resource.available
        Cognitive Serialization Constraint: max 1 Goal/Tick（非硬限制，单焦点模型推导）。
        Attention 权限: ALLOW_PLANNING / DEFER_PLANNING (signal only)。
        Attention 禁止: CREATE_PLAN / MODIFY_PLAN / CANCEL_PLAN。
        """
        try:
            report = self._attention_report

            # Gate 1: Attention available
            if report is not None and report.recommendation.suppress_planning:
                return {
                    "step": 6, "name": "planning_trigger", "phase": 36,
                    "gated": True, "reason": "attention_suppress",
                }

            # Gate 2: Resource available
            if self._active_dag is not None:
                return {
                    "step": 6, "name": "planning_trigger", "phase": 36,
                    "gated": True, "reason": "resource_saturated",
                    "active_dag_remaining": self._dag_total - self._dag_cursor
                    if hasattr(self, '_dag_cursor') else "?",
                }

            if self._goal_store is None:
                return {"step": 6, "name": "planning_trigger", "phase": 36, "decomposed": 0}

            # Gate 3: Goal ready + attention-aware filtering
            active = self._goal_store.load_active()
            pending = [g for g in active if getattr(g, "status", None) and g.status.name == "PENDING"]
            # UX-I: 人工目标优先于 SELF 目标（level 排序曾让 SELF 抢占分解名额）
            pending.sort(key=lambda g: 0 if getattr(
                getattr(g, "origin_level", None), "value", "") == "HUMAN" else 1)

            # If focused on a goal, only decompose that one
            if report is not None and report.focus_type == "GOAL" and not report.recommendation.ready_for_new_goal:
                pending = [g for g in pending if getattr(g, "goal_id", "") == report.current_focus_id]

            # Cognitive Serialization Constraint: max 1 Goal/Tick
            decomposed = 0
            for g in pending[:1]:
                try:
                    from ocos.planning.decomposer import TaskDecomposer
                    from ocos.kernel.goal_types import UserGoal, GoalDomain
                    import uuid
                    ug = UserGoal(
                        id=f"GOAL-{uuid.uuid4().hex[:8]}",
                        raw_input=g.description,
                        objective=g.description,
                        # UX-1: domain 跟随目标自身（此前硬编码 WRITING）
                        domain=getattr(g, "domain", GoalDomain.WRITING) or GoalDomain.WRITING,
                        caller="runtime",
                    )
                    # UX-I: chat 编译目标（描述已具体化到命令级）→ 单任务
                    # 直执行，不走模板分解——模板产出"分析数据"这类空壳
                    # 任务，LLM 无法转换（无数据源/无动作）
                    if getattr(g, "caller", "") == "chat":
                        from ocos.planning.models import Task as PlanTask, TaskDAG as PlanDAG
                        dag = PlanDAG()
                        _task = PlanTask.create(
                            goal_id=g.goal_id,
                            description=ug.objective or ug.raw_input or g.description,
                            task_type=_infer_task_type(g.description,
                                                       getattr(g, "domain", None)),
                            agent_type=_infer_agent_type(g.description,
                                                         getattr(g, "domain", None)),
                        )   # agent_type 限合法枚举（"executor" 曾致 ValueError → 分解永远失败）
                        dag.add_task(_task)
                    else:
                        dag = TaskDecomposer.decompose(ug)
                        # UX-F1: 模板任务携带目标语境
                        # FIX(AGI): PlanTask 是 @dataclass(frozen=True)，直接
                        # _t.description=... 抛 FrozenInstanceError 被吞 →
                        # 子任务永远是"收集数据"等空壳名，goal 指令（如"调用
                        # codex"）丢失 → bridge 注入/保真闸门全部无法命中。
                        # 用 dataclasses.replace 重建任务并写回 DAG。
                        goal_ctx = (ug.objective or ug.raw_input or "")[:80]
                        import dataclasses as _dc
                        for _tid, _t in list(dag.tasks.items()):
                            _d = getattr(_t, "description", "")
                            if goal_ctx and goal_ctx not in _d:
                                try:
                                    dag.tasks[_tid] = _dc.replace(
                                        _t, description=f"{goal_ctx} — {_d}")
                                except Exception:
                                    pass
                    self._active_dag = dag
                    self._dag_cursor = 0
                    self._dag_total = len(dag.tasks)
                    self._dag_tick_count = 0   # P2: 新 DAG 重置超时计数
                    # UX-F2+: 结果汇总起点 — 只汇总当前目标的任务输出，
                    # 不混入上一目标残留（此前 _recent_results 不清空导致串味）
                    self._result_mark = len(getattr(self, "_recent_results", []))
                    # UX-堆积修复: 分解后目标状态推进 PENDING → ACTIVE
                    # （此前状态不变 → 同一目标每 tick 被重复分解 + 重复调 LLM）
                    try:
                        from ocos.kernel.goal_types import GoalStatus as _GS
                        g.status = _GS.ACTIVE
                        self._goal_store.save(g)
                    except Exception as _st_e:
                        logger.debug("goal status advance failed: %s", _st_e)
                    self._active_dag_goal_id = g.goal_id
                    # PW-4.4: 同步 ocos.task 执行期镜像（Stage ⑤ 消费）
                    self._sync_task_mirror(dag)
                    decomposed = 1
                except Exception as inner_e:
                    logger.warning("Planning decomposition failed: %s", inner_e)

            return {
                "step": 6, "name": "planning_trigger",
                "phase": 36,
                "pending_total": len(pending),
                "decomposed": decomposed,
                "gated_by_attention": (report is not None and report.recommendation.suppress_planning),
            }
        except Exception as e:
            return {"step": 6, "name": "planning_trigger", "error": str(e)}

    def _sync_task_mirror(self, planning_dag: Any) -> None:
        """PW-4.4: 规划 DAG → ocos.task 执行期 TaskDAG 镜像。

        供 RuntimeKernel Stage ⑤ (ExecutionCheckStage) resolve_ready()
        生成执行候选 — ocos.task 的首个生产消费者。
        """
        try:
            from ocos.task import TaskDAG as ExecDAG, TaskStatus
            mirror = ExecDAG()
            for tid, task in planning_dag.tasks.items():
                mirror.add_task(task_id=tid,
                                name=getattr(task, "description", "")[:60])
                for dep in (getattr(task, "inputs", None) or ()):
                    try:
                        mirror.add_dependency(tid, dep)
                    except Exception:
                        pass  # 环/缺依赖 → 跳过该边（诚实降级）
            self._task_mirror = mirror
        except Exception as e:
            logger.debug("task mirror sync failed: %s", e)

    @property
    def task_mirror(self) -> Any:
        """PW-4.4: 执行期任务镜像（RuntimeKernel 注入用）。"""
        return getattr(self, "_task_mirror", None)

    def _record_goal_result(self) -> None:
        """UX-F2: DAG 执行完毕 → 目标结果摘要 Episode（真实输出可对话查询）。

        decision 字段 = 各任务真实输出的聚合（此前 EchoAgent 时代这里
        全是空转记录，主人问"结果呢"时无从回答）。
        """
        if self._memory_hub is None or not self._memory_hub.is_initialized():
            return
        try:
            import uuid as _uuid
            from datetime import datetime, timezone
            from ocos.memory.episode.models import Episode, EpisodeStatus

            results = list(self._recent_results)[
                max(getattr(self, "_result_mark", 0), len(self._recent_results) - 12):]
            # P0-2: 交付物相关性最小校验 — 描述要求正文交付物而执行证据
            # 仅为 shell 回显 → 诚实降级为失败（在汇总行/落库前生效）
            for r in results:
                _desc = str(r.get("description", ""))
                if (r.get("success")
                        and r.get("capability") == "shell"
                        and _DELIVERABLE_GOAL_RE.search(_desc)
                        and not _DATA_COLLECT_RE.search(_desc)):
                    r["success"] = False
                    r["output"] = ("【交付物缺失】该任务要求计划/方案/报告类"
                                   "正文交付物，但执行证据仅为 shell 命令回显"
                                   "（无 ANSWER 正文、无 FILE_WRITE 落盘），"
                                   "诚实降级为失败。\n"
                                   + str(r.get("output", "")))[:1600]
                    logger.warning("deliverable gap downgraded: %s",
                                   _desc[:60])
                # P0-2b (2026-09-08「开发虚拟人应用」事件): 开发/构建类 —
                # 交付物 = 落盘工件，执行证据全为只读探查（无写指示符）→
                # 物理上不可能完成，诚实降级。独立判定采集豁免（开发类
                # 描述常带"检查/运行"字样，采集豁免会使条款形同虚设）。
                elif (r.get("success")
                      and r.get("capability") == "shell"
                      and _BUILD_GOAL_RE.search(_desc)
                      # P0-2f 校准: 评估/画像类意图（"部署可行性评估"）不是
                      # 构建动作，纯只读探查是其合法完成形态，不降级
                      and not _BUILD_ASSESS_RE.search(_desc)
                      and not _has_write_evidence(r.get("output", ""))):
                    r["success"] = False
                    r["output"] = ("【交付物缺失】该任务要求开发/构建类工件"
                                   "（项目结构/代码/依赖落盘），但执行证据仅"
                                   "为只读探查命令（无任何写操作），诚实降级"
                                   "为失败。\n"
                                   + str(r.get("output", "")))[:1600]
                    logger.warning("build deliverable gap downgraded: %s",
                                   _desc[:60])
                # P0-2c: 总结器自认不完整 — 固定 prompt 要求"判断是否达成"，
                # 摘要显式承认未完整/缺少调研 → 诚实降级（描述类正则的兜底，
                # 混合型目标（联网调研+本地检查）靠采集豁免溜过上面两关）。
                # P0-2c 校准（2026-09-08 E2E 复测）: 摘要可能在交付实质正文
                # （调研表+升级方案 1500 字）的同时提及某子步骤（README 抓取）
                # 未完成并自述"部分达成"——此时交付物已存在，降级会把真实
                # 价值标成失败。规则收紧: 自认不完整 且 摘要缺乏实质交付
                # 内容（<600 字）才降级；长摘要视为已含交付物正文。
                elif r.get("success"):
                    _out = str(r.get("output", ""))
                    if _out.startswith("【结论摘要】"):
                        _summary = _out.split("【原始输出】", 1)[0]
                        if (_SELF_INCOMPLETE_RE.search(_summary)
                                and len(_summary) < 600):
                            r["success"] = False
                            r["output"] = ("【执行不完整】结论摘要自认任务未"
                                           "完整达成（存在缺失的调研/交付部"
                                           "分），诚实降级为失败。\n" + _out)[:1600]
                            logger.warning("self-admitted incomplete "
                                           "downgraded: %s", _desc[:60])
            lines = []
            for r in results:
                ok = "✓" if r.get("success") else "✗"
                out = _truncate_text(r.get("output", ""), 1500)
                lines.append(f"{ok} {r.get('description', '')[:50]} → {out}")
            if not lines:
                return
            # P2: 能力级实测归因 — 同名能力多结果时 AND 聚合（一次目标内
            # shell 全成功才算该次 shell 实测成功），供自我模型统计
            _cap_success: dict[str, bool] = {}
            for r in results:
                _cap = r.get("capability")
                if _cap:
                    _cap_success[_cap] = bool(
                        _cap_success.get(_cap, True)) and bool(r.get("success"))
            episode = Episode(
                id=f"EPI-{uuid.uuid4().hex[:12]}",
                experience_id=f"EXP-GOAL-{uuid.uuid4().hex[:8]}",
                created_at=datetime.now(timezone.utc),
                session_id=f"tick_{self._cycle_count}",
                context={"task_count": len(results),
                         "kind": "goal_execution_result",
                         # P2: 此前 context 无 agent 键 → 自我模型把全部
                         # 目标归到 "?"，agent 级成功率永远失真
                         "agent": next((r.get("agent") for r in results
                                        if r.get("agent")), "?"),
                         "capabilities": [{"name": k, "success": v}
                                          for k, v in sorted(_cap_success.items())]},
                goal="目标执行结果汇总",
                decision="\n".join(lines)[:4000],
                action="goal_result",
                outcome={"success": all(r.get("success") for r in results) or len(results) == 0,
                         "cycle": self._cycle_count,
                         "task_success_rate": sum(1 for r in results if r.get("success")) / max(len(results), 1)},
                significance_score=0.7,
                source="goal_result",
                status=EpisodeStatus.ACTIVE,
                tags=["goal_result"],
            )
            self._memory_hub.episode.save(episode)
            logger.info("Goal result episode saved (%d tasks)", len(results))
            # UX-J 即时推送: 通知宿主（daemon）立刻推送出站消息，
            # 不等 5-tick 节拍；回调失败不阻断主流程
            cb = getattr(self, "_on_goal_result", None)
            if cb is not None:
                try:
                    cb()
                except Exception as cb_e:  # noqa: BLE001
                    logger.debug("on_goal_result callback failed: %s", cb_e)
            # P4.1 (AGI 计划): 目标完成后触发技能习得 — 从最近成功 goal_result
            # episode 归纳候选技能（只读自动提交、写类待审批）。失败不阻断。
            try:
                self._grow_skills()
            except Exception as _gs_e:
                logger.debug("skill growth skipped: %s", _gs_e)
        except Exception as e:
            logger.debug("goal result episode skipped: %s", e)

    def _grow_skills(self) -> dict[str, Any]:
        """P4.1 (AGI 计划): 技能习得触发 — 最近成功 goal_result → 候选技能。

        输入：hub.episode 最近 goal_result episodes（SkillProposer 归纳成功
        任务指纹 → 四段生命周期）。产出打点 skill_growth{stage} 供观测。
        """
        try:
            episodes = (self._memory_hub.episode
                        .query_by_source("goal_result", limit=30))
        except Exception as e:
            logger.debug("skill growth episodes fetch failed: %s", e)
            return {}
        if not episodes:
            return {}
        grow = getattr(self.agent, "grow_skills_from_episodes", None)
        if grow is None:
            return {}
        stats = grow(episodes) or {}
        try:
            from ocos.monitoring.manager import record_global
            record_global("skill_growth", float(stats.get("proposals", 0)),
                          labels={"stage": "proposals"})
            record_global("skill_growth", float(stats.get("committed", 0)),
                          labels={"stage": "committed"})
        except Exception:
            pass
        if stats.get("proposals"):
            logger.info("Skill growth: %s", str(stats)[:200])
        return stats

    def attach_decision_bridge(self, bridge: Any) -> None:
        """R4-A: 挂载决策执行铰链 (公开装配入口, 供 daemon.factory 调用)。

        挂载后 step 7 的 TaskDAG 任务与 step 8 的决策输出优先经
        DecisionBridge 风险分级执行; 未挂载或裸构造实例保持既有行为。
        P1.2 (AGI 计划): 挂载时把本 runtime 的 learning_artifacts 绑定为
        bridge 学习产物源（决策 prompt 注入通道）。
        """
        self._decision_bridge = bridge
        attach = getattr(bridge, "attach_learning_source", None)
        if attach is not None:
            try:
                attach(self.learning_artifacts)
            except Exception as _lse:
                logger.debug("learning source bind skipped: %s", _lse)
        # P2.1 (AGI 计划): 世界状态检索源 — 经 master_agent.world_context 消费
        # WorldStore（感知→世界模型→决策；空世界返回 available=False 不注入）
        attach_world = getattr(bridge, "attach_world_source", None)
        if attach_world is not None:
            try:
                attach_world(lambda _desc: self.agent.world_context())
            except Exception as _wse:
                logger.debug("world source bind skipped: %s", _wse)

    def _replan_failed_task(self, task_id: str, task: Any,
                            reason: str) -> dict[str, Any]:
        """Phase 49-C (L4): 失败任务重规划决策。

        用 FailureDiagnoser 分类失败原因 → TaskReplanner 决定动作:
          - 执行错误/超时 (未超次数) → retry_pending (下 tick 重试)
          - 模糊任务/不可重试 → 终态 (推进 cursor, 记录 replan 元数据)

        治理: 重试次数上限 MAX_RETRY_PER_TASK; 写类动作仍由
        DecisionBridge 分级 (此处只管重试节奏, 不触碰权限)。
        """
        from ocos.learning.skill_growth import TaskReplanner
        from ocos.learning.experience_learning import FailureDiagnoser

        # 从失败文本分类原因 (复用 Phase 49-A 确定性诊断)
        cause = "unknown"
        diag = None
        try:
            # 构造最小 episode 形状供诊断器使用
            fake_ep = type("FailedTask", (), {
                "id": task_id,
                "outcome": {"success": False, "reason": reason,
                            "error": reason},
                "decision": f"failed: {reason[:100]}",
            })()
            diag = FailureDiagnoser.diagnose(fake_ep)
            if diag is not None:
                cause = diag.cause.value
                self._last_failure_cause = cause
        except Exception:
            pass

        retry_count = getattr(self, "_task_retry_count", {}).get(task_id, 0)
        decision = TaskReplanner.decide(task_id, cause, retry_count)
        meta: dict[str, Any] = {
            "task_id": task_id,
            "cause": cause,
            "decision": decision.action.value,
            "reason": decision.reason,
            "retry_count": retry_count,
        }
        if TaskReplanner.should_retry(decision):
            # 裸实例兼容 (Phase 31: __new__ 构造无 __init__ 字段)
            counts = getattr(self, "_task_retry_count", None)
            if counts is None:
                self._task_retry_count = {}
                counts = self._task_retry_count
            counts[task_id] = retry_count + 1
            meta["decision"] = "retry_pending"

            # FIX-9: 重试不再"原样重放同描述" — 把失败原因回注到任务描述,
            # 使下 tick 桥端规划 LLM 看到失败上下文并给出修正/替代的可行方案
            # （等价于 bridge 沙盒拦截后的带反馈重试, 只是从 daemon 重试层生效）。
            # task==PlanTask 可变, 用 try 防御; base 存档避免多次重试反复叠加注记。
            bases = getattr(self, "_task_base_desc", None)
            if bases is None:
                bases = {}
                self._task_base_desc = bases
            if task_id not in bases:
                bases[task_id] = (getattr(task, "description", "") or "")
            revised = self._revise_task_description(
                bases[task_id], reason, retry_count + 1)
            # FIX(AGI): PlanTask 为 frozen dataclass，直接赋值抛
            # FrozenInstanceError 被吞 → 重试描述回注从未生效。用
            # dataclasses.replace 重建并写回 active DAG。
            try:
                import dataclasses as _dc
                _active = getattr(self, "_active_dag", None)
                if (_active is not None
                        and task_id in getattr(_active, "tasks", {})):
                    _active.tasks[task_id] = _dc.replace(
                        task, description=revised)
                else:
                    object.__setattr__(task, "description", revised)
            except Exception:
                pass
            meta["revised_description"] = revised
        else:
            # 终态: 清理重试计数, 该任务按失败归档
            counts = getattr(self, "_task_retry_count", None)
            if counts is not None:
                counts.pop(task_id, None)
            # P5.1 (AGI 计划): 不可修正/重试耗尽失败 → 教训回学习管道（feed G1）
            # （模糊任务/工具受限/重试耗尽 → honest failed + 教训入库）
            meta["lesson"] = self._record_failure_lesson(
                task_id, task, diag, decision, reason)
        return meta

    def _revise_task_description(self, base: str, reason: str,
                                 attempt: int) -> str:
        """FIX-9/07: 把失败原因回注为修正后的任务描述。

        覆盖 base 保持不含历史注记的原始描述；返回带【执行反馈】的修订版，
        供重试时桥端规划 LLM 可见失败上下文，产出一套可规避该失败的方案
        （而非原样重放导致同样失败）。确定性文本拼接，无需额外 LLM。
        FIX-07: 同时注入诊断原因，使下一次规划看到"为什么失败"。
        """
        _base = (base or "").strip()
        _reason = (reason or "").strip()[:200]
        _cause = getattr(self, '_last_failure_cause', 'unknown')
        note = (
            f"【执行反馈】第{attempt}次尝试执行失败"
            + (f"：{_reason}" if _reason else "。")
            + f"\n【失败诊断】原因：{_cause}"
            + "\n请据此修正或换一种可行的具体命令/方案"
              "（优先使用只读白名单命令），不要重复会失败的做法。"
        )
        return f"{_base}\n{note}" if _base else note.strip()

    def _record_failure_lesson(self, task_id: str, task: Any,
                               diagnosis: Any, decision: Any,
                               reason: str) -> dict[str, Any]:
        """P5.1 (AGI 计划): 失败教训回学习管道 — 不可修正失败 → LESSON 入库。

        对齐 G5（失败归因重规划）: 归因已由 FailureDiagnoser 完成（确定性
        规则，无 LLM；覆盖目标模糊/工具受限/执行错误/超时/权限拒绝），
        此处把结构化教训持久化为 source="lesson" Episode（复用 EpisodeStore，
        零新表）。下一周期 _fast_path_learning 重放 → RuleBasedLearner 聚合
        failure_causes 分布（feed G1 统计侧，为未来决策提供成功率依据）。

        治理: 教训只进统计学习管道，不注入决策 prompt（延续 FIX-4 教训——
        失败史注入造成负反馈循环）。未装配 memory hub / 写入失败 → 静默跳过，
        不影响主流程。
        """
        # diagnosis.cause 为 FailureCause 枚举 → 归一为字符串值（与
        # _replan_failed_task 的 cause 语义一致，供指标/标签/检索使用）
        _cause = getattr(diagnosis, "cause", "unknown")
        _cause = _cause.value if hasattr(_cause, "value") else str(_cause)
        lesson: dict[str, Any] = {
            "task_id": task_id,
            "cause": _cause,
            "recorded": False,
        }
        hub = getattr(self, "_memory_hub", None)
        if hub is None or not hub.is_initialized():
            return lesson
        try:
            import uuid as _uuid
            from datetime import datetime, timezone
            from ocos.learning.experience_learning import (
                FailureCause, FailureDiagnosis, build_lesson_artifact,
            )
            from ocos.memory.episode.models import Episode, EpisodeStatus

            if diagnosis is None:
                # 归因失败 → 以 UNKNOWN 教训兜底（仍入库，避免信息黑洞）
                diagnosis = FailureDiagnosis(
                    episode_id=f"task:{task_id}",
                    cause=FailureCause.UNKNOWN,
                    hypothesis="失败原因无法从现有证据分类",
                    evidence=(reason or "")[:500],
                    signals_hit=(),
                )
            description = (getattr(task, "description", "") or "")[:300]
            # P2: normalized_goal — 去噪后提取稳定语义签名
            _sig_text = _normalize_goal_for_signature(description)
            _signature = f"{_sig_text}|{_cause}"
            artifact = build_lesson_artifact(diagnosis, description)
            episode = Episode(
                id=f"EPI-LESSON-{_uuid.uuid4().hex[:12]}",
                experience_id=artifact.id,
                created_at=datetime.now(timezone.utc),
                session_id=f"tick_{getattr(self, '_cycle_count', 0)}",
                context={
                    "lesson_type": "failure_pattern",
                    "task_id": task_id,
                    "artifact_id": artifact.id,
                    "goal_pattern": description[:100],
                    # P2: failure_signature — 精确检索键
                    # 格式: "<normalized_goal>|<cause>"
                    # 替代原来的 LIKE 模糊匹配，避免 30 字截断丢失语义
                    "failure_signature": _signature,
                },
                goal=description[:200],
                decision=(f"[{artifact.artifact_type.value}] "
                          f"{artifact.hypothesis}")[:400],
                action="failure_lesson",
                outcome={
                    "success": False,
                    "cause": _cause,
                    "replan": (decision.action.value
                               if getattr(decision, "action", None) else ""),
                    "confidence": artifact.confidence,
                },
                condition=(f"task:{task_id} failed "
                           f"cause={_cause}"),
                significance_score=0.55,
                evaluation_trace={"source": "p5.1_replan",
                                  "task_id": task_id},
                source="lesson",
                status=EpisodeStatus.ACTIVE,
                tags=["failure_lesson", _cause],
            )
            hub.episode.save(episode)
            lesson["recorded"] = True
            lesson["artifact_id"] = artifact.id
            lesson["episode_id"] = episode.id
            try:
                from ocos.monitoring.manager import record_global
                record_global("failure_lesson", 1.0,
                              labels={"cause": _cause})
            except Exception:
                pass
            logger.info("Failure lesson recorded: cause=%s task=%s "
                        "artifact=%s", _cause, task_id, artifact.id)

            # P2a-2026-09-10: DEPENDENCY_MISSING → agent 能力 offline 标记
            # 硬依赖缺失（shell 命令/Python 模块不可用）不是可修复的软错误。
            # 除了 failure_lesson episode，还要写明确的 agent capability 状态
            # 让 GoalGenesis / EpistemicDrive 知道: writer 在当前环境不可用。
            if _cause == "dependency_missing":
                try:
                    self._record_capability_offline(task, diagnosis, reason)
                except Exception as e2:
                    logger.debug("capability offline record skipped: %s", e2)
        except Exception as e:
            logger.debug("failure lesson recording skipped: %s", e)
        return lesson

    def _record_capability_offline(self, task: Any, diagnosis: Any,
                                    reason: str) -> None:
        """P2a-2026-09-10: DEPENDENCY_MISSING → 标记 agent 能力 offline.

        写入 belief 表:
          statement: "<agent_type> 在当前环境因依赖缺失不可用: <dependency>"
          confidence: 0.0 (确定不可用)
          tags: ["capability_offline", "dependency_missing", agent_type]

        供 GoalGenesis / EpistemicDrive 查询 → 不再生成该 agent 的目标。
        依赖修复后（P2b 自恢复），需手动或重启后重新探测。
        """
        from datetime import datetime, timezone
        import sqlite3

        agent_type = getattr(task, "agent_type", "unknown") or "unknown"
        evidence = getattr(diagnosis, "evidence", reason or "") or ""

        # 从 evidence 提取缺失的依赖 (启发式)
        dep = "unknown_dependency"
        for sig in ("/bin/sh:", "command not found", "exit_code=127",
                    "ModuleNotFoundError", "No module named"):
            if sig in evidence:
                # 尝试提取具体命令/模块名
                if "/bin/sh:" in evidence:
                    # "/bin/sh: 1: sqlite3: not found" → "sqlite3"
                    import re as _re
                    m = _re.search(r"/bin/sh:\s*\d+:\s*(\S+):", evidence)
                    if m:
                        dep = m.group(1)
                elif "No module named" in evidence:
                    import re as _re
                    m = _re.search(r"No module named ['\"]?(\S+?)['\"]?", evidence)
                    if m:
                        dep = f"python:{m.group(1)}"
                break

        hub = getattr(self, "_memory_hub", None)
        db_path = None
        if hub and hasattr(hub, "db_path"):
            db_path = hub.db_path
        elif hub and hasattr(hub, "_db_path"):
            db_path = hub._db_path

        belief_text = (
            f"agent[{agent_type}] 在当前环境因依赖 '{dep}' 不可用"
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        if db_path:
            try:
                import uuid as _uuid
                import json as _json
                conn = sqlite3.connect(db_path)
                conn.execute(
                    """INSERT INTO belief
                        (id, statement, confidence, uncertainty, scope, status,
                         created_at, last_updated, source_knowledge_ids, evidence_ids)
                    VALUES (?, ?, 0.0, 1.0, ?, 'active', ?, ?, '[]', '[]')""",
                    (f"BLF-CAPOFF-{_uuid.uuid4().hex[:10]}",
                     belief_text,
                     _json.dumps({"type": "capability_offline",
                                  "agent": agent_type,
                                  "dependency": dep}),
                     now_iso, now_iso))
                conn.commit()
                conn.close()
                logger.warning(
                    "P2a-capability-offline: %s → dep=%s (written to belief)",
                    agent_type, dep)
            except Exception:
                pass
        else:
            logger.warning(
                "P2a-capability-offline: %s → dep=%s (no db_path, belief not written)",
                agent_type, dep)

        # 同时写一条 episode 让 cognition loop 可见
        try:
            from ocos.memory.episode.models import Episode, EpisodeStatus
            import uuid as _uuid
            ep = Episode(
                id=f"EPI-CAPOFF-{_uuid.uuid4().hex[:10]}",
                created_at=now_iso,
                session_id="capability_offline",
                context={"agent_type": agent_type, "dependency": dep,
                         "evidence": evidence[:200]},
                goal=f"capability_offline:{agent_type}",
                decision=belief_text[:300],
                action="capability_offline",
                outcome={"success": False, "cause": "dependency_missing",
                         "confidence": 0.0},
                condition=f"agent={agent_type} dep={dep}",
                significance_score=0.9,
                tags=["capability_offline", "dependency_missing", agent_type],
                source="system",
                status=EpisodeStatus.ACTIVE,
            )
            if hub:
                hub.episode.save(ep)
        except Exception:
            pass

    def _tick_step_core_loop(self) -> dict[str, Any]:
        """Step 7: Core Loop — 优先执行 TaskDAG，无 DAG 时回退认知循环。

        Phase 31: 每 tick 从 active_dag 取 1 个 task → echo_agent.execute。
        """
        # ── Phase 31: TaskDAG execution ──
        if self._active_dag is not None:
            # P2: DAG 超时杀 — 每个 tick 存活 +1，超过阈值强制收尾
            # hasattr 防御: 部分测试直接 AgentRuntime() 不走完整 __init__
            _tick = getattr(self, "_dag_tick_count", 0)
            _timeout = getattr(self, "_DAG_TICK_TIMEOUT", 999999)
            self._dag_tick_count = _tick + 1
            if _tick + 1 > _timeout:
                logger.warning(
                    "DAG timed out after %d ticks (limit=%d), force-closing",
                    _tick + 1, _timeout)
                self._recent_results.append({
                    "task_id": "TIMEOUT",
                    "description": (
                        f"DAG 存活 {_tick + 1} tick "
                        f"超过阈值 {_timeout}，强制终止"),
                    "agent": "runtime",
                    "output": "DAG_TIMEOUT",
                    "success": False,
                })
                # 把关联目标标 FAIL
                gid = getattr(self, "_active_dag_goal_id", None)
                if gid and self._goal_store:
                    try:
                        g = self._goal_store.load(gid)
                        if g is not None:
                            from ocos.kernel.goal_types import GoalStatus
                            g.status = GoalStatus.FAILED
                            g.completed_at = datetime.now(timezone.utc)
                            self._goal_store.save(g)
                    except Exception as _e:
                        logger.debug("DAG timeout goal status advance failed: %s", _e)
                # 清理 DAG 状态
                self._active_dag = None
                self._dag_cursor = 0
                self._dag_total = 0
                self._dag_tick_count = 0
                self._active_dag_goal_id = None
                return {
                    "step": 7, "name": "core_loop",
                    "strategy": "dag_timeout",
                    "progress": "forced_close",
                    "tick_count": self._dag_tick_count,
                }

            order = self._active_dag.topological_order()
            if self._dag_cursor < len(order):
                tid = order[self._dag_cursor]
                task = self._active_dag.tasks[tid]
                try:
                    # R4-A: 真实任务优先经 DecisionBridge 执行
                    # (只读 analyze/verify → AUTO 真实执行; create/modify/execute → ASK 待批)
                    # getattr: 兼容 __new__ 裸构造实例 (Phase 31 合约), 避免静默 AttributeError
                    bridge = getattr(self, "_decision_bridge", None)
                    if bridge is not None:
                        dag_result = bridge.execute_dag_task(task)
                        dag_status = dag_result.get("status", "")
                        if dag_status != "echo_fallback":
                            # Phase 49-C (L4): 失败 → 重规划决策
                            # (执行错误/超时 → 有限重试; 模糊任务 → 终态阻塞)
                            replan_meta: dict[str, Any] = {}
                            if dag_status == "failed":
                                reason = str(
                                    dag_result.get("reason")
                                    or dag_result.get("error")
                                    or "")[:300]
                                replan_meta = self._replan_failed_task(
                                    tid, task, reason)
                                if replan_meta.get("decision") == "retry_pending":
                                    # 本 tick 不推进 cursor — 下 tick 重试同任务
                                    self._task_statuses[tid] = "retry_pending"
                                    self._recent_results.append({
                                        "task_id": tid,
                                        "description": task.description,
                                        "agent": task.agent_type,
                                        "output": (f"retry scheduled: {reason[:120]}"),
                                        "success": False,
                                    })
                                    return {
                                        "step": 7, "name": "core_loop",
                                        "strategy": "dag_execution",
                                        "task": tid,
                                        "progress":
                                            f"{self._dag_cursor}/{self._dag_total}",
                                        "execution": "retry_pending",
                                        "retry_count": replan_meta.get(
                                            "retry_count", 0),
                                        "output": reason[:150],
                                    }

                            # completed/failed/pending_approval 诚实透传, 不把失败伪装成待批
                            self._task_statuses[tid] = (
                                dag_status if dag_status in ("completed", "failed", "pending_approval")
                                else "pending_approval"
                            )
                            # UX-F2+: completed → 提取真实 stdout（此前存整个
                            # dict repr 截断 200 字符，主人问结果时无数据可答）
                            _res = dag_result.get("result")
                            _stdout = (_res.get("stdout", "")
                                       if isinstance(_res, dict) else "")
                            _out = _truncate_text(
                                str(_stdout or dag_result), 1600)
                            self._recent_results.append({
                                "task_id": tid,
                                "description": task.description,
                                "agent": task.agent_type,
                                "output": _out,
                                "success": dag_status == "completed",
                                # P2: bridge 能力实测标签（shell/filesystem/
                                # None=纯认知 ANSWER），供交付物校验与自我模型归因
                                "capability": (_res.get("capability")
                                               if isinstance(_res, dict)
                                               else None),
                            })
                            self._dag_cursor += 1
                            return {
                                "step": 7, "name": "core_loop",
                                "strategy": "dag_execution",
                                "task": tid,
                                "progress": f"{self._dag_cursor}/{self._dag_total}",
                                "execution": dag_status,
                                "output": str(dag_result)[:200],
                                "replan": replan_meta or None,
                            }
                    # 既有 EchoAgent 回退 (无能力匹配 / bridge 未装配)
                    from ocos.capability.echo_agent import EchoAgent
                    agent = EchoAgent(prefix=task.agent_type.capitalize())
                    result = agent.execute(
                        prompt=task.description,
                        task_type=task.task_type,
                        task_id=tid,
                    )
                    self._task_statuses[tid] = "completed"
                    output = result.get("output", str(result))
                    self._recent_results.append({
                        "task_id": tid,
                        "description": task.description,
                        "agent": task.agent_type,
                        "output": output,
                        "success": True,
                    })
                    self._dag_cursor += 1
                    return {
                        "step": 7, "name": "core_loop",
                        "strategy": "dag_execution",
                        "task": tid,
                        "progress": f"{self._dag_cursor}/{self._dag_total}",
                        "output": output[:200],
                    }
                except Exception as e:
                    logger.warning("core_loop task %s execution failed: %s", tid, e)
                    self._task_statuses[tid] = "failed"
                    self._dag_cursor += 1
                    return {"step": 7, "name": "core_loop", "task": tid, "error": str(e)}

            # DAG exhausted — UX-F2: 目标执行完毕 → 结果摘要 Episode
            try:
                self._record_goal_result()
            except Exception as _gr_e:
                logger.debug("goal result episode failed: %s", _gr_e)
            # UX-堆积修复: 目标生命周期闭合 ACTIVE → COMPLETED
            gid = getattr(self, "_active_dag_goal_id", None)
            try:
                from ocos.kernel.goal_types import GoalStatus as _GS
                if gid and self._goal_store is not None:
                    _g = self._goal_store.load(gid)
                    if _g is not None and _g.status.name == "ACTIVE":
                        _g.status = _GS.COMPLETED
                        self._goal_store.save(_g)
            except Exception as _gc_e:
                logger.debug("goal completion failed: %s", _gc_e)
            # P1 (2026-09-01): 域层 goals 表同步写回 — 认领路径
            # (daemon._claim_persisted_goals) 置域层 ACTIVE, 完成路径此前
            # 只更新 agent 层 goal 表 → 域层永久卡 ACTIVE。此处经 GoalStore
            # mark_completed 补齐双表闭环 (agent 层失败不阻断域层同步)。
            try:
                if gid and getattr(self, "_db_path", None):
                    from ocos.goal.store import GoalStore as _DGoalStore
                    _DGoalStore(db_path=self._db_path).mark_completed(gid)
            except Exception as _dc_e:
                logger.debug("domain goal completion sync failed: %s", _dc_e)
            self._active_dag_goal_id = None
            self._active_dag = None
            self._dag_cursor = 0
            self._dag_total = 0

        # ── Fallback: original cognitive loop (or idle if not booted) ──
        # FIX-01: 生产默认停用 idle 兜底认知循环（空转无输出，白耗 CPU）
        # OCOS_ENABLE_COGNITIVE_LOOP=1 可重新启用（调试/未来用途）
        _enable_cognitive_loop = os.environ.get("OCOS_ENABLE_COGNITIVE_LOOP", "0") == "1"
        if _enable_cognitive_loop and hasattr(self, "loop") and self.loop is not None:
            try:
                result = self.loop.execute_single()
                # R4-A: 缓存决策结果供 step 8 Dispatch 经 DecisionBridge 执行
                self._last_core_loop_result = result if isinstance(result, dict) else {}
                return {"step": 7, "name": "core_loop", "status": result.get("status", "unknown")}
            except Exception as e:
                return {"step": 7, "name": "core_loop", "error": str(e)}
        return {"step": 7, "name": "core_loop", "status": "idle"}

    def _tick_step_dispatch(self) -> dict[str, Any]:
        """Step 8: Dispatch — 通过 Bridge + Gateway 派发结果。

        Phase 24-A: 所有 dispatch 合约经过 PermissionGateway 验证。
        """
        gateway_stats = {"checks": 0, "allowed": 0, "blocked": 0}
        try:
            # Gateway 扫描待审批的 dispatch contract
            gw = self.gateway
            # 从 controller/loop 获取当前合约
            contracts = []
            if hasattr(self.controller, "pending_contracts"):
                contracts = self.controller.pending_contracts or []
            for contract in contracts:
                try:
                    result = gw.validate_or_raise(contract)
                    gateway_stats["checks"] += 1
                    gateway_stats["allowed"] += 1
                except PermissionDeniedError as e:
                    gateway_stats["checks"] += 1
                    gateway_stats["blocked"] += 1
                    logger.warning("Gateway blocked contract: %s", e)
        except Exception as e:
            logger.debug("Gateway dispatch scan skipped: %s", e)

        # ── R4-A: DecisionBridge — 决策输出 → 真实执行 (AUTO) / 待批 (ASK) ──
        bridge_stats: dict | None = None
        decision_bridge = getattr(self, "_decision_bridge", None)
        last_result = getattr(self, "_last_core_loop_result", None)
        if decision_bridge is not None and last_result:
            try:
                report = decision_bridge.process(last_result)
                bridge_stats = report.summary()
            except Exception as e:
                logger.warning("DecisionBridge process failed: %s", e)

        return {
            "step": 8, "name": "dispatch",
            "status": "via_core_loop",
            "gateway": gateway_stats,
            "bridge": bridge_stats,
        }

    def _tick_step_result_ingest(self) -> dict[str, Any]:
        """Step 9: Result Ingest — 消费执行结果 → Memory + Attention（Phase 32）。

        通过 _result_cursor 读取 _recent_results（不弹），保留给 step 10 模式提取。
        """
        ingested = None
        mem_before = self.memory.working_count

        # ── Phase 32: 消费执行结果 ──
        if self._result_cursor < len(self._recent_results):
            ingested = self._recent_results[self._result_cursor]
            self._result_cursor += 1

            # A. 写入 Working Memory
            content = f"[{ingested['agent']}] {ingested['description']}: {ingested['output'][:200]}"
            importance = 0.6 if ingested['success'] else 0.4
            self.memory.add_to_working(
                content=content,
                importance=importance,
                tags=[ingested['agent'], ingested.get('task_id', '')],
                metadata={"task_id": ingested.get('task_id', ''), "success": ingested['success']},
            )

            # B. Phase 34C: 写入 MemoryHub Episode（Result → Episode 沉淀）
            self._record_episode_from_result(ingested)

            # C. 推送 Attention 信号
            try:
                from ocos.capability.attention import TargetType, FocusTarget
                au = self.attention
                au.push_focus(FocusTarget(
                    target_type=TargetType.GOAL,
                    target_id=ingested.get("task_id", "task"),
                    priority=0.6 if ingested["success"] else 0.3,
                    description=f"{ingested['agent']}: {ingested['description'][:60]}",
                ))
            except Exception as _att_e:
                # BR-04 B批（2026-08-25）：attention 信号推送失败留痕。
                logger.warning("attention.push_focus failed: %s", _att_e)

        # ── 基础经验记录（向后兼容） ──
        try:
            self.experiences.record(
                situation=f"tick_{self._cycle_count}",
                action="cognitive_cycle",
                outcome="completed",
            )
        except Exception as _exp_e:
            # BR-04 B批（2026-08-25）：经验记录失败留痕，否则学习输入静默丢失。
            logger.warning("experiences.record failed: %s", _exp_e)

        return {
            "step": 9, "name": "result_ingest",
            "ingested": ingested is not None,
            "memory": {"working_before": mem_before, "working_now": self.memory.working_count}
            if ingested else None,
        }

    def _tick_step_learning_consolidation(self) -> dict[str, Any]:
        """Step 10: Learning Consolidation — 经验巩固 + 信念提取（Phase 32 enhanced）。

        Phase-LIFE enhancements:
        - 从 _recent_results 构建 ExperienceCandidate → 喂 builder（dream 有料可合成）
        - PredictionGapTracker 记录预测误差（Phase 1: 好奇心自驱动的基础）
        """
        try:
            # 记忆巩固（每5 tick）
            if self._cycle_count % 5 == 0:
                self.memory.consolidate_to_long_term()

            # 信念提取 + Experience 构建 + 预测误差（每10 tick）
            if self._cycle_count % 10 == 0:
                self._extract_beliefs()
                self._extract_beliefs_from_results()
                self._ingest_results_to_experience_builder()
                # PHASE-LIFE Phase 1: 记录 SymbolicReasoner 预测误差
                self._track_prediction_gaps()

            return {
                "step": 10, "name": "learning_consolidation",
                "cycle": self._cycle_count,
            }
        except Exception as e:
            logger.debug("Learning consolidation step failed: %s", e)
            return {"step": 10, "name": "learning_consolidation", "error": str(e)}

    def _track_prediction_gaps(self) -> None:
        """PHASE-LIFE Phase 1: EpistemicDrive — 记录预测误差。

        对每个 goal_result，先用 SymbolicReasoner.predict() → expected，
        然后对比 actual outcome → gap。gap 是 OCOS 的好奇心信号。

        懒加载 PredictionGapTracker（第一次调用时创建），放在 self 上复用。
        """
        results = list(getattr(self, "_recent_results", []) or [])
        if not results:
            return

        try:
            from ocos.reasoning.symbolic import SymbolicReasoner
            from ocos.reasoning.curiosity import PredictionGapTracker

            # 懒创建 tracker（必须传 db_path 才能落库，让 MotivationHub 读到）
            if not hasattr(self, "_gap_tracker"):
                db_path = getattr(self, "_db_path", None)
                self._gap_tracker = PredictionGapTracker(db_path=db_path)

            sr = SymbolicReasoner()

            for r in results:
                success = bool(r.get("success", False))
                task_text = str(r.get("description", r.get("task_id", "")))
                agent_type = str(r.get("agent", ""))
                if not task_text or not agent_type:
                    continue

                pred = sr.predict(task_text, agent_type)
                self._gap_tracker.record(
                    task_text=task_text,
                    agent_type=agent_type,
                    predicted_success=pred.expected_success,
                    actual_success=success,
                    confidence=pred.confidence,
                )

            stats = self._gap_tracker.stats()
            if stats["total_gaps"] > 0:
                logger.info(
                    "PHASE-LIFE: gap tracker stats — domains=%d total=%d mean_gap=%.2f",
                    stats["domains"], stats["total_gaps"], stats["mean_gap_all"],
                )
        except Exception as e:
            logger.debug("Prediction gap tracking skipped: %s", e)

    def _ingest_results_to_experience_builder(self) -> int:
        """PHASE-LIFE: 把 _recent_results 喂进 ExperienceBuilder。

        Step 9 (Result Ingest) 把 DAG/认知循环的执行结果写进 _recent_results；
        Step 10 每 10 tick 扫一次，把新条目构建成 ExperienceCandidate 塞进
        builder，同时落 EpisodeStore。这样 dream 周期（每 200 tick）时 builder
        已经积累了足够多 candidate → _synthesize_lessons 能产出 C 类 Lesson。

        Returns:
            本次构建的 ExperienceCandidate 数量。
        """
        agent = getattr(self, "agent", None) or getattr(self, "_agent", None)
        builder = getattr(agent, "_experience_builder", None) if agent else None
        store = getattr(agent, "_episode_store", None) if agent else None
        if builder is None:
            return 0

        try:
            from ocos.memory.experience.models import (
                TraceBundle, ExperienceSource, ExperienceCandidate,
            )
            from ocos.memory.experience.validator import ExperienceValidator
            from ocos.memory.experience.models import ExperienceStatus
            from ocos.memory.episode.models import Episode
        except Exception as e:
            logger.debug("Experience models unavailable: %s", e)
            return 0

        results = list(getattr(self, "_recent_results", []) or [])
        if not results:
            return 0

        ingested = 0
        for r in results:
            try:
                success = bool(r.get("success", False))
                task_desc = str(r.get("description", r.get("task_id", "unknown")))[:200]
                agent_type = str(r.get("agent", "unknown"))[:50]
                output = str(r.get("output", r.get("result", "")))[:500]
                task_id = str(r.get("task_id", ""))[:50] or f"task-{self._cycle_count}-{ingested}"
                goal_id = str(r.get("goal_id", task_id))[:100]

                # PHASE-LIFE: 字段对齐 LessonsSynthesizer 的读取预期
                #   goal_context['goal_id'] → _group_by_goal 的 goal_ref
                #   goal_context 其他 keys   → _ctx_keys 做上下文聚类
                #   action_result['action'] → _action_str 提取动作
                trace_bundle = TraceBundle(
                    observation={
                        "task": task_desc,
                        "agent_type": agent_type,
                        "output": output[:100],
                    },
                    reasoning_trace_id=f"step10-auto-{self._cycle_count}",
                    decision_trace_id=f"step10-auto-{self._cycle_count}",
                    action_result={
                        "action": agent_type,       # synthesizer 读 action_result['action']
                        "type": "dag_execution" if r.get("task_id") else "cognitive_loop",
                        "result": output,
                    },
                    outcome={
                        "success": success,
                        "source": "step10_auto_ingest",
                        "cycle": self._cycle_count,
                        "agent_type": agent_type,
                    },
                    goal_context={
                        "goal_id": goal_id,          # synthesizer 读 goal_context['goal_id']
                        "agent_type": agent_type,
                        "success": success,
                    },
                )

                # 用 validator 判断 COMPLETE/INCOMPLETE（和 builder.build() 同逻辑）
                complete, _missing = ExperienceValidator.required_fields_present(trace_bundle)
                status = ExperienceStatus.COMPLETE if complete else ExperienceStatus.INCOMPLETE

                candidate = ExperienceCandidate.create(
                    trace_bundle=trace_bundle,
                    source=ExperienceSource.DECISION,
                    context={
                        "agent_id": getattr(agent, "agent_id", "?"),
                        "phase": "step10_learning_consolidation",
                        "cycle": self._cycle_count,
                        "task_id": r.get("task_id", ""),
                    },
                    status=status,
                )

                # 塞 builder — dream 时 _synthesize_lessons 能消费
                builder._candidates.append(candidate)
                ingested += 1

                # 同时落 EpisodeStore（如果有的话）
                if store is not None:
                    try:
                        episode = Episode.from_candidate(
                            experience_id=candidate.id,
                            context=candidate.context,
                            goal=task_desc,
                            decision=f"step10_auto success={success}",
                            action="dag_execution" if r.get("task_id") else "cognitive_loop",
                            outcome={"success": success},
                            source="experience",
                            tags=["auto_ingest", "step10", agent_type],
                        )
                        store.save(episode)
                    except Exception as se:
                        logger.debug("Episode save skipped: %s", se)

            except Exception as e:
                logger.debug("ExperienceCandidate ingestion failed: %s", e)
                continue

        if ingested:
            logger.info(
                "PHASE-LIFE: ingested %d results into ExperienceBuilder "
                "(total=%d)", ingested, len(builder._candidates),
            )
        return ingested

    # ── 原有辅助方法 ────────────────────────────────────────────────────────

    def _homeostasis_check(self) -> None:
        """自我调节检查。"""
        # Phase 35: 使用 CognitiveAttentionController 检查疲劳
        if self.attention is not None and hasattr(self.attention, 'fatigue') and self.attention.fatigue > 0.9:
            self.cortex.sleep()
            logger.info("Homeostasis: entering sleep mode.")

        if self.cortex.needs_intervention():
            self.cortex.emergency_activate()
            logger.warning("Homeostasis: emergency activation triggered.")

    def _persist_working_memory(self) -> None:
        """Phase 21: 将 MemoryConsolidator 的工作记忆保存到 SQLiteWorkingMemory。"""
        if self._wm_store is None:
            return
        try:
            self._wm_store.store("wm:working", {
                "items": [
                    {"content": m.content, "importance": m.importance,
                     "frequency": m.frequency, "tags": m.tags}
                    for m in self.memory.get_working_items()
                ],
            })
        except Exception as e:
            logger.debug("WorkingMemory persist skipped: %s", e)

    def _restore_working_memory(self) -> None:
        """Phase 21: 从 SQLiteWorkingMemory 恢复工作记忆。"""
        if self._wm_store is None:
            return
        try:
            data = self._wm_store.load("wm:working")
            if not data or not data.get("items"):
                return
            restored = 0
            for item_data in data["items"]:
                self.memory.add_to_working(
                    content=item_data.get("content", ""),
                    importance=item_data.get("importance", 0.5),
                    tags=item_data.get("tags", []),
                )
                restored += 1
            if restored > 0:
                logger.info("Phase 34B: Restored %d working memory items — cognitive continuity confirmed", restored)
        except Exception as e:
            logger.debug("WorkingMemory restore skipped: %s", e)

    def _record_episode_from_result(self, result: dict[str, Any]) -> None:
        """Phase 34C: 将执行结果记录为 MemoryHub Episode。

        Result → Episode 是长期学习的第一个转换步骤。
        后续 Pattern → Knowledge → Belief 由 MemoryHub 内部 pipeline 处理。
        """
        if self._memory_hub is None or not self._memory_hub.is_initialized():
            return
        try:
            import uuid
            from datetime import datetime, timezone
            from ocos.memory.episode.models import Episode, EpisodeStatus

            episode = Episode(
                id=f"EPI-{uuid.uuid4().hex[:12]}",
                experience_id=result.get("task_id", f"EXP-{uuid.uuid4().hex[:8]}"),
                created_at=datetime.now(timezone.utc),
                session_id=f"tick_{self._cycle_count}",
                context={
                    "agent": result.get("agent", "?"),
                    "description": result.get("description", ""),
                    "success": result.get("success", False),
                    "output_excerpt": result.get("output", "")[:300],
                },
                goal=result.get("description", "")[:200],
                # UX-F2: decision 携带真实输出（此前是常量 "execute"，记忆里查不到结果）
                decision=str(result.get("output", ""))[:400],
                action=f"{result.get('agent', 'agent')}.execute",
                outcome={
                    "success": result.get("success", False),
                    "cycle": self._cycle_count,
                },
                # FIX: condition 应该是"任务上下文"而非 tick 序号。
                # tick@N 让每次 tick 都是唯一分组 → PatternExtractor 永远组不出 ≥min_samples 的模式。
                # 改成 agent+success — 同类任务重复出现时自然聚合.
                condition=(
                    f"agent={result.get('agent', 'unknown')}, "
                    f"success={str(result.get('success', False)).lower()}"
                ),
                significance_score=0.6 if result.get("success") else 0.3,
                evaluation_trace={"source": "step9_ingest", "cycle": self._cycle_count},
                source="decision",
                status=EpisodeStatus.ACTIVE,
                tags=[result.get("agent", "?"), result.get("task_id", "")],
            )
            self._memory_hub.episode.save(episode)
        except Exception as e:
            logger.debug("Episode recording skipped: %s", e)

    def _sleep_tick(self) -> dict[str, Any]:
        """休眠周期 — 巩固记忆、信念衰减、持久化工作记忆。"""
        self.memory.consolidate_to_long_term()
        self.beliefs.decay_all(rate=0.02)
        # P1.4 (AGI 计划): 陈旧低质信念淘汰（低置信 + 长期未检索）
        try:
            self.beliefs.prune_stale()
        except Exception:
            pass
        self.experiences.replay_important(count=2)
        # Phase 21: Persist working memory during sleep
        self._persist_working_memory()
        return {
            "status": "sleeping",
            "cycle": self._cycle_count,
            "cortex_mode": "SLEEPING",
        }

    def _emergency_tick(self) -> dict[str, Any]:
        """紧急周期 — 只做最关键的维护。"""
        self.memory.consolidate_to_long_term()
        return {
            "status": "emergency",
            "cycle": self._cycle_count,
            "cortex_mode": "EMERGENCY",
        }

    def _extract_beliefs(self) -> None:
        """从经验中提炼信念。"""
        important = self.experiences.replay_important(count=3)
        count = 0
        for exp in important:
            # S2.14 (白皮书 P2): ExperienceStore.record 写入的 outcome
            # 恒为 "completed"（:1411），原判定集合不含它 → 每 10 tick 的
            # 信念提取恒空转。补齐成功语义的等价值。
            if exp.outcome in ("success", "great", "good", "completed"):
                self.beliefs.add(
                    statement=f"当{exp.situation}时, {exp.action}有效",
                    confidence=0.6 + exp.importance * 0.3,
                )
                self.knowledge.add(
                    subject=exp.situation,
                    predicate="effective_action",
                    object=exp.action,
                    confidence=exp.importance,
                    source="experience",
                )
                count += 1
        # P0.3 (AGI 计划): 学习产物可观测 — 产出打点（未装配监控时静默 no-op）
        if count:
            self._record_belief_metric(count, "experience")

    def _extract_beliefs_from_results(self) -> int:
        """Phase 32-B: 从 _recent_results 模式提取 Belief。

        提取规则:
          1. 最近 N 条全部成功 → "goal execution is achievable"
          2. 同一 agent 3+ 次 → "agent X is reliable"
          3. 同一 task fingerprint 3+ 次 → "tasks like X are common"
        """
        results = self._recent_results[:]  # cursor-preserved 快照
        if len(results) < 3:
            return 0

        from collections import Counter
        from ocos.agent.belief_system import BeliefSource
        count = 0

        # 模式0: 全量成功率（最近3+条）
        all_ok = sum(1 for r in results if r.get("success")) / len(results)
        if all_ok == 1.0:
            self.beliefs.add(
                statement="recent execution chain completed with 100% success rate",
                confidence=0.5 + 0.1 * min(len(results), 5),
                source=BeliefSource.CONSOLIDATION,
            )
            count += 1

        # 模式1: agent 可靠性
        agent_ok: Counter[str] = Counter()
        agent_total: Counter[str] = Counter()
        for r in results:
            agent = r.get("agent", "?")
            agent_total[agent] += 1
            if r.get("success"):
                agent_ok[agent] += 1

        for agent, total in agent_total.items():
            if total >= 3:
                rate = agent_ok[agent] / total
                if rate >= 0.8:
                    self.beliefs.add(
                        statement=f"{agent} agent consistently produces reliable results",
                        confidence=0.5 + 0.3 * rate,
                        source=BeliefSource.CONSOLIDATION,
                    )
                    count += 1

        # 模式2: task 类型常见性
        desc_fp: Counter[str] = Counter()
        for r in results:
            d = r.get("description", "")
            fp = d[:6] if len(d) >= 6 else d
            desc_fp[fp] += 1

        for fp, n in desc_fp.items():
            if n >= 3:
                self.beliefs.add(
                    statement=f"tasks similar to '{fp}' appear frequently ({n}x)",
                    confidence=0.3 + 0.1 * min(n, 5),
                    source=BeliefSource.CONSOLIDATION,
                )
                count += 1

        # P0.3 (AGI 计划): 学习产物可观测 — consolidation 来源打点
        if count:
            self._record_belief_metric(count, "consolidation")
        return count

    def _record_belief_metric(self, count: int, source: str) -> None:
        """P0.3: 信念产出计数打点（S3.5 全局指标钩子；未装配时静默 no-op）。"""
        try:
            from ocos.monitoring.manager import record_global
            record_global("belief_created", float(count),
                          labels={"source": source})
        except Exception:
            pass

    # ── P1.1 (AGI 计划): 学习产物检索 ────────────────────────────────────

    def learning_artifacts(
        self,
        description: str,
        limit: int = 5,
        min_confidence: float = 0.6,
    ) -> list[dict[str, Any]]:
        """聚合检索决策可用学习产物（beliefs + knowledge + skills + reflection + failure_lessons）。
          - beliefs: 置信度 >= min_confidence 的已持有信念，按与描述的关键
            词重叠度排序（重叠越多越相关），取 top-k。
          - knowledge: 全文 search(描述) 命中 + 置信度过滤。
        每项含 artifact_id（belief.statement 或 triple.id）——ER-2 归因用。
        无匹配时返回空列表（决策侧据此走"无经验注入"基线路径）。
        """
        artifacts: list[dict[str, Any]] = []

        def _overlap(statement: str, desc: str) -> int:
            # 描述 2-gram 与语句的包含重叠计数（中文可用；英文按词）
            if not desc:
                return 0
            grams = {desc[i:i + 2] for i in range(len(desc) - 1)}
            grams = {g for g in grams if g.strip()}  # 去除含空白的 gram
            return sum(1 for g in grams if g in statement)

        try:
            for b in self.beliefs.get_held(threshold=min_confidence):
                statement = getattr(b, "statement", "") or ""
                score = _overlap(statement, description)
                if score > 0:
                    artifacts.append({
                        "artifact_id": getattr(b, "id", None) or statement,
                        "type": "belief",
                        "text": statement,
                        "confidence": float(getattr(b, "confidence", 0.0)),
                        "score": score,
                    })
        except Exception:
            pass

        try:
            for t in self.knowledge.search(description[:30]):
                if t.confidence < min_confidence:
                    continue
                artifacts.append({
                    "artifact_id": t.id or f"{t.subject}:{t.predicate}",
                    "type": "knowledge",
                    "text": f"{t.subject} {t.predicate} {t.object}",
                    "confidence": float(t.confidence),
                    "score": 1,
                })
        except Exception:
            pass

        # P4.2 (AGI 计划): 技能复用 — 已提交技能按名称/描述与任务描述重叠
        # 检索，type="skill" 且 score 权重高于信念（技能 > 信念 > 知识）。
        # 技能来自 grow_skills_from_episodes 生命周期（四段治理后提交）。
        try:
            registry = getattr(getattr(self, "agent", None),
                               "_skill_registry", None)
            if registry is not None:
                for s in registry.list_skills():
                    hay = f"{s.name} {s.description}"
                    if _overlap(hay, description) > 0 or s.name in description:
                        artifacts.append({
                            "artifact_id": f"skill:{s.id}",
                            "type": "skill",
                            "text": f"技能[{s.name}]: {s.description}"[:120],
                            "confidence": 0.9,  # 已提交技能 = 高置信可复用
                            "score": 3,
                        })
        except Exception:
            pass

        # P3.2 (AGI 计划): 反思回流 — 最近反思的建设性结论并入注入面
        # （仅取 insights 文本，作为 type="reflection" artifact；无反思或
        #  反思为空则跳过，不伪造）
        try:
            agent = getattr(self, "agent", None)
            last_ref = getattr(agent, "_last_reflection", None)
            insights = getattr(last_ref, "insights", None) or ()
            if insights:
                for i, insight in enumerate(insights[:2]):
                    artifacts.append({
                        "artifact_id": f"reflection:{i}",
                        "type": "reflection",
                        "text": str(insight)[:120],
                        "confidence": 0.7,  # 反思默认视为可用参考（成功侧）
                        "score": 1,
                    })
        except Exception:
            pass

        # P0-D (2026-09-10): Failure Lesson 主动注入 — 近 7 天 sql_schema_mismatch
        # / non_retryable failure lessons 作为 type="failure_lesson" 注入决策 prompt。
        # 这是打通 Lesson → Recall → Decision 管道的关键改动。之前 BV2 失败
        # 证实: learning_artifacts 只返回 beliefs+knowledge+skills+reflection，
        # 不返回 failure lessons，导致普通 goal 无法读到之前的 SQL 失败经验。
        try:
            self._inject_failure_lessons(artifacts, description)
        except Exception:
            pass

        artifacts.sort(key=lambda a: (a["score"], a["confidence"]),
                       reverse=True)
        return artifacts[:limit]

    # ── P2 (2026-09-11): failure_signature — 精确检索辅助 ────────────────

    @staticmethod
    def _lookup_failure_by_signature(db_path: str | None,
                                     description: str,
                                     days: int = 7) -> list[dict]:
        """P2: 用 failure_signature 精确查同目标同因 failure lessons。

        优先用 failure_signature（normalized_goal + cause）精确匹配；
        无签名时 fallback 到 LIKE 模糊匹配（兼容历史 lessons）。

        返回简化的 lesson 字典列表（含 rowid, cause, hypothesis）。
        """
        import sqlite3 as _sqlite3
        from datetime import datetime, timezone as _tz, timedelta as _td

        if not db_path:
            return []
        try:
            since = (datetime.now(_tz.utc) - _td(days=days)).isoformat()
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row

            norm = _normalize_goal_for_signature(description)
            # 策略 1: 精确签名匹配（新 lessons 有 signature）
            rows = conn.execute(
                "SELECT rowid, tags, context, substr(decision,1,200) as d "
                "FROM episodes "
                "WHERE action='failure_lesson' "
                "AND created_at >= ? "
                "AND context LIKE ? "
                "ORDER BY rowid DESC LIMIT 10",
                (since, f'%failure_signature": "{norm}|%'),
            ).fetchall()
            if not rows:
                # 策略 2: LIKE fallback（历史 lessons 无 signature）
                key = (description or "")[:30]
                rows = conn.execute(
                    "SELECT rowid, tags, context, substr(decision,1,200) as d "
                    "FROM episodes "
                    "WHERE action='failure_lesson' "
                    "AND goal LIKE ? "
                    "AND created_at >= ? "
                    "ORDER BY rowid DESC LIMIT 10",
                    (f"%{key}%", since),
                ).fetchall()
            conn.close()
        except Exception:
            return []

        result = []
        for r in rows:
            cause = None
            try:
                tags = json.loads(r["tags"] or "[]")
            except Exception:
                tags = []
            for t in tags:
                if t in ("sql_schema_mismatch", "dependency_missing",
                         "tool_unavailable", "permission_denied"):
                    cause = t
                    break
            if cause is None:
                continue
            result.append({
                "rowid": r["rowid"],
                "cause": cause,
                "text": (r["d"] or "")[:150],
            })
        return result

    # ── P0-D (2026-09-10): Failure Lesson 主动注入 ─────────────────────

    def _inject_failure_lessons(self, artifacts: list[dict],
                                description: str) -> None:
        """P0-D: 把近 7 天 failure lessons 注入 learning_artifacts。

        BV2 失败证实: learning_artifacts 只返回 beliefs+knowledge+skills
        + reflection，不返回 failure lessons → 普通 goal 读不到之前的 SQL
        schema mismatch 经验 → 继续盲目幻觉 SQL。

        这里只注入:
          - source='lesson' 且 tags 含 sql_schema_mismatch / dependency_missing /
            tool_unavailable / permission_denied（都是"值得 recall 的失败"）
          - 近 7 天内
          - 与 description 有目标重叠（或无重叠但 sql_schema_mismatch 是通用经验）

        不注入答案 — 只注入事实，让 LLM 自己决定是否改变策略。
        """
        import sqlite3 as _sqlite3
        from datetime import datetime, timezone as _tz, timedelta

        db_path = getattr(self, "_db_path", None) or getattr(
            getattr(self, "agent", None), "db_path", None)
        if not db_path:
            return
        try:
            since = (datetime.now(_tz.utc) - timedelta(days=7)).isoformat()
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row
            rows = conn.execute(
                "SELECT rowid, tags, substr(decision,1,400) as d, goal, created_at "
                "FROM episodes "
                "WHERE action='failure_lesson' AND created_at >= ? "
                "ORDER BY rowid DESC LIMIT 10",
                (since,),
            ).fetchall()
            conn.close()
        except Exception:
            return

        _RECALLABLE_CAUSES = frozenset({
            "sql_schema_mismatch", "dependency_missing",
            "tool_unavailable", "permission_denied",
        })
        for r in rows:
            try:
                tags = json.loads(r["tags"] or "[]")
            except Exception:
                tags = []
            cause = None
            for t in tags:
                if t in _RECALLABLE_CAUSES:
                    cause = t
                    break
            if cause is None:
                continue

            text = (r["d"] or "").strip()
            if not text:
                continue
            # 与当前任务描述的目标重叠度（sql_schema_mismatch 通用，低阈值也注入）
            goal_match = (r["goal"] or "") and any(
                g.strip() in description[:300]
                for g in (r["goal"] or "").split("、")[:3]
                if g.strip()
            )
            # sql_schema_mismatch 是跨任务通用经验 — 任何涉及 DB/SQL 的任务都该看
            sql_related = any(kw in description.lower()
                              for kw in ("sql", "sqlite", "episodes", "数据库", "schema", "表"))
            if not goal_match and not sql_related and cause != "sql_schema_mismatch":
                continue

            # 简短摘要（hypothesis 已含关键信息）
            artifacts.append({
                "artifact_id": f"lesson:{r['rowid']}",
                "type": "failure_lesson",
                "text": text[:150],
                "confidence": 0.95,  # FailureDiagnoser 确定性分类 = 高置信
                "score": 2,  # 低于 skill(3) 但高于 belief(通常 <2)
            })

    # ── P0-C (2026-09-10): Schema Provider — DB schema 注入决策上下文 ──────

    def _get_db_schema_context(self, db_path: str | None = None) -> str:
        """P0-C: 目标 DB 的 episodes 表列名摘要。

        只给列名和类型，不注入 PRAGMA 或修复建议 — 让 LLM 自己决定。
        这是消灭 SQL 幻觉（no such column: content / artifact）的根因修复。

        无 DB / 查询失败 → ""（优雅降级）。
        """
        import sqlite3 as _sqlite3

        path = db_path or getattr(self, "_db_path", None)
        if not path:
            return ""
        try:
            conn = _sqlite3.connect(path)
            cols = conn.execute(
                "PRAGMA table_info(episodes)"
            ).fetchall()
            conn.close()
        except Exception:
            return ""
        if not cols:
            return ""
        col_lines = [
            f"  - {c[1]} ({c[2]})" for c in cols  # (cid, name, type)
        ]
        return (
            "【DB Schema】episodes 表真实列结构（查询前请据此构造 SQL）:\n"
            + "\n".join(col_lines)
        )

    def get_stability_report(self) -> dict[str, Any]:
        """Phase 34D: 运行稳定性报告。

        包含:
          - Tick 延迟分布 (p50/p95/p99)
          - 错误数
          - 运行时长
          - 记忆/信念增长趋势
          - Cognitive Drift 检测
        """
        import statistics

        with self._lock:
            uptime = time.time() - self._boot_time if self._boot_time else 0
            latencies = list(self._tick_latencies)

            p50 = statistics.median(latencies) if latencies else 0
            p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0
            p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0

            # Memory growth
            wm_size = self.memory.working_count if hasattr(self.memory, "working_count") else 0
            lt_size = self.memory.long_term_count if hasattr(self.memory, "long_term_count") else 0
            belief_count = self.beliefs.belief_count if hasattr(self.beliefs, "belief_count") else 0
            episode_count = self._memory_hub.episode.count() if self._memory_hub and self._memory_hub.is_initialized() else 0

            # Cognitive drift: detect anomalous belief changes
            drift_flags: list[str] = []
            if self._cycle_count > 100 and self._tick_errors / self._cycle_count > 0.1:
                drift_flags.append("high_error_rate")
            if self._boot_time and uptime > 3600 and uptime - self._cycle_count * self._tick_budget > 600:
                drift_flags.append("tick_delay_accumulation")

            return {
                "phase": "34D",
                "uptime_s": round(uptime, 1),
                "cycles": self._cycle_count,
                "tick_latency": {
                    "p50_ms": round(p50 * 1000, 2),
                    "p95_ms": round(p95 * 1000, 2),
                    "p99_ms": round(p99 * 1000, 2),
                    "samples": len(latencies),
                },
                "stability": {
                    "errors": self._tick_errors,
                    "error_rate": round(self._tick_errors / max(self._cycle_count, 1), 4),
                    "drift_flags": drift_flags,
                },
                "memory_growth": {
                    "working_memory": wm_size,
                    "long_term_memory": lt_size,
                    "beliefs": belief_count,
                    "episodes": episode_count,
                },
            }

    def _save_identity_snapshot(self, snapshot_id: str = "runtime_identity",
                                extra: dict[str, Any] | None = None
                                ) -> dict[str, Any] | None:
        """Phase 34E: 保存 Identity Snapshot 用于跨 session 连续性验证。

        snapshot_id 默认 "runtime_identity"（shutdown 路径，boot 时
        _verify_identity_continuity 消费）；周期快照传独立 id +
        extra 成长字段（weekly_identity），两类互不覆盖。
        """
        if self._identity_store is None:
            return None
        try:
            import hashlib

            snapshot = {
                "agent_id": str(self.agent.agent_id) if hasattr(self.agent, "agent_id") else "unknown",
                "cycle": self._cycle_count,
                "memory": {
                    "working_count": self.memory.working_count if hasattr(self.memory, "working_count") else 0,
                    "result_cursor": self._result_cursor,
                    "recent_results": len(self._recent_results),
                },
                "beliefs": self.beliefs.belief_count if hasattr(self.beliefs, "belief_count") else 0,
                "state": self._state.name,
                "version": "1.0-Phase34",
            }
            if extra:
                snapshot.update(extra)
            content = str(sorted(snapshot.items()))
            snapshot["continuity_hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]

            self._identity_store.save_snapshot(snapshot_id, snapshot)
            logger.info("Phase 34E: Identity snapshot saved — id=%s, hash=%s, cycle=%d",
                        snapshot_id, snapshot["continuity_hash"], self._cycle_count)
            return snapshot
        except Exception as e:
            logger.debug("Identity snapshot save skipped: %s", e)
            return None

    def save_weekly_identity_snapshot(self) -> dict[str, Any] | None:
        """周度身份快照（数字生命·自我连续性）。

        此前 identity_snapshots 仅优雅 shutdown 路径写入（L2264 附近），
        而 systemd 下 daemon 从不优雅关闭 → 表恒空，"我是谁"的时间序列
        缺失。改为周键幂等：每 ISO 周首次调用落一份，payload 带成长统计
        （本周完成目标/经历数），与成长叙事周记对齐。保留最近 26 周。
        """
        snap = None
        try:
            import sqlite3
            from datetime import datetime as _dt, timezone as _tz
            now = _dt.now(_tz.utc)
            iso = now.isocalendar()
            week_key = f"{iso[0]}-W{iso[1]:02d}"
            snapshot_id = f"weekly-{week_key}"
            if self._identity_store is not None:
                existing = self._identity_store.load_snapshot(snapshot_id)
                if existing is not None:
                    return None                     # 本周已快照（幂等）
            stats: dict[str, Any] = {"week_key": week_key}
            try:
                conn = sqlite3.connect(
                    f"file:{self._db_path}?mode=ro", uri=True)
                try:
                    start = _dt.fromisocalendar(iso[0], iso[1], 1).replace(
                        hour=0, tzinfo=_tz.utc).isoformat()
                    row = conn.execute(
                        "SELECT COUNT(*) FROM goals WHERE status IN "
                        "('COMPLETED','completed','DONE','done') "
                        "AND updated_at >= ?", (start,)).fetchone()
                    stats["goals_completed_this_week"] = int(row[0] or 0)
                    row = conn.execute(
                        "SELECT COUNT(*) FROM episodes WHERE created_at >= ?",
                        (start,)).fetchone()
                    stats["episodes_this_week"] = int(row[0] or 0)
                finally:
                    conn.close()
            except sqlite3.Error as e:
                logger.debug("weekly snapshot stats degraded: %s", e)
            snap = self._save_identity_snapshot(snapshot_id, extra=stats)
            # 全局保留最近 26 周（save_snapshot 的 keep-10 仅按 id 生效）
            if snap is not None:
                self._identity_store.connection.execute(
                    """DELETE FROM identity_snapshots
                       WHERE snapshot_id LIKE 'weekly-%'
                       AND id NOT IN (SELECT id FROM identity_snapshots
                                      WHERE snapshot_id LIKE 'weekly-%'
                                      ORDER BY id DESC LIMIT 26)""")
                self._identity_store.connection.commit()
        except Exception as e:
            logger.debug("weekly identity snapshot skipped: %s", e)
            return None
        return snap

    def _verify_identity_continuity(self) -> None:
        """Phase 34E: Boot 时验证 Identity Continuity。

        从 IdentityStore 加载上次 shutdown 保存的 snapshot，
        校验 agent_id 一致性和版本兼容性。"""
        if self._identity_store is None:
            return
        try:
            snapshot = self._identity_store.load_snapshot("runtime_identity")
            if snapshot is None:
                logger.info("Phase 34E: No previous identity snapshot — first boot or fresh identity")
                return

            prev_agent_id = snapshot.get("agent_id", "?")
            curr_agent_id = str(self.agent.agent_id) if hasattr(self.agent, "agent_id") else "?"
            prev_cycle = snapshot.get("cycle", 0)
            prev_hash = snapshot.get("continuity_hash", "?")
            prev_version = snapshot.get("version", "?")

            if prev_agent_id != curr_agent_id:
                logger.warning("Phase 34E: Identity mismatch — was %s, now %s", prev_agent_id, curr_agent_id)
                return

            logger.info(
                "Phase 34E: Identity continuity verified — agent=%s, last_cycle=%d, "
                "hash=%s, version=%s, restored WMs=%d",
                curr_agent_id, prev_cycle, prev_hash, prev_version,
                self.memory.working_count if hasattr(self.memory, "working_count") else 0,
            )
        except Exception as e:
            logger.debug("Identity continuity check skipped: %s", e)

    def get_full_status(self) -> dict[str, Any]:
        """获取完整运行时状态。"""
        with self._lock:
            return {
                "runtime_state": self._state.name,
                "agent_status": self.agent.state.status.name,
                "cortex_mode": self.cortex.mode.name,
                "cycle": self._cycle_count,
                "controller": self.controller.get_stats(),
                "memory": self.memory.get_stats(),
                "beliefs": self.beliefs.belief_count,
                "knowledge": self.knowledge.count,
                "experiences": self.experiences.total_count,
            }

    def shutdown(self) -> None:
        """关闭运行时。"""
        with self._lock:
            logger.info("AgentRuntime shutting down...")
            self._state = RuntimeState.SHUTDOWN
            self.cortex.sleep()
            # 最后一次记忆巩固
            self.memory.consolidate_to_long_term()
            # Phase 21: Persist working memory before closing stores
            self._persist_working_memory()
            # Phase 34E: 保存 Identity Snapshot 用于下次 boot 连续性验证
            self._save_identity_snapshot()
            # Phase 21: 关闭持久化层
            if self._identity_store:
                self._identity_store.close()
            if self._goal_store:
                self._goal_store.close()
            if self._memory_hub:
                self._memory_hub.shutdown()
            if self._wm_store:
                self._wm_store.close()
            logger.info("AgentRuntime shutdown complete.")


# ── P2 (2026-09-11): failure_signature — 模块级辅助 ────────────────────

def _normalize_goal_for_signature(text: str) -> str:
    """P2: 把任意 goal 描述归一化为稳定签名片段。

    规则：
      1. 去标点/空白/全角符号
      2. 小写化
      3. 截断到 80 字符（语义足够 + 索引友好）
      4. 兜底: 空串 → "_empty_"

    目的: 同一个"查 episodes 表 source 分布"目标不管怎么描述
    （"episodes source 统计" / "episodes表按source分组"），
    归一化后有机会产生相同或重叠的签名片段，让 LIKE 和精确匹配
    都能工作得更可靠。
    """
    if not text:
        return "_empty_"
    # 1. 去空白
    t = re.sub(r"\s+", "", text)
    # 2. 去常见标点（中英）
    t = re.sub(r"[，。？！,.?!、；;：:（）()「」""''—~…/\\|]", "", t)
    # 3. 小写
    t = t.lower()
    # 4. 截断
    t = t[:80]
    return t or "_empty_"
