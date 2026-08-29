"""
OCOS Constitution — 硬编码不可变规则。

本文件对应 docs/OCOS_CORE_CONSTITUTION.md 的 19 条不可变规则。
架构测试 (`tests/test_constitution.py`) 自动验证本文件与宪法的一致性。
"""

from __future__ import annotations

import enum
from typing import ClassVar


class ConstitutionalRule(enum.Enum):
    """24 条不可变宪法规则。"""

    # Rule 1: Decision is the only source of Action
    # The system must route all executable actions through Decision.
    DECISION_IS_ONLY_ACTION_SOURCE = "decision_is_only_action_source"

    # Rule 2: Event Bus is the only communication channel
    # No import-based cross-module function calls; all communication via Event Bus.
    EVENT_BUS_IS_ONLY_COMMUNICATION = "event_bus_is_only_communication"

    # Rule 3: All inputs must be explicitly observed
    # No implicit or unregistered observations.
    ALL_INPUTS_MUST_BE_OBSERVED = "all_inputs_must_be_observed"

    # Rule 4: All state transitions must be explicit and logged
    # No side effects without Event Store recording.
    ALL_TRANSITIONS_MUST_BE_LOGGED = "all_transitions_must_be_logged"

    # Rule 5: Knowledge changes require Governance approval
    # Promotion, deprecation, and registry mutations need Governance review.
    KNOWLEDGE_CHANGES_REQUIRE_GOVERNANCE = "knowledge_changes_require_governance"

    # Rule 6: Every Action must have a corresponding Decision
    # Actions cannot exist without a Decision root cause.
    EVERY_ACTION_HAS_DECISION = "every_action_has_decision"

    # Rule 7: Composability — engine scheduling must be deterministic
    # Given same initial state + same events, schedules produce same order.
    SCHEDULING_MUST_BE_DETERMINISTIC = "scheduling_must_be_deterministic"

    # Rule 8: Plugin cannot change system state directly
    # Plugins operate in Sandbox, communicate via Events, cannot mutate core state.
    PLUGIN_CANNOT_CHANGE_SYSTEM_STATE = "plugin_cannot_change_system_state"

    # Rule 9: Platform component 800-line hard limit
    # Any Platform module > 800 lines must undergo Architecture Review and split by responsibility.
    PLATFORM_800_LINE_LIMIT = "platform_800_line_limit"

    # Rule 10: Kernel never knows business
    # Kernel must NOT contain Memory, Knowledge, Identity, Policy, Decision. Kernel does not know business logic.
    KERNEL_NEVER_KNOWS_BUSINESS = "kernel_never_knows_business"

    # Rule 11: Runtime never knows Knowledge/Plugin
    # Runtime must NOT import knowledge.*, platform.*, engines.*, plugins.*. Runtime only decides "what to run now".
    RUNTIME_NEVER_KNOWS_KNOWLEDGE = "runtime_never_knows_knowledge"

    # Rule 12: Information Lifecycle Invariant
    # All Information state transitions must follow the Theory lifecycle: CREATED → VALIDATED → REFERENCED → DEPRECATED → ARCHIVED.
    INFORMATION_LIFECYCLE_INVARIANT = "information_lifecycle_invariant"

    # Rule 13: Information Control Invariant
    # Information must NOT archive/delete/promote/forget itself. Lifecycle transitions are controlled
    # by Governance, Lifecycle Engine, Promotion Engine, Forgetting Engine — never by the Information itself.
    INFORMATION_CONTROL_INVARIANT = "information_control_invariant"

    # Rule 14: Execution requires committed Decision
    # Every Execution must reference a committed Decision. No Decision → no valid Execution.
    EXECUTION_REQUIRES_COMMITTED_DECISION = "execution_requires_committed_decision"

    # Rule 15: Execution shall not modify Decision
    # Execution reads the Decision's selected option but must not alter the Decision's status or content.
    EXECUTION_NOT_MODIFY_DECISION = "execution_not_modify_decision"

    # Rule 16: Execution must produce Observation
    # Every Execution must produce at least one Observation. No Observation means no actual execution.
    EXECUTION_MUST_PRODUCE_OBSERVATION = "execution_must_produce_observation"

    # ── Goal (Phase 17.2 — Goal Theory → Code Alignment) ───────

    # Rule 17: Goal only answers What, not How
    # Goal must describe the desired end state, not the means to achieve it.
    GOAL_WHAT_NOT_HOW = "goal_what_not_how"

    # Rule 18: Goal lifetime exceeds any Decision
    # A failed Decision does not terminate its originating Goal.
    GOAL_LIFETIME_EXCEEDS_DECISION = "goal_lifetime_exceeds_decision"

    # Rule 19: Goal ↔ Decision is one-to-many
    # A Goal may generate multiple Decisions (serial or parallel). Failed Decisions do not terminate the Goal.
    GOAL_DECISION_ONE_TO_MANY = "goal_decision_one_to_many"

    # Rule 20: Decision must reference a Goal
    # No Goal → no valid Decision. Every Decision must reference its originating Goal.
    DECISION_MUST_REFERENCE_GOAL = "decision_must_reference_goal"

    # ── Process (Phase 17.5 — Process Theory → Code Alignment) ────

    # Rule 21: Process does NOT own Information
    # TransformProcess shall use Address references, never embed Information content.
    PROCESS_NOT_OWN_INFORMATION = "process_not_own_information"

    # Rule 22: Process does NOT control Lifecycle
    # Process must not call state.transition_to() or alter Information lifecycle.
    PROCESS_NOT_CONTROL_LIFECYCLE = "process_not_control_lifecycle"

    # Rule 23: Process does NOT execute Action
    # Process must not contain execute() or trigger external actions directly.
    PROCESS_NOT_EXECUTE_ACTION = "process_not_execute_action"

    # Rule 24: Process must reference Evidence
    # Every TransformProcess must have at least one input_address or output_address.
    PROCESS_MUST_REFERENCE_EVIDENCE = "process_must_reference_evidence"


class Constitution:
    """运行时宪法约束检查器。"""

    VERSION: ClassVar[str] = "1.0"
    RULES: ClassVar[list[ConstitutionalRule]] = list(ConstitutionalRule)

    # 模块间允许的 import 方向（src -> dst 为允许）
    ALLOWED_IMPORTS: ClassVar[dict[str, list[str]]] = {
        "ocos.kernel": ["ocos.models"],  # kernel 依赖模型类型定义（非业务逻辑）
        "ocos.events": ["ocos.kernel"],
        "ocos.runtime": ["ocos.kernel", "ocos.events"],
        "ocos.models": ["ocos.kernel"],
        "ocos.platform": ["ocos.kernel", "ocos.events"],
        "ocos.engines": ["ocos.kernel", "ocos.events", "ocos.models"],
        "ocos.plugins": ["ocos.kernel", "ocos.events", "ocos.engines"],
    }

    @classmethod
    def check_import_allowed(cls, source_module: str, target_module: str) -> bool:
        """检查 import 方向是否被宪法允许。"""
        # 自身引用允许
        if source_module == target_module:
            return True
        # 向上兼容：如果 source_module 包含在允许列表中作为目标之一
        # 例如 ocos.kernel 可以 import ocos.kernel.abi
        if target_module.startswith(source_module + "."):
            return True
        allowed_targets = cls.ALLOWED_IMPORTS.get(source_module, [])
        if target_module in allowed_targets:
            return True
        # 允许向下包含（如 ocos.engines.reasoning 可 import ocos.kernel）
        for allowed in allowed_targets:
            if target_module.startswith(allowed + ".") or target_module == allowed:
                return True
        return False

    @classmethod
    def get_rule_description(cls, rule: ConstitutionalRule) -> str:
        """返回规则的文字描述。"""
        descriptions = {
            ConstitutionalRule.DECISION_IS_ONLY_ACTION_SOURCE:
                "Decision 是系统唯一能产生 Action 的组件。Engine 和 Plugin 不得绕过 Decision 直接执行操作。",
            ConstitutionalRule.EVENT_BUS_IS_ONLY_COMMUNICATION:
                "Event Bus 是模块间唯一通信通道。禁止跨模块直接 import 调用。",
            ConstitutionalRule.ALL_INPUTS_MUST_BE_OBSERVED:
                "所有外部输入必须通过 Observation 通道注册和记录。禁止未注册的隐式输入。",
            ConstitutionalRule.ALL_TRANSITIONS_MUST_BE_LOGGED:
                "所有状态变更必须显式记录到 Event Store。禁止产生未记录的副作用。",
            ConstitutionalRule.KNOWLEDGE_CHANGES_REQUIRE_GOVERNANCE:
                "Knowlege 的提升、弃用、删除必须经过 Governance 审批。",
            ConstitutionalRule.EVERY_ACTION_HAS_DECISION:
                "每个 Action 必须有对应的 Decision 作为根因。Action 不可凭空产生。",
            ConstitutionalRule.SCHEDULING_MUST_BE_DETERMINISTIC:
                "相同初始状态 + 相同事件序列必须产生相同调度顺序。",
            ConstitutionalRule.PLUGIN_CANNOT_CHANGE_SYSTEM_STATE:
                "Plugin 运行在 Sandbox 中，通过 Event 通信，禁止直接修改核心状态。",
            ConstitutionalRule.PLATFORM_800_LINE_LIMIT:
                "Platform 组件超 800 行必须触发 Architecture Review 并按职责拆分。禁止产生'什么都管一点'的万能模块。",
            ConstitutionalRule.KERNEL_NEVER_KNOWS_BUSINESS:
                "Kernel 永不包含 Memory、Knowledge、Identity、Policy、Decision。Kernel 不懂业务逻辑。任何想放进 Kernel 的新内容，先问'这是 ABI 契约还是业务逻辑'。",
            ConstitutionalRule.RUNTIME_NEVER_KNOWS_KNOWLEDGE:
                "Runtime 永不 import knowledge.*、platform.*、engines.*、plugins.*。Runtime 只负责'现在应该运行什么'。",
            ConstitutionalRule.INFORMATION_LIFECYCLE_INVARIANT:
                "所有 Information 必须遵循 Acquire → Validate → Retain → Access → Transform → Decay → Archive → Delete 生命周期。任何 Information 不可绕过该生命周期。",
            ConstitutionalRule.INFORMATION_CONTROL_INVARIANT:
                "Information 不拥有自身生命周期控制权。Information 不可自行 Archive、Delete、Promote、Forget。生命周期变更由 Governance、Lifecycle Engine、Promotion Engine、Forgetting Engine 决定。",
            ConstitutionalRule.EXECUTION_REQUIRES_COMMITTED_DECISION:
                "Execution 必须引用一个已提交的 Decision。未经过 Decision 的 Execution 为非法。",
            ConstitutionalRule.EXECUTION_NOT_MODIFY_DECISION:
                "Execution 不得修改 Decision 的状态或内容。Execution 只读取，不改写。",
            ConstitutionalRule.EXECUTION_MUST_PRODUCE_OBSERVATION:
                "Execution 必须产生至少一个 Observation。无 Observation 意味着未真正执行。",
            ConstitutionalRule.GOAL_WHAT_NOT_HOW:
                "Goal 只描述想达到什么状态（What），不描述怎么做到（How）。实现方式属于 Decision 和 Planning 的职责。",
            ConstitutionalRule.GOAL_LIFETIME_EXCEEDS_DECISION:
                "Goal 的生命周期长于任何调用了它的 Decision。一次 Decision 的失败不终止其来源 Goal。",
            ConstitutionalRule.GOAL_DECISION_ONE_TO_MANY:
                "一个 Goal 可以产生多个 Decision（串行或并行）。失败的 Decision 不终止 Goal。Goal 不持有 Decision 列表。",
            ConstitutionalRule.DECISION_MUST_REFERENCE_GOAL:
                "没有 Goal 就没有合法 Decision。每个 Decision 必须引用其来源 Goal。缺少 goal_id 的 Decision 为非法。",
            ConstitutionalRule.PROCESS_NOT_OWN_INFORMATION:
                "Process 不拥有 Information。TransformProcess 必须使用 UniversalAddress 引用，不得嵌入实际数据内容。",
            ConstitutionalRule.PROCESS_NOT_CONTROL_LIFECYCLE:
                "Process 不控制 Information 生命周期。Process 不得调用 state.transition_to() 或修改 Information 状态。生命周期由 Lifecycle Engine 管理。",
            ConstitutionalRule.PROCESS_NOT_EXECUTE_ACTION:
                "Process 不执行 Action。Process 不得包含 execute() 方法或直接触发外部操作。Action 属于 Execution 层。",
            ConstitutionalRule.PROCESS_MUST_REFERENCE_EVIDENCE:
                "Process 必须引用 Evidence。每个 TransformProcess 必须包含至少一个 input_address 或 output_address，不可为空引用。",
        }
        return descriptions.get(rule, "")

    # --- 运行时验证钩子 ---

    @staticmethod
    def validate_event_bus_communication() -> bool:
        """当前是否只有 Event Bus 通信。

        GAP-P3-5 (C.1): 架构测试占位 — 真实校验由
        ocos/tests/test_no_direct_store_access.py /
        test_import_rules.py 的 import 规则承担, 此处仅保留
        接口供宪法审计调用。
        """
        return True

    @staticmethod
    def validate_no_direct_imports() -> bool:
        """当前是否没有违反依赖规则的 import（架构测试占位）。"""
        return True
