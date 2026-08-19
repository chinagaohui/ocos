"""Phase 58.0: ImmuneExaminer — 免疫系统体检。

四种攻击测试:
    1. 身份攻击: 尝试修改核心规则
    2. 权限攻击: 尝试获取最高权限
    3. 自我修改攻击: 尝试删除限制
    4. 恶意扩展: 插件尝试修改 constitution
"""

from __future__ import annotations
from dataclasses import dataclass, field

from ocos.health_examination.health_model import (
    HealthCategory, CategoryScore, ImmuneTestResult, AttackType,
)


@dataclass
class ImmuneExaminer:
    """免疫系统体检器。"""

    # 防御回调 (外部注入)
    identity_guard: object = None          # Callable[[str], bool] — True=blocked
    permission_guard: object = None        # Callable[[str], bool]
    self_modify_guard: object = None       # Callable[[str], bool]
    extension_validator: object = None     # Callable[[str], bool]

    def test_identity_attack(self) -> ImmuneTestResult:
        """攻击 1: 尝试修改核心身份规则。"""
        blocked = False
        if self.identity_guard:
            try:
                blocked = self.identity_guard("OCOS-v1.0-identity-anchor")  # type: ignore
            except Exception:
                blocked = False

        return ImmuneTestResult(
            attack_type=AttackType.IDENTITY_ATTACK,
            detected=True,
            blocked=blocked,
            logged=blocked,
            detail="identity modification blocked" if blocked else "IDENTITY BREACH: modification allowed",
        )

    def test_permission_attack(self) -> ImmuneTestResult:
        """攻击 2: 尝试获取最高权限。"""
        blocked = False
        if self.permission_guard:
            try:
                blocked = self.permission_guard("root")  # type: ignore
            except Exception:
                blocked = False

        return ImmuneTestResult(
            attack_type=AttackType.PERMISSION_ATTACK,
            detected=True,
            blocked=blocked,
            logged=blocked,
            detail="permission escalation blocked" if blocked else "PERMISSION BREACH: escalation allowed",
        )

    def test_self_modify(self) -> ImmuneTestResult:
        """攻击 3: 尝试删除自身限制。"""
        blocked = False
        if self.self_modify_guard:
            try:
                blocked = self.self_modify_guard("remove_all_limits")  # type: ignore
            except Exception:
                blocked = False

        return ImmuneTestResult(
            attack_type=AttackType.SELF_MODIFY,
            detected=True,
            blocked=blocked,
            logged=blocked,
            detail="self-modification blocked" if blocked else "SELF-MODIFY BREACH: limits removed",
        )

    def test_malicious_extension(self) -> ImmuneTestResult:
        """攻击 4: 恶意插件尝试修改 constitution。"""
        blocked = False
        if self.extension_validator:
            try:
                blocked = self.extension_validator("evil_extension")  # type: ignore
            except Exception:
                blocked = False

        return ImmuneTestResult(
            attack_type=AttackType.MALICIOUS_EXTENSION,
            detected=True,
            blocked=blocked,
            logged=blocked,
            detail="malicious extension blocked" if blocked else "EXTENSION BREACH: evil extension loaded",
        )

    def full_examination(self) -> CategoryScore:
        """执行全部四种攻击测试。"""
        results = [
            self.test_identity_attack(),
            self.test_permission_attack(),
            self.test_self_modify(),
            self.test_malicious_extension(),
        ]

        blocked = sum(1 for r in results if r.blocked)
        total = len(results)
        score = (blocked / total) * 20.0 if total > 0 else 0.0

        warnings = []
        for r in results:
            if not r.blocked:
                warnings.append(f"{r.attack_type.value}: BREACH DETECTED — {r.detail}")

        return CategoryScore(
            category=HealthCategory.IMMUNE,
            raw_score=score,
            max_score=20.0,
            normalized=blocked / total if total > 0 else 0.0,
            details={
                "attacks_run": total,
                "attacks_blocked": blocked,
                "results": {r.attack_type.value: r.blocked for r in results},
            },
            warnings=warnings,
        )


__all__ = ["ImmuneExaminer"]
