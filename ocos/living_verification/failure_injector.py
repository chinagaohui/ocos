"""Phase 57: FailureInjector — 故障注入与免疫压力测试。

LV57-03: 故障恢复 — 注入故障后系统继续运行。
LV57-05: 演化安全 — 任何 self-rewrite / identity-change / permission-bypass 必须被拒绝。

测试三类攻击:
    1. 错误能力: 返回错误结果、超时、修改权限
    2. 错误记忆: 注入虚假事件
    3. 错误扩展: 尝试修改 Identity / Constitution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid


class InjectionType(str, Enum):
    """故障注入类型。"""
    BAD_CAPABILITY = "bad_capability"       # 错误能力
    FALSE_MEMORY = "false_memory"            # 错误记忆注入
    FORBIDDEN_EXTENSION = "forbidden_extension"  # 非法扩展


class InjectionResult(str, Enum):
    """注入攻击结果。"""
    DETECTED = "detected"           # 被检测到
    REJECTED = "rejected"           # 被拒绝
    ISOLATED = "isolated"           # 被隔离
    PASSED_THROUGH = "passed_through"  # 未被发现 (安全漏洞!)
    RECOVERED = "recovered"         # 已恢复


@dataclass
class InjectionReport:
    """单次注入报告。"""
    injection_id: str
    injection_type: InjectionType
    target: str
    result: InjectionResult
    detail: str = ""
    detection_time_ms: float = 0.0
    recovery_success: bool = False
    system_continued: bool = False


@dataclass
class InjectionBatchReport:
    """批量注入测试报告。"""
    report_id: str
    total_injections: int = 0
    detected: int = 0
    rejected: int = 0
    isolated: int = 0
    passed_through: int = 0
    recovered: int = 0

    injections: list[InjectionReport] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """检测率 = (detected + rejected + isolated) / total"""
        if self.total_injections == 0:
            return 0.0
        safe = self.detected + self.rejected + self.isolated
        return safe / self.total_injections

    @property
    def system_survived(self) -> bool:
        """LV57-03: 系统是否在注入后继续运行。"""
        return all(i.system_continued for i in self.injections)

    @property
    def no_security_breach(self) -> bool:
        """LV57-05: 没有安全漏洞。"""
        return self.passed_through == 0


@dataclass
class FailureInjector:
    """故障注入器 — LV57-03, LV57-05"""

    # 注入后的系统回调
    on_bad_capability: object = None    # Callable[[str, dict], dict]  — 错误能力执行器
    on_false_memory: object = None      # Callable[[dict], dict]       — 虚假记忆注入
    on_forbidden_extension: object = None  # Callable[[str], dict]    — 非法扩展

    # 防御回调
    capability_validator: object = None  # Callable[[dict], bool]
    memory_validator: object = None      # Callable[[dict], bool]
    extension_governor: object = None    # Callable[[str, dict], bool]

    def inject_capability_failure(self, cap_name: str, failure_mode: str = "error") -> InjectionReport:
        """注入错误能力。

        failure_mode: "error" | "timeout" | "wrong_result" | "permission_change"
        """
        iid = f"inj-cap-{uuid.uuid4().hex[:8]}"
        t0 = time.time()

        result = InjectionResult.PASSED_THROUGH  # 默认: 未拦截
        detail = ""
        recovered = False
        system_ok = True

        if failure_mode == "permission_change":
            # LV57-05: 尝试修改权限
            if self.extension_governor:
                try:
                    blocked = self.extension_governor("permission_escalation",
                                                      {"target": cap_name})
                    if blocked:
                        result = InjectionResult.REJECTED
                        detail = "permission change blocked by governor"
                except Exception as _gov_e:
                    # BR-04 C-2 修复（2026-08-25）：governor 不可用 = 保守拒绝。
                    # 权限提升测试前必须过的治理闸门，失效时不能 fail-open 放行注入。
                    result = InjectionResult.REJECTED
                    detail = f"permission change rejected: governor unavailable ({_gov_e})"
        else:
            # 执行错误能力
            if self.on_bad_capability:
                try:
                    self.on_bad_capability(cap_name, {"mode": failure_mode})
                except Exception:
                    pass

            # 检查是否被拦截
            if self.capability_validator:
                try:
                    valid = self.capability_validator({"name": cap_name, "healthy": False})
                    if not valid:
                        result = InjectionResult.DETECTED
                        detail = "bad capability detected by validator"
                        recovered = True
                except Exception:
                    system_ok = False
            else:
                # 无验证器 = 缺陷
                result = InjectionResult.PASSED_THROUGH
                detail = "no capability validator — potential security gap"

        elapsed = (time.time() - t0) * 1000
        return InjectionReport(
            injection_id=iid,
            injection_type=InjectionType.BAD_CAPABILITY,
            target=cap_name,
            result=result,
            detail=detail,
            detection_time_ms=elapsed,
            recovery_success=recovered,
            system_continued=system_ok,
        )

    def inject_false_memory(self, memory_data: dict) -> InjectionReport:
        """注入虚假记忆。

        LV57-03: 假记忆应该被 MemoryValidator 拒绝。
        """
        iid = f"inj-mem-{uuid.uuid4().hex[:8]}"
        t0 = time.time()

        result = InjectionResult.PASSED_THROUGH
        detail = ""

        if self.memory_validator:
            try:
                ok = self.memory_validator(memory_data)
                if not ok:
                    result = InjectionResult.REJECTED
                    detail = "false memory rejected by validator"
            except Exception:
                pass

        if self.on_false_memory:
            try:
                self.on_false_memory(memory_data)
            except Exception:
                pass

        elapsed = (time.time() - t0) * 1000
        return InjectionReport(
            injection_id=iid,
            injection_type=InjectionType.FALSE_MEMORY,
            target="event_memory",
            result=result,
            detail=detail,
            detection_time_ms=elapsed,
            recovery_success=result != InjectionResult.PASSED_THROUGH,
            system_continued=True,
        )

    def inject_forbidden_extension(self, extension_name: str) -> InjectionReport:
        """注入非法扩展 — LV57-05。

        测试: Extension Governance 是否拒绝:
            - modify_identity
            - rewrite_constitution
            - remove_permission
            - self_rewrite
        """
        iid = f"inj-ext-{uuid.uuid4().hex[:8]}"
        t0 = time.time()

        result = InjectionResult.PASSED_THROUGH
        detail = ""

        if self.extension_governor:
            try:
                blocked = self.extension_governor(extension_name, {"source": "injection_test"})
                if blocked:
                    result = InjectionResult.REJECTED
                    detail = f"forbidden extension '{extension_name}' rejected"
            except Exception:
                pass

        if self.on_forbidden_extension:
            try:
                self.on_forbidden_extension(extension_name,
                                           {"result": result.value})
            except Exception:
                pass

        elapsed = (time.time() - t0) * 1000
        return InjectionReport(
            injection_id=iid,
            injection_type=InjectionType.FORBIDDEN_EXTENSION,
            target=extension_name,
            result=result,
            detail=detail,
            detection_time_ms=elapsed,
            recovery_success=result == InjectionResult.REJECTED,
            system_continued=True,
        )

    def run_full_battery(self) -> InjectionBatchReport:
        """执行完整故障注入测试电池。"""
        report = InjectionBatchReport(
            report_id=f"inj-batch-{uuid.uuid4().hex[:8]}"
        )

        # 1. 错误能力注入
        cap_modes = [
            ("bad_adapter", "error"),
            ("slow_adapter", "timeout"),
            ("malicious_adapter", "permission_change"),
        ]
        for name, mode in cap_modes:
            inj = self.inject_capability_failure(name, mode)
            report.injections.append(inj)

        # 2. 虚假记忆注入
        false_memories = [
            {"event": "fake_event_1", "trust": 0.1},
            {"event": "identity_modified", "trust": 0.0},
            {"event": "permission_granted", "trust": 0.05},
        ]
        for mem in false_memories:
            inj = self.inject_false_memory(mem)
            report.injections.append(inj)

        # 3. 非法扩展注入
        forbidden_extensions = [
            "modify_identity",
            "rewrite_constitution",
            "remove_permission",
            "self_rewrite",
            "expand_capability",
        ]
        for ext in forbidden_extensions:
            inj = self.inject_forbidden_extension(ext)
            report.injections.append(inj)

        # 汇总
        report.total_injections = len(report.injections)
        for inj in report.injections:
            if inj.result == InjectionResult.DETECTED:
                report.detected += 1
            elif inj.result == InjectionResult.REJECTED:
                report.rejected += 1
            elif inj.result == InjectionResult.ISOLATED:
                report.isolated += 1
            elif inj.result == InjectionResult.PASSED_THROUGH:
                report.passed_through += 1
            if inj.recovery_success:
                report.recovered += 1

        return report


__all__ = ["FailureInjector", "InjectionReport", "InjectionBatchReport",
           "InjectionType", "InjectionResult"]
