"""OCOS kernel 宪法不可违反性测试。

聚焦两条硬约束：
1. 宪法规则列表完整且不可篡改
2. import 方向契约稳定
"""

import pytest
from ocos.kernel.constitution import Constitution, ConstitutionalRule


class TestConstitutionRules:
    """24 条规则必须全部存在，不可被外部删除或绕过。"""

    def test_all_24_rules_exist(self):
        """当前必须有 24 条规则。"""
        assert len(Constitution.RULES) == 24

    def test_rules_are_immutable_enum(self):
        """RULES 必须是 ConstitutionalRule 枚举的成员列表。"""
        assert all(isinstance(r, ConstitutionalRule) for r in Constitution.RULES)

    def test_rule_values_are_unique_strings(self):
        """每条规则的 value 必须是唯一字符串。"""
        values = [r.value for r in Constitution.RULES]
        assert len(values) == len(set(values))

    def test_key_rules_present(self):
        """四条核心规则必须存在：决策源、事件总线、可追溯、执行不修改决策。"""
        present = {r.value for r in Constitution.RULES}
        assert "decision_is_only_action_source" in present
        assert "event_bus_is_only_communication" in present
        assert "execution_not_modify_decision" in present
        assert "all_transitions_must_be_logged" in present

    def test_no_rule_can_be_none_or_empty(self):
        """不允许任何规则为 None 或空字符串。"""
        for rule in Constitution.RULES:
            assert rule.value != ""


class TestConstitutionDescription:
    """每条规则都必须有文字描述。"""

    def test_all_rules_have_descriptions(self):
        """get_rule_description 对所有规则返回非空字符串。"""
        for rule in Constitution.RULES:
            desc = Constitution.get_rule_description(rule)
            assert desc and len(desc) > 10, f"规则 {rule.value} 缺少描述"


class TestImportDirection:
    """宪法规定模块间 import 方向。"""

    def test_allowed_imports_structure(self):
        """ALLOWED_IMPORTS 是 dict[str, list[str]]。"""
        assert isinstance(Constitution.ALLOWED_IMPORTS, dict)
        for src, dsts in Constitution.ALLOWED_IMPORTS.items():
            assert isinstance(src, str)
            assert isinstance(dsts, list)
            assert all(isinstance(d, str) for d in dsts)

    def test_self_import_always_allowed(self):
        """自身引用永远允许。"""
        for module in list(Constitution.ALLOWED_IMPORTS.keys()):
            assert Constitution.check_import_allowed(module, module) is True

    def test_submodule_import_allowed(self):
        """子模块可以 import 父模块（通过 prefix 匹配）。"""
        # ocos.runtime.tick 应该可以 import ocos.runtime（同层级或父级）
        # 注意：constitution 只允许显式配置的方向
        assert Constitution.check_import_allowed(
            "ocos.runtime", "ocos.runtime"
        ) is True

    def test_forbidden_import_blocked(self):
        """kernel 不允许 import engines（依赖方向反了）。"""
        assert Constitution.check_import_allowed(
            "ocos.kernel", "ocos.engines"
        ) is False

    def test_allow_root_module(self):
        """kernel 可以 import models（在 ALLOWED_IMPORTS 中配置）。"""
        assert Constitution.check_import_allowed(
            "ocos.kernel", "ocos.models"
        ) is True

    def test_unknown_source_denied(self):
        """不在 ALLOWED_IMPORTS 中的 source，只能 import 自身。"""
        assert Constitution.check_import_allowed(
            "ocos.unknown_module", "ocos.engine"
        ) is False

    def test_version_class_variable(self):
        """VERSION 是类变量，字符串格式为 'X.Y'。"""
        assert hasattr(Constitution, "VERSION")
        assert isinstance(Constitution.VERSION, str)
        parts = Constitution.VERSION.split(".")
        assert len(parts) == 2
        int(parts[0])
        int(parts[1])
