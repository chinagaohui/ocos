"""Phase 40: PreferenceModel — 双层偏好模型。

关键区分:
    User Preference       — 用户偏好，从行为/反馈推断
    Operational Preference — OCOS 操作偏好，运行效率权衡

User Preference ≠ User Value（用户价值在 Identity.anchor，不在此）
Operational Preference ≠ Self Judgement（不是价值判断，是效率权衡）

禁止:
    - OCOS 操作偏好替代用户偏好
    - 偏好绕过用户意图
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.self.self_types import PreferenceEntry, PreferenceType


@dataclass
class PreferenceModel:
    """SelfModel 的双层偏好管理。

    User:
        从用户行为/反馈中推断（不是替代用户价值）
        例如: "详细解释"、"先给方案再执行"、"中文回复"

    Operational:
        OCOS 自身的运行效率权衡（不是价值判断）
        例如: "优先本地计算"、"批处理优于单条请求"
    """

    user_preferences: dict[str, PreferenceEntry] = field(default_factory=dict)
    """用户偏好。"""

    operational_preferences: dict[str, PreferenceEntry] = field(default_factory=dict)
    """操作偏好。"""

    # ── 查询 ──

    @property
    def user_count(self) -> int:
        return len(self.user_preferences)

    @property
    def operational_count(self) -> int:
        return len(self.operational_preferences)

    def get_user_pref(self, key: str) -> Optional[str]:
        entry = self.user_preferences.get(key)
        return entry.value if entry else None

    def get_operational_pref(self, key: str) -> Optional[str]:
        entry = self.operational_preferences.get(key)
        return entry.value if entry else None

    def get_all_user_prefs(self) -> dict[str, str]:
        return {k: v.value for k, v in self.user_preferences.items()}

    def get_all_operational_prefs(self) -> dict[str, str]:
        return {k: v.value for k, v in self.operational_preferences.items()}

    # ── 操作 ──

    def set_user(self, entry: PreferenceEntry) -> None:
        """设置用户偏好。"""
        if entry.pref_type != PreferenceType.USER:
            raise ValueError(f"Expected USER preference, got {entry.pref_type}")
        self.user_preferences[entry.key] = entry

    def set_operational(self, entry: PreferenceEntry) -> None:
        """设置操作偏好。"""
        if entry.pref_type != PreferenceType.OPERATIONAL:
            raise ValueError(f"Expected OPERATIONAL preference, got {entry.pref_type}")
        self.operational_preferences[entry.key] = entry

    def remove_user(self, key: str) -> None:
        self.user_preferences.pop(key, None)

    def remove_operational(self, key: str) -> None:
        self.operational_preferences.pop(key, None)

    def apply_to(self, target: dict) -> dict:
        """将偏好应用到目标字典（不覆盖已有值）。

        安全: User 偏好优先级 > Operational 偏好。
        不会修改传入的 dict，返回新 dict。
        """
        result = dict(target)
        # Operational first (lower priority)
        for k, v in self.get_all_operational_prefs().items():
            if k not in result:
                result[k] = v
        # User preferences override operational
        for k, v in self.get_all_user_prefs().items():
            result[k] = v
        return result

    def summary(self) -> str:
        return (
            f"PreferenceModel: {self.user_count} user prefs, "
            f"{self.operational_count} operational prefs"
        )
