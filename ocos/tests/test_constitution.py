"""
A1 Architecture Tests — 宪法规则验证。

验证 ocos/kernel/constitution.py 与 docs/OCOS_CORE_CONSTITUTION.md 的一致性。
所有 8 条不可变规则必须有自动化测试覆盖。
"""

from ocos.kernel.constitution import Constitution, ConstitutionalRule


def test_all_24_constitutional_rules_defined():
    """宪法必须有且仅有 24 条不可变规则（Phase 17.5 + R21-R24）。"""
    rules = Constitution.RULES
    assert len(rules) == 24, f"期望 24 条规则，实际 {len(rules)} 条"
    expected = {
        ConstitutionalRule.DECISION_IS_ONLY_ACTION_SOURCE,
        ConstitutionalRule.EVENT_BUS_IS_ONLY_COMMUNICATION,
        ConstitutionalRule.ALL_INPUTS_MUST_BE_OBSERVED,
        ConstitutionalRule.ALL_TRANSITIONS_MUST_BE_LOGGED,
        ConstitutionalRule.KNOWLEDGE_CHANGES_REQUIRE_GOVERNANCE,
        ConstitutionalRule.EVERY_ACTION_HAS_DECISION,
        ConstitutionalRule.SCHEDULING_MUST_BE_DETERMINISTIC,
        ConstitutionalRule.PLUGIN_CANNOT_CHANGE_SYSTEM_STATE,
        ConstitutionalRule.PLATFORM_800_LINE_LIMIT,
        ConstitutionalRule.KERNEL_NEVER_KNOWS_BUSINESS,
        ConstitutionalRule.RUNTIME_NEVER_KNOWS_KNOWLEDGE,
        ConstitutionalRule.INFORMATION_LIFECYCLE_INVARIANT,
        ConstitutionalRule.INFORMATION_CONTROL_INVARIANT,
        ConstitutionalRule.EXECUTION_REQUIRES_COMMITTED_DECISION,
        ConstitutionalRule.EXECUTION_NOT_MODIFY_DECISION,
        ConstitutionalRule.EXECUTION_MUST_PRODUCE_OBSERVATION,
        ConstitutionalRule.GOAL_WHAT_NOT_HOW,
        ConstitutionalRule.GOAL_LIFETIME_EXCEEDS_DECISION,
        ConstitutionalRule.GOAL_DECISION_ONE_TO_MANY,
        ConstitutionalRule.DECISION_MUST_REFERENCE_GOAL,
        ConstitutionalRule.PROCESS_NOT_OWN_INFORMATION,
        ConstitutionalRule.PROCESS_NOT_CONTROL_LIFECYCLE,
        ConstitutionalRule.PROCESS_NOT_EXECUTE_ACTION,
        ConstitutionalRule.PROCESS_MUST_REFERENCE_EVIDENCE,
    }
    assert set(rules) == expected, f"规则集合不匹配: {set(rules) ^ expected}"


def test_all_rules_have_descriptions():
    """每条规则必须有文字描述。"""
    for rule in ConstitutionalRule:
        desc = Constitution.get_rule_description(rule)
        assert desc and len(desc) > 10, f"规则 {rule.value} 缺少描述"


def test_constitution_version():
    """宪法版本必须合法。"""
    assert Constitution.VERSION == "1.0"


def test_allowed_imports_kernel_can_depend_on_models():
    """Kernel 可以依赖 models（类型定义，非业务逻辑）。"""
    assert Constitution.ALLOWED_IMPORTS.get("ocos.kernel") == ["ocos.models"]


def test_allowed_imports_runtime_can_depend_on_kernel():
    """Runtime 可以依赖 kernel 和 events。"""
    allowed = Constitution.ALLOWED_IMPORTS.get("ocos.runtime", [])
    assert "ocos.kernel" in allowed
    assert "ocos.events" in allowed


def test_allowed_imports_engines_cannot_depend_on_runtime():
    """Engine 不能依赖 runtime。"""
    allowed = Constitution.ALLOWED_IMPORTS.get("ocos.engines", [])
    assert "ocos.runtime" not in allowed


def test_allowed_imports_plugins_cannot_depend_on_runtime():
    """Plugin 不能依赖 runtime。"""
    allowed = Constitution.ALLOWED_IMPORTS.get("ocos.plugins", [])
    assert "ocos.runtime" not in allowed


def test_check_import_allowed_kernel_import_self():
    """Kernel import 自身应该允许。"""
    assert Constitution.check_import_allowed("ocos.kernel", "ocos.kernel")


def test_check_import_allowed_engines_events():
    """engines 可 import events。"""
    assert Constitution.check_import_allowed("ocos.engines", "ocos.events")


def test_check_import_allowed_engines_runtime_blocked():
    """engines 不可 import runtime。"""
    assert not Constitution.check_import_allowed("ocos.engines", "ocos.runtime")


def test_check_import_allowed_plugins_runtime_blocked():
    """plugins 不可 import runtime。"""
    assert not Constitution.check_import_allowed("ocos.plugins", "ocos.runtime")


def test_rule_1_description_decision():
    """Rule 1 描述必须提 Decision 是唯一动作源。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.DECISION_IS_ONLY_ACTION_SOURCE
    )
    assert "Decision" in desc
    assert "Action" in desc


def test_rule_8_description_plugin():
    """Rule 8 描述必须提 Plugin 不可改系统状态。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PLUGIN_CANNOT_CHANGE_SYSTEM_STATE
    )
    assert "Plugin" in desc
    assert "Sandbox" in desc or "Event" in desc or "状态" in desc or "state" in desc.lower()


def test_rule_9_description_platform_800():
    """Rule 9 描述必须提 Platform 800 行限制。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PLATFORM_800_LINE_LIMIT
    )
    assert "800" in desc
    assert "Architecture Review" in desc


def test_rule_10_description_kernel_business():
    """Rule 10 描述必须提 Kernel 不懂业务。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.KERNEL_NEVER_KNOWS_BUSINESS
    )
    assert "Kernel" in desc
    assert "Memory" in desc or "Knowledge" in desc or "Identity" in desc or "Policy" in desc or "Decision" in desc


def test_rule_11_description_runtime():
    """Rule 11 描述必须提 Runtime 不可 import knowledge/platform。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.RUNTIME_NEVER_KNOWS_KNOWLEDGE
    )
    assert "knowledge" in desc or "import" in desc
    assert desc != ""


def test_rule_12_description_lifecycle():
    """Rule 12 描述必须提 Information Lifecycle 八阶段。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.INFORMATION_LIFECYCLE_INVARIANT
    )
    assert "Acquire" in desc and "Decay" in desc and "Archive" in desc
    assert desc != ""


def test_rule_13_description_control():
    """Rule 13 描述必须提 Information 不可控制自身生命周期。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.INFORMATION_CONTROL_INVARIANT
    )
    assert "自行" in desc or "不可" in desc or "not" in desc.lower()
    assert desc != ""


def test_rule_21_description_process_own_information():
    """Rule 21 描述必须提 Process 不拥有 Information。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PROCESS_NOT_OWN_INFORMATION
    )
    assert "Address" in desc or "引用" in desc


def test_rule_22_description_process_control_lifecycle():
    """Rule 22 描述必须提 Process 不控制生命周期。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PROCESS_NOT_CONTROL_LIFECYCLE
    )
    assert "生命周期" in desc or "Lifecycle" in desc


def test_rule_23_description_process_execute_action():
    """Rule 23 描述必须提 Process 不执行 Action。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PROCESS_NOT_EXECUTE_ACTION
    )
    assert "Action" in desc or "execute" in desc


def test_rule_24_description_process_reference_evidence():
    """Rule 24 描述必须提 Process 必须引用 Evidence。"""
    desc = Constitution.get_rule_description(
        ConstitutionalRule.PROCESS_MUST_REFERENCE_EVIDENCE
    )
    assert "input" in desc or "output" in desc or "address" in desc or "引用" in desc
